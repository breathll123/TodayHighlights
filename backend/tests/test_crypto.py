import pytest

from app.core.crypto import CryptoService


def test_encrypt_decrypt_roundtrip() -> None:
    service = CryptoService("ThXyPQKmCPsS2H7tmF17YF6zxkStfOGYr0IkZ-9jJGw=")

    encrypted = service.encrypt("secret-cookie")

    assert encrypted != "secret-cookie"
    assert service.decrypt(encrypted) == "secret-cookie"


def test_decrypt_empty_value_returns_empty_string() -> None:
    service = CryptoService("ThXyPQKmCPsS2H7tmF17YF6zxkStfOGYr0IkZ-9jJGw=")

    assert service.decrypt("") == ""


def test_invalid_key_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="APP_SECRET_KEY must be a urlsafe base64 Fernet key"):
        CryptoService("not-a-fernet-key")
