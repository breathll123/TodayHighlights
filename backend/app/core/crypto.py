from cryptography.fernet import Fernet, InvalidToken


class CryptoService:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except Exception as exc:
            raise ValueError("APP_SECRET_KEY must be a urlsafe base64 Fernet key") from exc

    def encrypt(self, value: str) -> str:
        if value == "":
            return ""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        if value == "":
            return ""
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Encrypted value cannot be decrypted with the configured key") from exc
