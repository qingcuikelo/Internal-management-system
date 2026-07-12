from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Permission


def get_by_code(db: Session, code: str) -> Permission | None:
    return db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()


def list_all(db: Session) -> list[Permission]:
    return list(db.execute(select(Permission)).scalars().all())
