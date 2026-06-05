from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import CryptoService
from app.models.entities import AIModelConfig
from app.schemas.admin import AIModelConfigWrite


def _crypto() -> CryptoService:
    return CryptoService(settings.app_secret_key)


def _unset_other_defaults(session: Session, keep_id: int | None = None) -> None:
    for model in session.scalars(select(AIModelConfig).where(AIModelConfig.is_default.is_(True))):
        if keep_id is None or model.id != keep_id:
            model.is_default = False


def serialize_ai_model(model: AIModelConfig) -> dict:
    return {
        "id": model.id,
        "name": model.name,
        "base_url": model.base_url,
        "model": model.model,
        "is_default": model.is_default,
        "enabled": model.enabled,
        "notes": model.notes,
        "has_api_key": bool(model.api_key_encrypted),
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def list_ai_models(session: Session) -> list[AIModelConfig]:
    return list(session.scalars(select(AIModelConfig).order_by(AIModelConfig.is_default.desc(), AIModelConfig.id.desc())))


def get_default_ai_model(session: Session) -> AIModelConfig | None:
    return session.scalar(select(AIModelConfig).where(AIModelConfig.enabled.is_(True), AIModelConfig.is_default.is_(True)))


def create_ai_model(session: Session, payload: AIModelConfigWrite) -> AIModelConfig:
    if payload.is_default:
        _unset_other_defaults(session)
    model = AIModelConfig(
        name=payload.name,
        base_url=payload.base_url.rstrip("/"),
        model=payload.model,
        api_key_encrypted=_crypto().encrypt(payload.api_key),
        is_default=payload.is_default,
        enabled=payload.enabled,
        notes=payload.notes,
    )
    session.add(model)
    session.flush()
    return model


def update_ai_model(session: Session, model_id: int, payload: AIModelConfigWrite) -> AIModelConfig:
    model = session.get(AIModelConfig, model_id)
    if model is None:
        raise ValueError("AI model config not found")
    if payload.is_default:
        _unset_other_defaults(session, keep_id=model.id)
    model.name = payload.name
    model.base_url = payload.base_url.rstrip("/")
    model.model = payload.model
    if payload.api_key:
        model.api_key_encrypted = _crypto().encrypt(payload.api_key)
    model.is_default = payload.is_default
    model.enabled = payload.enabled
    model.notes = payload.notes
    session.flush()
    return model


def set_default_ai_model(session: Session, model_id: int) -> AIModelConfig:
    model = session.get(AIModelConfig, model_id)
    if model is None:
        raise ValueError("AI model config not found")
    _unset_other_defaults(session, keep_id=model.id)
    model.is_default = True
    model.enabled = True
    session.flush()
    return model
