import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from hashlib import sha256
from typing import Any

from app.core.logging import log_event, log_event_rate_limited

logger = logging.getLogger("today_highlights.cache")

# Shared background executor for SWR refreshes — bounded to avoid runaway threads
_swr_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="swr-refresh")


def _log_cache_failure(operation: str, exc: Exception, *, level: int = logging.WARNING) -> None:
    log_event_rate_limited(
        logger,
        fingerprint=f"cache:{operation}:{type(exc).__name__}",
        interval_seconds=30,
        channel="application",
        category="cache",
        event="cache_operation_failed",
        level=level,
        operation=operation,
        backend="redis",
        exception_type=type(exc).__name__,
        status="fallback",
    )


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
# Redis cache backend
# ---------------------------------------------------------------------------

class RedisCacheBackend:
    """Redis-backed shared cache with distributed locks and generation-based
    invalidation."""

    def __init__(self, client, *, prefix: str, lock_ttl_seconds: int = 45):
        self._client = client
        self._prefix = prefix
        self._lock_ttl_seconds = lock_ttl_seconds

    def _cache_key(self, key: str) -> str:
        return f"{self._prefix}:cache:v1:{key}"

    def _lock_key(self, key: str) -> str:
        return f"{self._prefix}:lock:v1:{key}"

    def _generation_key(self, function_id: str) -> str:
        return f"{self._prefix}:generation:v1:{function_id}"

    # -- status --

    def status(self) -> str:
        return "redis"

    # -- envelope storage --

    def get(self, key: str) -> dict | None:
        try:
            raw = self._client.get(self._cache_key(key))
        except Exception as exc:
            _log_cache_failure("get", exc)
            return None
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        if payload.get("schema_version") != 1:
            return None
        if not isinstance(payload.get("fresh_until"), (int, float)):
            return None
        if "value" not in payload:
            return None
        return payload

    def set(self, key: str, envelope: dict, ttl_seconds: int) -> None:
        try:
            self._client.set(
                self._cache_key(key),
                json.dumps(envelope, ensure_ascii=False),
                ex=ttl_seconds,
            )
        except Exception as exc:
            _log_cache_failure("set", exc)

    # -- fallback delegation (managed by ResilientCacheBackend) --

    def get_fallback(self, key: str) -> dict | None:
        return None

    def set_fallback(self, key: str, envelope: dict, ttl_seconds: int) -> None:
        pass

    # -- distributed locks with token-checked release --

    def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool:
        try:
            result = self._client.set(
                self._lock_key(key), token, nx=True, ex=ttl_seconds
            )
            return bool(result)
        except Exception as exc:
            _log_cache_failure("acquire_lock", exc)
            return False

    def release_lock(self, key: str, token: str) -> None:
        try:
            lock_key = self._lock_key(key)
            current = self._client.get(lock_key)
            if current == token:
                self._client.delete(lock_key)
        except Exception as exc:
            _log_cache_failure("release_lock", exc)

    # -- generation-based invalidation --

    def get_generation(self, function_id: str) -> int:
        try:
            val = self._client.get(self._generation_key(function_id))
            return int(val) if val is not None else 0
        except Exception as exc:
            _log_cache_failure("get_generation", exc)
            return 0

    def clear_function(self, function_id: str) -> None:
        try:
            self._client.incr(self._generation_key(function_id))
        except Exception as exc:
            _log_cache_failure("clear_function", exc)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Resilient (Redis-primary, memory-fallback) backend
# ---------------------------------------------------------------------------


