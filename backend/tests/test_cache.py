import time

import fakeredis
import pytest

from app.core.cache import (
    CacheBusyError,
    CacheSerializationError,
    MemoryCacheBackend,
    RedisCacheBackend,
    ResilientCacheBackend,
    build_argument_hash,
    configure_cache_backend_for_tests,
    reset_cache_backend_for_tests,
    ttl_cache,
)


def test_argument_hash_is_stable_for_dict_order():
    left = build_argument_hash(({"market": "CN", "limit": 10},), {})
    right = build_argument_hash(({"limit": 10, "market": "CN"},), {})
    assert left == right


def test_argument_hash_does_not_expose_sensitive_values():
    digest = build_argument_hash(("secret-cookie-value",), {})
    assert "secret-cookie-value" not in digest
    assert len(digest) == 64


def test_argument_hash_rejects_runtime_objects():
    with pytest.raises(CacheSerializationError):
        build_argument_hash(({"_media_cache": object()},), {})


def test_memory_backend_expires_values():
    backend = MemoryCacheBackend(maxsize=8)
    backend.set("key", {"schema_version": 1, "value": [1], "fresh_until": time.time() + 1, "created_at": time.time()}, ttl_seconds=1)
    assert backend.get("key") is not None
    time.sleep(1.05)
    assert backend.get("key") is None


def test_memory_clear_function_changes_generation_and_drops_fallback():
    backend = MemoryCacheBackend(maxsize=8)
    assert backend.get_generation("fn") == 0
    backend.set_fallback("cache-key", {"schema_version": 1, "value": [1], "fresh_until": time.time() + 30, "created_at": time.time()}, 30)
    backend.clear_function("fn")
    assert backend.get_generation("fn") == 1
    assert backend.get_fallback("cache-key") is None


def test_redis_backend_shares_values_and_generation():
    client = fakeredis.FakeRedis(decode_responses=True)
    first = RedisCacheBackend(client, prefix="test", lock_ttl_seconds=45)
    second = RedisCacheBackend(client, prefix="test", lock_ttl_seconds=45)
    envelope = {"schema_version": 1, "created_at": time.time(), "fresh_until": time.time() + 30, "value": [1]}

    first.set("cache-key", envelope, 60)
    assert second.get("cache-key")["value"] == [1]

    first.clear_function("module.func")
    assert second.get_generation("module.func") == 1


def test_redis_lock_requires_matching_token_to_release():
    client = fakeredis.FakeRedis(decode_responses=True)
    backend = RedisCacheBackend(client, prefix="test", lock_ttl_seconds=45)
    assert backend.acquire_lock("lock-key", "owner-a", 45)
    backend.release_lock("lock-key", "owner-b")
    assert not backend.acquire_lock("lock-key", "owner-c", 45)
    backend.release_lock("lock-key", "owner-a")
    assert backend.acquire_lock("lock-key", "owner-c", 45)


def test_resilient_backend_uses_memory_when_redis_fails():
    class BrokenRedis:
        def ping(self):
            raise ConnectionError("offline")

    memory = MemoryCacheBackend(maxsize=8)
    backend = ResilientCacheBackend(
        redis_factory=lambda: BrokenRedis(),
        memory=memory,
        prefix="test",
        socket_timeout_seconds=1,
        lock_ttl_seconds=45,
        retry_interval_seconds=30,
    )
    backend.initialize()
    assert backend.status() == "memory-fallback"


def test_ttl_cache_fresh_hit_calls_function_once():
    backend = MemoryCacheBackend(maxsize=32)
    configure_cache_backend_for_tests(backend)
    calls = 0

    @ttl_cache(30)
    def load(config, limit):
        nonlocal calls
        calls += 1
        return [{"limit": limit}]

    assert load({"market": "CN"}, 10) == [{"limit": 10}]
    assert load({"market": "CN"}, 10) == [{"limit": 10}]
    assert calls == 1
    reset_cache_backend_for_tests()


def test_ttl_cache_unsupported_argument_bypasses_cache(caplog):
    backend = MemoryCacheBackend(maxsize=32)
    configure_cache_backend_for_tests(backend)
    calls = 0

    @ttl_cache(30)
    def load(config):
        nonlocal calls
        calls += 1
        return [calls]

    assert load({"_media_cache": object()}) == [1]
    assert load({"_media_cache": object()}) == [2]
    assert "unsupported cache argument type" in caplog.text
    reset_cache_backend_for_tests()


def test_local_only_cache_never_uses_shared_backend():
    class SharedBackendMustNotRun(MemoryCacheBackend):
        def get(self, key):
            raise AssertionError("shared backend was used")

    configure_cache_backend_for_tests(SharedBackendMustNotRun(maxsize=8))
    calls = 0

    @ttl_cache(30, shared=False)
    def decrypt(value):
        nonlocal calls
        calls += 1
        return f"plain-{value}"

    assert decrypt("cipher") == "plain-cipher"
    assert decrypt("cipher") == "plain-cipher"
    assert calls == 1
    reset_cache_backend_for_tests()


def test_lock_waiter_does_not_execute_wrapped_function():
    import threading

    backend = MemoryCacheBackend(maxsize=32)
    configure_cache_backend_for_tests(
        backend,
        cold_wait_seconds=0.05,
        cold_poll_seconds=0.01,
        max_waiters_per_key=4,
    )
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    @ttl_cache(30)
    def load():
        nonlocal calls
        calls += 1
        entered.set()
        release.wait(timeout=1)
        return [{"ok": True}]

    owner = threading.Thread(target=load)
    owner.start()
    assert entered.wait(timeout=1)

    with pytest.raises(CacheBusyError):
        load()

    release.set()
    owner.join(timeout=1)
    assert calls == 1
    reset_cache_backend_for_tests()
