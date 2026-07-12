from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_active_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_active_by_id(db: Session, id_: str) -> User | None:
    stmt = select(User).where(User.id == id_, User.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def update_last_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)


def set_password(db: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    user.pwd_updated_at = datetime.now(timezone.utc)
