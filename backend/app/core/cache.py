import time
import threading
from functools import wraps


def ttl_cache(ttl_seconds: int = 30):
    """In-memory TTL cache for API responses. Thread-safe."""
    store: dict[str, tuple[float, object]] = {}
    lock = threading.Lock()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            now = time.time()
            with lock:
                if key in store:
                    expired_at, value = store[key]
                    if now < expired_at:
                        return value
            result = func(*args, **kwargs)
            with lock:
                store[key] = (now + ttl_seconds, result)
            return result

        wrapper.cache_clear = lambda: store.clear()
        return wrapper

    return decorator
