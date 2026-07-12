from datetime import datetime, timezone

from sqlalchemy import select, func, or_, false, update
from sqlalchemy.orm import Session

from app.models import Employee
from app.schemas.common import PageParams


def get_active(db: Session, id_: str) -> Employee | None:
    stmt = select(Employee).where(Employee.id == id_, Employee.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_by_employee_no(db: Session, no: str) -> Employee | None:
    stmt = select(Employee).where(Employee.employee_no == no, Employee.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def _apply_scope(stmt, scope: dict):
    mode = scope["mode"]
    if mode == "all":
        return stmt
    if mode == "self":
        eid = scope.get("employee_id")
        return stmt.where(Employee.id == eid) if eid else stmt.where(false())
    ids = scope.get("dept_ids") or set()
    return stmt.where(Employee.department_id.in_(ids)) if ids else stmt.where(false())


def paginate(db: Session, *, params: PageParams, department_id: str | None = None,
             status: int | None = None, scope: dict) -> tuple[list[Employee], int]:
    base = select(Employee).where(Employee.deleted_at.is_(None))
    base = _apply_scope(base, scope)
    if department_id:
        base = base.where(Employee.department_id == department_id)
    if status is not None:
        base = base.where(Employee.status == status)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(Employee.name.like(kw), Employee.employee_no.like(kw)))

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    order_col = Employee.created_at.desc() if params.order == "desc" else Employee.created_at.asc()
    stmt = base.order_by(order_col).offset((params.page - 1) * params.page_size).limit(params.page_size)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def create(db: Session, **fields) -> Employee:
    emp = Employee(**fields)
    db.add(emp)
    return emp


def soft_delete(db: Session, emp: Employee) -> None:
    emp.deleted_at = datetime.now(timezone.utc)


def batch_set_department(db: Session, ids: list[str], department_id: str | None, updated_by: str | None = None) -> int:
    stmt = (update(Employee)
            .where(Employee.id.in_(ids), Employee.deleted_at.is_(None))
            .values(department_id=department_id, updated_by=updated_by))
    result = db.execute(stmt)
    return result.rowcount


def supervisor_chain_has(db: Session, start_supervisor_id: str, target_id: str) -> bool:
    seen: set[str] = set()
    current = start_supervisor_id
    while current is not None and current not in seen:
        if current == target_id:
            return True
        seen.add(current)
        emp = db.get(Employee, current)
        current = emp.direct_supervisor_id if emp else None
    return False
