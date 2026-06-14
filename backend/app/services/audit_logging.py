import logging
from collections.abc import Iterable

from fastapi import Request

from app.core.logging import current_log_context, log_event
from app.models.entities import User

logger = logging.getLogger("today_highlights.audit")


def log_admin_change(
    *,
    action: str,
    object_type: str,
    object_name: str,
    object_id: int | str | None,
    changed_fields: Iterable[str],
    request: Request | None = None,
    user: User | None = None,
) -> None:
    state = getattr(request, "state", None)
    username = user.username if user else getattr(state, "username", "-")
    user_id = user.id if user else getattr(state, "user_id", "-")
    context = current_log_context()
    request_id = getattr(state, "request_id", None) or context.get("request_id", "-")
    safe_fields = sorted(
        "api_key" if field == "api_key_encrypted" else str(field)
        for field in changed_fields
    )
    log_event(
        logger,
        channel="application",
        category="admin",
        event="admin.changed",
        username=username,
        user_id=user_id,
        action=action,
        object_type=object_type,
        object_name=object_name,
        object_id=object_id,
        changed_fields=safe_fields,
        request=str(request_id)[:8],
    )