class ResilientCacheBackend:
    """Redis-first cache backend with automatic memory fallback.

    Successful Redis writes are mirrored to the memory backend so
    fallback data is available immediately. Redis recovery is attempted
    on demand, at most once per *retry_interval_seconds*.
    """

    def __init__(
        self,
        *,
        redis_factory,
        memory: MemoryCacheBackend,
        prefix: str,
        socket_timeout_seconds: float = 1.0,
        lock_ttl_seconds: int = 45,
        retry_interval_seconds: int = 30,
    ):
        self._redis_factory = redis_factory
        self._memory = memory
        self._prefix = prefix
        self._socket_timeout_seconds = socket_timeout_seconds
        self._lock_ttl_seconds = lock_ttl_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._redis: RedisCacheBackend | None = None
        self._status: str = "memory-disabled"
        self._last_retry_attempt: float = 0.0
        self._lock = threading.Lock()

    # -- lifecycle --

    def initialize(self) -> None:
        try:
            client = self._redis_factory()
            client.ping()
            self._redis = RedisCacheBackend(
                client, prefix=self._prefix, lock_ttl_seconds=self._lock_ttl_seconds
            )
            self._status = "redis"
            log_event(
                logger,
                channel="application",
                category="cache",
                event="cache_backend_ready",
                backend="redis",
            )
        except Exception as exc:
            self._redis = None
            self._status = "memory-fallback"
            log_event(
                logger,
                channel="application",
                category="cache",
                event="cache_backend_fallback",
                level=logging.WARNING,
                backend="redis",
                fallback="memory",
                exception_type=type(exc).__name__,
            )

    def status(self) -> str:
        return self._status

    # -- Redis availability --

    def _redis_available(self) -> RedisCacheBackend | None:
        if self._status == "redis" and self._redis is not None:
            return self._redis
        # Attempt reconnection at most once per retry interval
        now = time.time()
        with self._lock:
            if now - self._last_retry_attempt < self._retry_interval_seconds:
                return None
            self._last_retry_attempt = now
        try:
            client = self._redis_factory()
            client.ping()
            self._redis = RedisCacheBackend(
                client, prefix=self._prefix, lock_ttl_seconds=self._lock_ttl_seconds
            )
            self._status = "redis"
            log_event(
                logger,
                channel="application",
                category="cache",
                event="cache_backend_recovered",
                backend="redis",
            )
            return self._redis
        except Exception as exc:
            self._status = "memory-fallback"
            _log_cache_failure("reconnect", exc)
            return None

    # -- envelope storage --

    def get(self, key: str) -> dict | None:
        redis = self._redis_available()
        if redis is not None:
            try:
                result = redis.get(key)
                if result is not None:
                    return result
            except Exception as exc:
                _log_cache_failure("get", exc)
        return None

    def set(self, key: str, envelope: dict, ttl_seconds: int) -> None:
        redis = self._redis_available()
        if redis is not None:
            try:
                redis.set(key, envelope, ttl_seconds)
                # Mirror to memory fallback
                self._memory.set_fallback(key, envelope, ttl_seconds)
            except Exception as exc:
                _log_cache_failure("set", exc)
        else:
            # Use memory directly when Redis is unavailable
            self._memory.set(key, envelope, ttl_seconds)

    # -- fallback (read from memory mirror) --

    def get_fallback(self, key: str) -> dict | None:
        return self._memory.get_fallback(key)

    def set_fallback(self, key: str, envelope: dict, ttl_seconds: int) -> None:
        self._memory.set_fallback(key, envelope, ttl_seconds)

    # -- distributed locks --

    def acquire_lock(self, key: str, token: str, ttl_seconds: int) -> bool:
        redis = self._redis_available()
        if redis is not None:
            try:
                return redis.acquire_lock(key, token, ttl_seconds)
            except Exception as exc:
                _log_cache_failure("acquire_lock", exc)
        return self._memory.acquire_lock(key, token, ttl_seconds)

    def release_lock(self, key: str, token: str) -> None:
        redis = self._redis_available()
        if redis is not None:
            try:
                redis.release_lock(key, token)
            except Exception as exc:
                _log_cache_failure("release_lock", exc)
        self._memory.release_lock(key, token)

    # -- generation-based invalidation --

    def get_generation(self, function_id: str) -> int:
        redis = self._redis_available()
        if redis is not None:
            try:
                return redis.get_generation(function_id)
            except Exception as exc:
                _log_cache_failure("get_generation", exc)
        return self._memory.get_generation(function_id)

    def clear_function(self, function_id: str) -> None:
        redis = self._redis_available()
        if redis is not None:
            try:
                redis.clear_function(function_id)
            except Exception as exc:
                _log_cache_failure("clear_function", exc)
        self._memory.clear_function(function_id)

    def close(self) -> None:
        self._memory.close()
