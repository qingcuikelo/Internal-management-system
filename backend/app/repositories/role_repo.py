from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.orm import Session

from app.models import Role, RolePermission, Permission, User


def get_by_id(db: Session, id_: str) -> Role | None:
    return db.get(Role, id_)


def permission_codes_for_role(db: Session, role_id: str) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return set(db.execute(stmt).scalars().all())


def list_all(db: Session) -> list[Role]:
    return list(db.execute(select(Role).order_by(Role.created_at)).scalars().all())


def get_by_code(db: Session, code: str) -> Role | None:
    return db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()


def create(db: Session, **fields) -> Role:
    role = Role(**fields)
    db.add(role)
    return role


def delete(db: Session, role: Role) -> None:
    db.execute(sa_delete(RolePermission).where(RolePermission.role_id == role.id))
    db.delete(role)


def users_count(db: Session, role_id: str) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role_id == role_id, User.deleted_at.is_(None))
    return db.execute(stmt).scalar_one()


def set_permissions(db: Session, role_id: str, permission_ids: set[str]) -> None:
    db.execute(sa_delete(RolePermission).where(RolePermission.role_id == role_id))
    for pid in permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))
