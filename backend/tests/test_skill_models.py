from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.entities import Skill, SkillStat


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_skill_and_stat_persist() -> None:
    with _session() as s:
        s.add(Skill(source="github", external_id="1", name="alpha", author="o",
                    url="u", popularity=10, popularity_kind="stars"))
        s.commit()
        skill = s.query(Skill).one()
        s.add(SkillStat(skill_id=skill.id, popularity=10, captured_at=datetime(2026, 6, 24)))
        s.commit()
        assert s.query(Skill).count() == 1
        assert s.query(SkillStat).count() == 1


def test_skill_unique_per_source_external() -> None:
    with _session() as s:
        s.add(Skill(source="github", external_id="42", name="a", url="u"))
        s.commit()
        # Same (source, external_id) must be rejected; a different source is fine.
        s.add(Skill(source="github", external_id="42", name="dup", url="u2"))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        s.add(Skill(source="other", external_id="42", name="ok", url="u3"))
        s.commit()
        assert s.query(Skill).count() == 2