# ---------------------------------------------------------------------------
# Global cache backend lifecycle
# ---------------------------------------------------------------------------

_cache_backend: MemoryCacheBackend | ResilientCacheBackend | None = None
_cold_wait_seconds: float = 2.0
_cold_poll_seconds: float = 0.05
_max_waiters_per_key: int = 4


def initialize_cache() -> None:
    """Create and initialise the cache backend based on application settings.
    Must be called once during FastAPI startup."""
    global _cache_backend
    from app.core.config import settings

    memory = MemoryCacheBackend(maxsize=256)
    if not settings.redis_enabled:
        _cache_backend = memory
        log_event(
            logger,
            channel="application",
            category="cache",
            event="cache_backend_ready",
            backend="memory",
            reason="redis_disabled",
        )
        return

    try:
        import redis
        client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
        )
        backend = ResilientCacheBackend(
            redis_factory=lambda: client,
            memory=memory,
            prefix=settings.redis_key_prefix,
            socket_timeout_seconds=settings.redis_socket_timeout_seconds,
            lock_ttl_seconds=settings.redis_lock_ttl_seconds,
            retry_interval_seconds=settings.redis_retry_interval_seconds,
        )
        backend.initialize()
        _cache_backend = backend
    except Exception as exc:
        _cache_backend = memory
        log_event(
            logger,
            channel="application",
            category="cache",
            event="cache_backend_fallback",
            level=logging.WARNING,
            backend="redis",
            fallback="memory",
            exception_type=type(exc).__name__,
            exc_info=True,
        )


def shutdown_cache() -> None:
    """Close the cache backend and the SWR executor pool."""
    global _cache_backend
    if _cache_backend is not None:
        _cache_backend.close()
        _cache_backend = None
    shutdown_swr_executor()


def cache_backend_status() -> str:
    """Return a short label for the active cache backend."""
    backend = _cache_backend
    if backend is None:
        return "uninitialized"
    return backend.status()


def _get_backend() -> MemoryCacheBackend | ResilientCacheBackend:
    backend = _cache_backend
    if backend is None:
        raise RuntimeError("cache backend not initialised")
    return backend


# ---------------------------------------------------------------------------
# Test hooks
# ---------------------------------------------------------------------------


def configure_cache_backend_for_tests(
    backend=None,
    *,
    cold_wait_seconds: float = 0.05,
    cold_poll_seconds: float = 0.01,
    max_waiters_per_key: int = 4,
) -> None:
    global _cache_backend, _cold_wait_seconds, _cold_poll_seconds, _max_waiters_per_key
    _cache_backend = backend or MemoryCacheBackend(maxsize=32)
    _cold_wait_seconds = cold_wait_seconds
    _cold_poll_seconds = cold_poll_seconds
    _max_waiters_per_key = max_waiters_per_key


def reset_cache_backend_for_tests() -> None:
    global _cache_backend, _cold_wait_seconds, _cold_poll_seconds, _max_waiters_per_key
    if _cache_backend is not None:
        _cache_backend.close()
    _cache_backend = None
    _cold_wait_seconds = 2.0
    _cold_poll_seconds = 0.05
    _max_waiters_per_key = 4


# ---------------------------------------------------------------------------
# ttl_cache decorator — shared backend-aware
# ---------------------------------------------------------------------------

_VALIDATE_WARNED: set[str] = set()


