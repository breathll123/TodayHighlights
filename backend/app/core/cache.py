import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

logger = logging.getLogger(__name__)

# Shared background executor for SWR refreshes — bounded to avoid runaway threads
_swr_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="swr-refresh")


def shutdown_swr_executor():
    """Called during app shutdown."""
    _swr_executor.shutdown(wait=False)


def ttl_cache(ttl_seconds: int = 30, swr: int = 0, maxsize: int = 128):
    """In-memory TTL cache with optional stale-while-revalidate. Thread-safe.

    Args:
        ttl_seconds: How long cached data is considered "fresh".
        swr: Stale-while-revalidate window in seconds. After ttl_seconds expires,
             serve stale data for up to `swr` additional seconds while refreshing
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
