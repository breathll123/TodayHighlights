from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.models.entities import Highlight, Topic
from app.schemas.public import HighlightRead, TopicRead

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
