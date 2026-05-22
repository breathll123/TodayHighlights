from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import Highlight, Topic
from app.schemas.public import HighlightRead, TopicRead
from app.services.blocks import get_page_blocks

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/topics", response_model=list[TopicRead])
def list_topics(session: Session = Depends(get_session)) -> list[Topic]:
    return list(session.scalars(select(Topic).where(Topic.enabled.is_(True)).order_by(Topic.sort_order)))


@router.get("/highlights", response_model=list[HighlightRead])
def list_highlights(session: Session = Depends(get_session)) -> list[Highlight]:
    statement = (
        select(Highlight)
        .where(Highlight.is_hidden.is_(False))
        .order_by(Highlight.is_pinned.desc(), Highlight.score.desc(), Highlight.created_at.desc())
    )
    return list(session.scalars(statement))


@router.get("/pages/{route:path}/blocks")
def page_blocks(route: str, session: Session = Depends(get_session)) -> dict:
    route = "/" + route if not route.startswith("/") else route
    blocks = get_page_blocks(session, route)
    return {"blocks": blocks}
