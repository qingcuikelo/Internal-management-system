from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found
from app.models import Employee
from app.repositories import employee_repo, department_repo, operation_log_repo
from app.services import scope_service


def _ip(req):
    return req.client.host if req and req.client else None


def _ua(req):
    return req.headers.get("User-Agent") if req else None


def _dept_name(db, dept_id):
    if not dept_id:
        return None
    d = department_repo.get_active(db, dept_id)
    return d.name if d else None


def _list_item(db, e: Employee) -> dict:
    return {"id": e.id, "employee_no": e.employee_no, "name": e.name,
            "department_name": _dept_name(db, e.department_id),
            "position": e.position, "status": e.status}


def _detail(db, e: Employee) -> dict:
    sup_name = None
    if e.direct_supervisor_id:
        sup = employee_repo.get_active(db, e.direct_supervisor_id)
        sup_name = sup.name if sup else None
    return {"id": e.id, "employee_no": e.employee_no, "name": e.name, "gender": e.gender,
            "email": e.email, "phone": e.phone, "department_id": e.department_id,
            "department_name": _dept_name(db, e.department_id),
            "direct_supervisor_id": e.direct_supervisor_id, "supervisor_name": sup_name,
            "position": e.position, "hire_date": e.hire_date.isoformat() if e.hire_date else None,
            "status": e.status}


def _visible(db, user, emp: Employee) -> bool:
    scope = scope_service.employee_scope(db, user)
    if scope["mode"] == "all":
        return True
    if scope["mode"] == "self":
        return emp.id == scope.get("employee_id")
    return emp.department_id in (scope.get("dept_ids") or set())


def list_employees(db: Session, user: CurrentUser, params, department_id, status) -> dict:
    scope = scope_service.employee_scope(db, user)
    items, total = employee_repo.paginate(db, params=params, department_id=department_id,
                                          status=status, scope=scope)
    return {"items": [_list_item(db, e) for e in items], "total": total,
            "page": params.page, "page_size": params.page_size}


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    emp = employee_repo.get_active(db, id_)
    if emp is None or not _visible(db, user, emp):
        raise not_found("员工不存在")
    return _detail(db, emp)


def _check_refs(db, department_id, supervisor_id):
    if department_id and department_repo.get_active(db, department_id) is None:
        raise biz(3002, "部门不存在")
    if supervisor_id and employee_repo.get_active(db, supervisor_id) is None:
        raise biz(3004, "直属上级不存在")


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if employee_repo.get_by_employee_no(db, data.employee_no) is not None:
        raise biz(3005, "工号已存在")
    _check_refs(db, data.department_id, data.direct_supervisor_id)
    emp = employee_repo.create(
        db, employee_no=data.employee_no, name=data.name, gender=data.gender,
        email=data.email, phone=data.phone, department_id=data.department_id,
        direct_supervisor_id=data.direct_supervisor_id, position=data.position,
        hire_date=data.hire_date, status=1, created_by=user.id, updated_by=user.id,
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "工号/邮箱/手机号已存在")
    operation_log_repo.create(db, user_id=user.id, module="employee", action="create",
                              target_type="employee", target_id=emp.id,
                              detail={"employee_no": emp.employee_no}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _detail(db, emp)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    emp = employee_repo.get_active(db, id_)
    if emp is None or not _visible(db, user, emp):
        raise not_found("员工不存在")
    if data.direct_supervisor_id is not None:
        if data.direct_supervisor_id == id_:
            raise biz(3004, "直属上级不能形成环")
        if employee_repo.get_active(db, data.direct_supervisor_id) is None:
            raise biz(3004, "直属上级不存在")
        # walking up from the new supervisor must not reach this employee
        if employee_repo.supervisor_chain_has(db, data.direct_supervisor_id, id_):
            raise biz(3004, "直属上级不能形成环")
        emp.direct_supervisor_id = data.direct_supervisor_id
    if data.department_id is not None:
        if data.department_id and department_repo.get_active(db, data.department_id) is None:
            raise biz(3002, "部门不存在")
        emp.department_id = data.department_id
    for field in ("name", "gender", "email", "phone", "position", "hire_date", "status"):
        val = getattr(data, field)
        if val is not None:
            setattr(emp, field, val)
    emp.updated_by = user.id
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "邮箱/手机号已存在")
    operation_log_repo.create(db, user_id=user.id, module="employee", action="update",
                              target_type="employee", target_id=emp.id,
                              detail={"employee_no": emp.employee_no}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _detail(db, emp)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    emp = employee_repo.get_active(db, id_)
    if emp is None or not _visible(db, user, emp):
        raise not_found("员工不存在")
    employee_repo.soft_delete(db, emp)
    operation_log_repo.create(db, user_id=user.id, module="employee", action="delete",
                              target_type="employee", target_id=id_,
                              detail={"employee_no": emp.employee_no}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def batch_department(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if data.department_id and department_repo.get_active(db, data.department_id) is None:
        raise biz(3002, "部门不存在")
    n = employee_repo.batch_set_department(db, data.employee_ids, data.department_id)
    operation_log_repo.create(db, user_id=user.id, module="employee", action="batch_update",
                              target_type="employee", target_id=None,
                              detail={"ids": data.employee_ids, "department_id": data.department_id},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"updated": n}
