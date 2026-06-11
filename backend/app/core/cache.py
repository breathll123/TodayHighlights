import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from hashlib import sha256
from typing import Any

logger = logging.getLogger(__name__)

# Shared background executor for SWR refreshes — bounded to avoid runaway threads
_swr_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="swr-refresh")


def shutdown_swr_executor():
    """Called during app shutdown."""
    _swr_executor.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Cache exception hierarchy
# ---------------------------------------------------------------------------

class CacheRefreshError(RuntimeError):
    """Third-party data fetch failed. Used by adapters so the cache layer
    can distinguish upstream failures from legitimate empty results."""

    pass


class CacheBusyError(RuntimeError):
    """Too many concurrent waiters for a cold-cache key — caller should
    fall back to local data or return an empty result."""

    pass


class CacheSerializationError(TypeError):
    """An argument or return value cannot be safely serialised for caching."""

    pass


# ---------------------------------------------------------------------------
# Deterministic argument serialisation
# ---------------------------------------------------------------------------

_SERIALIZATION_WARNED: set[str] = set()


def _normalize_for_cache(value: Any, _depth: int = 0) -> Any:
    """Recursively normalise a value for deterministic JSON serialisation.

    Allowed types: ``None``, ``bool``, ``int``, ``float``, ``str``,
    ``list``, ``tuple``, and ``dict`` whose keys are all ``str``.
    """

    if _depth > 16:
        raise CacheSerializationError("nesting depth exceeded")

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_for_cache(item, _depth + 1) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CacheSerializationError("cache dictionaries require string keys")
        return {key: _normalize_for_cache(value[key], _depth + 1) for key in sorted(value)}
    raise CacheSerializationError(f"unsupported cache argument type: {type(value).__name__}")


def build_argument_hash(args: tuple, kwargs: dict) -> str:
    """Build a stable SHA-256 hex digest from positional and keyword arguments.

    Raw values are never embedded in the digest — only the hash is exposed.
    """

    normalized = {"args": _normalize_for_cache(args), "kwargs": _normalize_for_cache(kwargs)}
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Memory cache backend (always available)
# ---------------------------------------------------------------------------


class MemoryCacheBackend:
    """Thread-safe in-process cache with LRU eviction, SWR fallback entries,
    in-memory locks, and generation counters for function-level invalidation."""

    def __init__(self, maxsize: int = 128):
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._fallback: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._generations: dict[str, int] = {}
        self._locks: dict[str, str] = {}

    # -- status --

    def status(self) -> str:
        return "memory"

    # -- envelope storage --

    def get(self, key: str) -> dict | None:
        now = time.time()
        with self._lock:
            if key in self._store:
                expires_at, envelope = self._store[key]
                if now < expires_at:
                    self._store.move_to_end(key)
                    return envelope
                del self._store[key]
        return None

    def set(self, key: str, envelope: dict, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._store[key] = (expires_at, envelope)
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    # -- fallback (mirror of successful shared-cache writes) --

    def get_fallback(self, key: str) -> dict | None:
        now = time.time()
        with self._lock:
            if key in self._fallback:
                expires_at, envelope = self._fallback[key]
                if now < expires_at:
                    self._fallback.move_to_end(key)
                    return envelope
                del self._fallback[key]
        return None

    def set_fallback(self, key: str, envelope: dict, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds
        with self._lock:
            self._fallback[key] = (expires_at, envelope)
            self._fallback.move_to_end(key)
            while len(self._fallback) > self._maxsize:
                self._fallback.popitem(last=False)

    # -- local locks --

    def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool:
        with self._lock:
            if key not in self._locks:
                self._locks[key] = token
                return True
        return False

    def release_lock(self, key: str, token: str) -> None:
        with self._lock:
            if self._locks.get(key) == token:
                del self._locks[key]

    # -- generation-based invalidation --

    def get_generation(self, function_id: str) -> int:
        return self._generations.get(function_id, 0)

    def clear_function(self, function_id: str) -> None:
        with self._lock:
            gen = self._generations.get(function_id, 0) + 1
            self._generations[function_id] = gen
            self._fallback.clear()

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Legacy ttl_cache decorator (preserved for backward compatibility;
# will be upgraded in Task 5)
# ---------------------------------------------------------------------------

def ttl_cache(ttl_seconds: int = 30, swr: int = 0, maxsize: int = 128):
    """In-memory TTL cache with optional stale-while-revalidate. Thread-safe.

    Args:
        ttl_seconds: How long cached data is considered "fresh".
        swr: Stale-while-revalidate window in seconds. After ttl_seconds expires,
             serve stale data for up to ``swr`` additional seconds while refreshing
             in the background. 0 = disabled (backward-compatible with old behavior).
        maxsize: Maximum number of cached entries. LRU eviction when exceeded.
    """

    store: OrderedDict[str, tuple[float, float, object]] = OrderedDict()
    # store values: (fresh_until, stale_until, value)
    lock = threading.Lock()
    refreshing: set[str] = set()
    refreshing_lock = threading.Lock()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            now = time.time()

            # --- Fast path: check cache ---
            with lock:
                if key in store:
                    fresh_until, stale_until, value = store[key]
                    # Move to end (most recently used)
                    store.move_to_end(key)

                    if now < fresh_until:
                        # Fresh hit — return cached data
                        return value

                    if swr > 0 and now < stale_until:
                        # Stale hit — return stale data, maybe trigger bg refresh
                        should_refresh = False
                        with refreshing_lock:
                            if key not in refreshing:
                                refreshing.add(key)
                                should_refresh = True

                        if should_refresh:
                            def _bg_refresh():
                                try:
                                    result = func(*args, **kwargs)
                                    _now = time.time()
                                    with lock:
                                        store[key] = (
                                            _now + ttl_seconds,
                                            _now + ttl_seconds + swr,
                                            result,
                                        )
                                        store.move_to_end(key)
                                except Exception:
                                    logger.warning(
                                        "SWR background refresh failed for %s", key
                                    )
                                finally:
                                    with refreshing_lock:
                                        refreshing.discard(key)

                            _swr_executor.submit(_bg_refresh)

                        return value

            # --- Cache miss or fully expired: caller blocks ---
            result = func(*args, **kwargs)
            now = time.time()
            with lock:
                store[key] = (now + ttl_seconds, now + ttl_seconds + swr, result)
                store.move_to_end(key)
                # LRU eviction
                while len(store) > maxsize:
                    store.popitem(last=False)
            return result

        def cache_clear():
            with lock:
                store.clear()
            with refreshing_lock:
                refreshing.clear()

        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator
