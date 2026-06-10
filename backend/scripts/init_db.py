import sys
from collections.abc import Callable
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.entities import AppSetting, User
from app.services.admin_bootstrap import (
    BOOTSTRAP_COMPLETED_KEY,
    LEGACY_PASSWORD_KEY,
    is_legacy_default_admin,
)


def reconcile_bootstrap_state(session: Session) -> None:
    session.flush()

    admins = session.scalars(
        select(User).where(User.role == "admin", User.status == "active")
    ).all()
    has_real_admin = any(
        not is_legacy_default_admin(session, admin)
        for admin in admins
    )

    if has_real_admin and session.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is None:
        session.add(
            AppSetting(
                key=BOOTSTRAP_COMPLETED_KEY,
                value_json={"value": "true"},
                value_encrypted="",
            )
        )

    session.execute(
        delete(AppSetting).where(AppSetting.key == LEGACY_PASSWORD_KEY)
    )

    session.flush()


def main(
    *,
    upgrade_fn: Callable = command.upgrade,
    session_factory: Callable = SessionLocal,
    output: Callable[[str], None] = print,
) -> int:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    upgrade_fn(config, "head")

    with session_factory() as session:
        reconcile_bootstrap_state(session)
        session.commit()

    output("数据库初始化完成。请启动服务并在浏览器登录页创建首个管理员。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
