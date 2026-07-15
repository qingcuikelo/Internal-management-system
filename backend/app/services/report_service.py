from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import not_found
from app.models import Employee, Department, Workstation, Device
from app.repositories import employee_repo
from app.services import scope_service


def _dept_filtered_employee_ids(db: Session, user: CurrentUser) -> set[str] | None:
    scope = scope_service.report_scope(db, user)
    if scope["mode"] == "all":
        return None  # no filter
    if scope["mode"] == "self":
        eid = scope.get("employee_id")
        return {eid} if eid else set()
    return scope.get("dept_ids", set())


def employee_assets(db: Session, user: CurrentUser, employee_id: str) -> dict:
    # scope check: dept_manager can only see own-dept employees
    allowed = _dept_filtered_employee_ids(db, user)
    if allowed is not None:
        emp = employee_repo.get_active(db, employee_id)
        if emp is None or emp.department_id not in allowed:
            raise not_found("员工不存在")
    ws = db.execute(
        select(Workstation).where(
            Workstation.current_employee_id == employee_id,
            Workstation.status == 2,
            Workstation.deleted_at.is_(None),
        )
    ).scalars().first()
    devices = db.execute(
        select(Device).where(
            Device.current_employee_id == employee_id,
            Device.status == 2,
            Device.deleted_at.is_(None),
        )
    ).scalars().all()
    return {
        "workstation": {"id": ws.id, "code": ws.code, "location": ws.location} if ws else None,
        "devices": [{"id": d.id, "asset_code": d.asset_code, "type": d.type, "brand": d.brand, "model": d.model} for d in devices],
    }


def idle_assets(db: Session, user: CurrentUser) -> dict:
    scope = scope_service.report_scope(db, user)
    if scope["mode"] == "dept":
        return {"idle_workstations": None, "idle_devices": None,
                "note": "闲置资产归属全局管理，本角色不可见"}
    ws_count = db.execute(
        select(func.count()).select_from(Workstation).where(
            Workstation.status == 1, Workstation.deleted_at.is_(None)
        )
    ).scalar_one()
    d_count = db.execute(
        select(func.count()).select_from(Device).where(
            Device.status == 1, Device.deleted_at.is_(None)
        )
    ).scalar_one()
    return {"idle_workstations": ws_count, "idle_devices": d_count}


def device_by_department(db: Session, user: CurrentUser,
                          department_id: str | None = None) -> dict:
    allowed = _dept_filtered_employee_ids(db, user)
    # devices with a holder in visible scope
    base = (select(Employee.department_id, func.count(Device.id).label("cnt"))
            .select_from(Device)
            .join(Employee, Employee.id == Device.current_employee_id)
            .where(Device.status == 2, Device.deleted_at.is_(None),
                   Employee.deleted_at.is_(None), Employee.status == 1))
    if allowed is not None:
        base = base.where(Employee.department_id.in_(allowed))
    if department_id:
        base = base.where(Employee.department_id == department_id)
    base = base.group_by(Employee.department_id)
    rows = db.execute(base).all()
    dept_names = {}
    if rows:
        ids = [r[0] for r in rows]
        depts = db.execute(select(Department).where(Department.id.in_(ids))).scalars().all()
        dept_names = {d.id: d.name for d in depts}
    items = [{"department_id": r[0], "department_name": dept_names.get(r[0], ""), "count": r[1]}
             for r in rows]
    return {"items": items}


def warranty_expiring(db: Session, user: CurrentUser, days: int = 30) -> dict:
    today = date.today()
    cutoff = today + timedelta(days=days)
    allowed = _dept_filtered_employee_ids(db, user)
    base = (select(Device)
            .where(Device.warranty_expire.between(today, cutoff),
                   Device.status != 4,
                   Device.deleted_at.is_(None))
            .order_by(Device.warranty_expire.asc()))
    devices = db.execute(base).scalars().all()
    if allowed is not None:
        devices = [d for d in devices if d.current_employee_id is not None
                   and employee_repo.get_active(db, d.current_employee_id) is not None
                   and employee_repo.get_active(db, d.current_employee_id).department_id in allowed]
    return {"items": [{"id": d.id, "asset_code": d.asset_code, "type": d.type,
                        "brand": d.brand, "model": d.model,
                        "current_employee_id": d.current_employee_id,
                        "warranty_expire": str(d.warranty_expire)}
                      for d in devices]}
