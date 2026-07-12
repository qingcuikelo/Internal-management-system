from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, RolePermission, Permission


def get_by_id(db: Session, id_: str) -> Role | None:
    return db.get(Role, id_)


def permission_codes_for_role(db: Session, role_id: str) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return set(db.execute(stmt).scalars().all())