def ttl_cache(ttl_seconds: int = 30, swr: int = 0, shared: bool = True, maxsize: int = 128):
    """TTL cache with optional stale-while-revalidate.

    When ``shared=True`` (default) the decorated function reads and writes
    through the global backend (Redis or memory). Set ``shared=False`` for
    sensitive values like decrypted credentials — those use a decorator-local
    in-process cache and never touch the shared store.
    """

    def decorator(func):
        function_id = f"{func.__module__}.{func.__qualname__}"
        local_memory: MemoryCacheBackend | None = None
        local_lock = threading.Lock()
        _local_refreshing: set[str] = set()
        _local_refreshing_lock = threading.Lock()

        def _local_backend() -> MemoryCacheBackend:
            nonlocal local_memory
            if local_memory is None:
                with local_lock:
                    if local_memory is None:
                        local_memory = MemoryCacheBackend(maxsize=maxsize)
            return local_memory

        @wraps(func)
        def wrapper(*args, **kwargs):
            # --- Unsupported argument types: bypass cache entirely ---
            try:
                argument_hash = build_argument_hash(args, kwargs)
            except CacheSerializationError:
                key = f"{function_id}:{id(args)}"
                with _local_refreshing_lock:
                    if key not in _VALIDATE_WARNED:
                        _VALIDATE_WARNED.add(key)
                        if len(_VALIDATE_WARNED) > 64:
                            _VALIDATE_WARNED.clear()
                        logger.warning(
                            "unsupported cache argument type in %s — bypassing cache",
                            function_id,
                        )
                return func(*args, **kwargs)

            # --- Determine backend ---
            if shared:
                backend = _get_backend()
            else:
                backend = _local_backend()

            generation = backend.get_generation(function_id)
            cache_key = f"{function_id}:{generation}:{argument_hash}"
            lock_key = cache_key

            # --- Fast path: fresh hit ---
            envelope = backend.get(cache_key)
            if envelope is not None and time.time() < envelope["fresh_until"]:
                return envelope["value"]

            # --- SWR path: stale hit ---
            if envelope is not None and swr > 0 and time.time() < envelope["fresh_until"] + swr:
                should_refresh = False
                with _local_refreshing_lock:
                    if cache_key not in _local_refreshing:
                        _local_refreshing.add(cache_key)
                        should_refresh = True

                if should_refresh:
                    def _bg_refresh():
                        try:
                            result = func(*args, **kwargs)
                            now = time.time()
                            backend.set(cache_key, {
                                "schema_version": 1,
                                "created_at": now,
                                "fresh_until": now + ttl_seconds,
                                "value": result,
                            }, ttl_seconds + swr)
                        except Exception as exc:
                            log_event_rate_limited(
                                logger,
                                fingerprint=f"swr:{function_id}:{type(exc).__name__}",
                                interval_seconds=30,
                                channel="application",
                                category="cache",
                                event="swr_refresh_failed",
                                level=logging.WARNING,
                                function_id=function_id,
                                exception_type=type(exc).__name__,
                            )
                        finally:
                            with _local_refreshing_lock:
                                _local_refreshing.discard(cache_key)

                    _swr_executor.submit(_bg_refresh)

                return envelope["value"]

            # --- Cold start / full miss ---
            token = cache_key
            if backend.acquire_lock(lock_key, token, ttl_seconds):
                try:
                    result = func(*args, **kwargs)
                    now = time.time()
                    backend.set(cache_key, {
                        "schema_version": 1,
                        "created_at": now,
                        "fresh_until": now + ttl_seconds,
                        "value": result,
                    }, ttl_seconds + swr)
                    return result
                finally:
                    backend.release_lock(lock_key, token)
            else:
                # Not the lock owner — wait for owner (with back-pressure)
                local_waiters = 0
                deadline = time.time() + _cold_wait_seconds

                while time.time() < deadline:
                    if local_waiters >= _max_waiters_per_key:
                        break
                    local_waiters += 1
                    time.sleep(_cold_poll_seconds)
                    envelope = backend.get(cache_key)
                    if envelope is not None:
                        return envelope["value"]
                    local_waiters -= 1

                fallback = backend.get_fallback(cache_key)
                if fallback is not None:
                    return fallback["value"]

                raise CacheBusyError(f"cache cold start timeout for {function_id}")

        def cache_clear():
            try:
                b = _get_backend() if shared else _local_backend()
                b.clear_function(function_id)
            except RuntimeError:
                pass
            _local_backend().clear_function(function_id)

        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator
