from pathlib import Path


REQUIRED_LOG_KEYS = {
    "LOG_DIR",
    "LOG_LEVEL",
    "LOG_ROTATION",
    "LOG_RETENTION_DAYS",
    "LOG_MAX_MESSAGE_LENGTH",
    "LOG_CONSOLE_ENABLED",
    "LOG_SLOW_REQUEST_MS",
    "LOG_ACCESS_EXCLUDE_PATHS",
    "LOG_TRUST_PROXY_HEADERS",
    "LOG_QUEUE_SIZE",
    "LOG_DETAIL_CRAWLER",
    "LOG_DETAIL_AI",
    "LOG_RESPONSE_PREVIEW_CHARS",
    "LOG_URL_QUERY_MODE",
}


def _env_keys(path: Path) -> set[str]:
    return {
        line.split("=", 1)[0].strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }


def test_logging_keys_exist_in_both_environment_examples():
    backend_dir = Path(__file__).resolve().parents[1]
    root_dir = backend_dir.parent

    assert REQUIRED_LOG_KEYS <= _env_keys(backend_dir / ".env.example")
    assert REQUIRED_LOG_KEYS <= _env_keys(root_dir / ".env.example")


def test_generated_log_directory_is_ignored():
    backend_dir = Path(__file__).resolve().parents[1]
    root_dir = backend_dir.parent

    assert "backend/logs/" in (root_dir / ".gitignore").read_text()


def test_logging_detail_settings_have_safe_defaults():
    from app.core.config import Settings

    fields = Settings.model_fields
    assert fields["log_detail_crawler"].default is True
    assert fields["log_detail_ai"].default is True
    assert fields["log_response_preview_chars"].default == 500
    assert fields["log_url_query_mode"].default == "safe"
