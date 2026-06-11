import time

import pytest

from app.core.cache import (
    CacheSerializationError,
    MemoryCacheBackend,
    build_argument_hash,
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
