from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import User, Role
from app.schemas.common import PageParams


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


def paginate(db: Session, *, params: PageParams, keyword: str | None = None,
             status: int | None = None, role_code: str | None = None) -> tuple[list[User], int]:
    base = select(User).where(User.deleted_at.is_(None))
    if keyword:
        base = base.where(User.username.like(f"%{keyword}%"))
    if status is not None:
        base = base.where(User.status == status)
    if role_code:
        base = base.join(Role, Role.id == User.role_id).where(Role.code == role_code)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = (base.order_by(User.created_at.desc())
            .offset((params.page - 1) * params.page_size).limit(params.page_size))
    return list(db.execute(stmt).scalars().all()), total


def create(db: Session, **fields) -> User:
    user = User(**fields)
    db.add(user)
    return user


def soft_delete(db: Session, user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)


def employee_bound_by(db: Session, employee_id: str, exclude_user_id: str | None = None) -> User | None:
    stmt = select(User).where(User.employee_id == employee_id, User.deleted_at.is_(None))
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)
    return db.execute(stmt).scalar_one_or_none()
