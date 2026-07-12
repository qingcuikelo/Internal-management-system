from datetime import date

from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import Session

from app.core.constants import DeviceStatus
from app.models import Device
from app.repositories.base import apply_current_employee_scope
from app.schemas.common import PageParams


def get_active(db: Session, id_: str) -> Device | None:
    return db.execute(select(Device).where(Device.id == id_, Device.deleted_at.is_(None))).scalar_one_or_none()


def get_by_asset_code(db: Session, code: str) -> Device | None:
    return db.execute(select(Device).where(Device.asset_code == code, Device.deleted_at.is_(None))).scalar_one_or_none()


def paginate(db: Session, *, params: PageParams, type: str | None = None,
             status: int | None = None, scope: dict) -> tuple[list[Device], int]:
    base = select(Device).where(Device.deleted_at.is_(None))
    base = apply_current_employee_scope(base, scope, Device)
    if type:
        base = base.where(Device.type == type)
    if status is not None:
        base = base.where(Device.status == status)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(Device.asset_code.like(kw), Device.serial_number.like(kw)))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    order = Device.created_at.desc() if params.order == "desc" else Device.created_at.asc()
    stmt = base.order_by(order).offset((params.page - 1) * params.page_size).limit(params.page_size)
    return list(db.execute(stmt).scalars().all()), total


def create(db: Session, **fields) -> Device:
    d = Device(**fields)
    db.add(d)
    return d


def checkout_if_available(db, id_, employee_id, assign_date, expected_version, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status == DeviceStatus.IN_STOCK,
                   Device.version == expected_version, Device.deleted_at.is_(None))
            .values(current_employee_id=employee_id, status=DeviceStatus.IN_USE,
                    assign_date=assign_date, version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def return_if_in_use(db, id_, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status == DeviceStatus.IN_USE, Device.deleted_at.is_(None))
            .values(current_employee_id=None, status=DeviceStatus.IN_STOCK, assign_date=None,
                    version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def to_repair(db, id_, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status == DeviceStatus.IN_STOCK, Device.deleted_at.is_(None))
            .values(status=DeviceStatus.REPAIR, version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def to_scrap(db, id_, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status.in_([DeviceStatus.IN_STOCK, DeviceStatus.REPAIR]),
                   Device.deleted_at.is_(None))
            .values(status=DeviceStatus.SCRAPPED, version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount
