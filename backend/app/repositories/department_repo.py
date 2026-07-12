from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Department, Employee


def get_active(db: Session, id_: str) -> Department | None:
    stmt = select(Department).where(Department.id == id_, Department.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def list_active(db: Session) -> list[Department]:
    stmt = (
        select(Department)
        .where(Department.deleted_at.is_(None))
        .order_by(Department.sort_order, Department.id)
    )
    return list(db.execute(stmt).scalars().all())


def all_id_parent_rows(db: Session) -> list[tuple[str, str | None]]:
    stmt = select(Department.id, Department.parent_id).where(Department.deleted_at.is_(None))
    return [(r[0], r[1]) for r in db.execute(stmt).all()]


def has_active_children(db: Session, id_: str) -> bool:
    stmt = select(func.count()).select_from(Department).where(
        Department.parent_id == id_, Department.deleted_at.is_(None)
    )
    return db.execute(stmt).scalar_one() > 0


def has_active_employees(db: Session, id_: str) -> bool:
    stmt = select(func.count()).select_from(Employee).where(
        Employee.department_id == id_, Employee.deleted_at.is_(None)
    )
    return db.execute(stmt).scalar_one() > 0


def create(db: Session, **fields) -> Department:
    dept = Department(**fields)
    db.add(dept)
    return dept


def soft_delete(db: Session, dept: Department) -> None:
    dept.deleted_at = datetime.now(timezone.utc)
