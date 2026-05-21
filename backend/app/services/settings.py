from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AppSetting


def set_plain_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key) or AppSetting(key=key)
    setting.value_json = {"value": value}
    session.add(setting)


def get_plain_setting(session: Session, key: str, default: str = "") -> str:
    setting = session.get(AppSetting, key)
    if setting is None or setting.value_json is None:
        return default
    return str(setting.value_json.get("value", default))


def set_secret_setting(session: Session, key: str, value: str) -> None:
    setting = session.get(AppSetting, key) or AppSetting(key=key)
    setting.value_encrypted = CryptoService(settings.app_secret_key).encrypt(value)
    session.add(setting)


def get_secret_setting(session: Session, key: str) -> str:
    setting = session.get(AppSetting, key)
    if setting is None:
        return ""
    return CryptoService(settings.app_secret_key).decrypt(setting.value_encrypted)
