from datetime import date

from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import Session

from app.core.constants import WorkstationStatus
from app.models import Workstation
from app.repositories.base import apply_current_employee_scope
from app.schemas.common import PageParams


def get_active(db: Session, id_: str) -> Workstation | None:
    stmt = select(Workstation).where(Workstation.id == id_, Workstation.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_by_code(db: Session, code: str) -> Workstation | None:
    stmt = select(Workstation).where(Workstation.code == code, Workstation.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def paginate(db: Session, *, params: PageParams, type: str | None = None,
             status: int | None = None, scope: dict) -> tuple[list[Workstation], int]:
    base = select(Workstation).where(Workstation.deleted_at.is_(None))
    base = apply_current_employee_scope(base, scope, Workstation)
    if type:
        base = base.where(Workstation.type == type)
    if status is not None:
        base = base.where(Workstation.status == status)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(Workstation.code.like(kw), Workstation.location.like(kw)))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    order = Workstation.created_at.desc() if params.order == "desc" else Workstation.created_at.asc()
    stmt = base.order_by(order).offset((params.page - 1) * params.page_size).limit(params.page_size)
    return list(db.execute(stmt).scalars().all()), total


def create(db: Session, **fields) -> Workstation:
    w = Workstation(**fields)
    db.add(w)
    return w


def assign_if_free(db: Session, id_: str, employee_id: str, assign_date: date,
                   expected_version: int, updated_by: str) -> int:
    stmt = (update(Workstation)
            .where(Workstation.id == id_, Workstation.status == WorkstationStatus.IDLE,
                   Workstation.version == expected_version, Workstation.deleted_at.is_(None))
            .values(current_employee_id=employee_id, status=WorkstationStatus.OCCUPIED,
                    assign_date=assign_date, version=Workstation.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def release_if_occupied(db: Session, id_: str, updated_by: str) -> int:
    stmt = (update(Workstation)
            .where(Workstation.id == id_, Workstation.status == WorkstationStatus.OCCUPIED,
                   Workstation.deleted_at.is_(None))
            .values(current_employee_id=None, status=WorkstationStatus.IDLE, assign_date=None,
                    version=Workstation.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def set_status(db: Session, id_: str, new_status: int, updated_by: str) -> int:
    stmt = (update(Workstation)
            .where(Workstation.id == id_, Workstation.status != WorkstationStatus.OCCUPIED,
                   Workstation.deleted_at.is_(None))
            .values(status=new_status, version=Workstation.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount
