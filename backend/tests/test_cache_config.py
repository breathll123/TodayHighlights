from app.core.config import settings


def test_redis_settings_have_safe_defaults():
    assert settings.redis_enabled is False
    assert settings.redis_url.startswith(("redis://", "rediss://"))
    assert settings.redis_key_prefix
    assert settings.redis_socket_timeout_seconds > 0
    assert settings.redis_lock_ttl_seconds > 0
    assert settings.redis_retry_interval_seconds > 0
