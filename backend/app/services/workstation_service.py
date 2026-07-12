from datetime import date

from sqlalchemy.exc import IntegrityError

from app.core.constants import WorkstationStatus
from app.core.exceptions import biz, not_found, conflict, invalid_state
from app.models import Workstation
from app.repositories import workstation_repo, assignment_repo, employee_repo, operation_log_repo
from app.services import scope_service


def _ip(r): return r.client.host if r and r.client else None
def _ua(r): return r.headers.get("User-Agent") if r else None


def _out(w: Workstation) -> dict:
    return {"id": w.id, "code": w.code, "location": w.location, "type": w.type,
            "status": w.status, "current_employee_id": w.current_employee_id,
            "assign_date": w.assign_date.isoformat() if w.assign_date else None,
            "version": w.version, "notes": w.notes}


def _visible(db, user, w: Workstation) -> bool:
    scope = scope_service.asset_scope(db, user)
    if scope["mode"] == "all":
        return True
    if scope["mode"] == "self":
        return w.current_employee_id == scope.get("employee_id")
    return w.current_employee_id in (scope.get("employee_ids") or set())


def list_(db, user, params, type, status) -> dict:
    scope = scope_service.asset_scope(db, user)
    items, total = workstation_repo.paginate(db, params=params, type=type, status=status, scope=scope)
    return {"items": [_out(w) for w in items], "total": total, "page": params.page, "page_size": params.page_size}


def get_one(db, user, id_) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None or not _visible(db, user, w):
        raise not_found("工位不存在")
    return _out(w)


def create(db, user, data, req) -> dict:
    if workstation_repo.get_by_code(db, data.code) is not None:
        raise biz(3005, "工位编号已存在")
    w = workstation_repo.create(db, code=data.code, location=data.location, type=data.type,
                                status=WorkstationStatus.IDLE, notes=data.notes,
                                created_by=user.id, updated_by=user.id)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "工位编号已存在")
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="create",
                              target_type="workstation", target_id=w.id, detail={"code": w.code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(w)


def update(db, user, id_, data, req) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    for f in ("location", "type", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(w, f, v)
    w.updated_by = user.id
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="update",
                              target_type="workstation", target_id=w.id, detail={"code": w.code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(w)


def assign(db, user, id_, data, req) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    emp = employee_repo.get_active(db, data.employee_id)
    if emp is None or emp.status != 1:
        raise biz(3002, "目标员工不存在或已离职")
    d = data.assign_date or date.today()
    expected = data.version if data.version is not None else w.version
    n = workstation_repo.assign_if_free(db, id_, data.employee_id, d, expected, user.id)
    if n == 0:
        raise conflict("该工位已被占用，请刷新后重试")
    assignment_repo.create_ws(db, id_, data.employee_id, d, user.id)
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="assign",
                              target_type="workstation", target_id=id_,
                              detail={"employee_id": data.employee_id}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(w)
    return _out(w)


def release(db, user, id_, req) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    n = workstation_repo.release_if_occupied(db, id_, user.id)
    if n == 0:
        raise invalid_state("工位当前未被占用")
    assignment_repo.close_ws_open(db, id_, date.today())
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="release",
                              target_type="workstation", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(w)
    return _out(w)


def batch_release(db, user, ids, req) -> dict:
    released = 0
    for id_ in ids:
        n = workstation_repo.release_if_occupied(db, id_, user.id)
        if n == 1:
            assignment_repo.close_ws_open(db, id_, date.today())
            released += 1
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="batch_release",
                              target_type="workstation", target_id=None,
                              detail={"ids": ids, "released": released}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"released": released}


def set_status(db, user, id_, new_status, req) -> dict:
    if new_status not in (WorkstationStatus.IDLE, WorkstationStatus.RESERVED, WorkstationStatus.DISABLED):
        raise biz(2001, "非法的目标状态")
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    n = workstation_repo.set_status(db, id_, new_status, user.id)
    if n == 0:
        raise invalid_state("占用中的工位不能直接改状态，请先释放")
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="set_status",
                              target_type="workstation", target_id=id_, detail={"status": new_status},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(w)
    return _out(w)


def history(db, user, id_) -> list[dict]:
    w = workstation_repo.get_active(db, id_)
    if w is None or not _visible(db, user, w):
        raise not_found("工位不存在")
    rows = assignment_repo.list_ws(db, id_)
    return [{"employee_id": r.employee_id, "start_date": r.start_date.isoformat(),
             "end_date": r.end_date.isoformat() if r.end_date else None,
             "operator_id": r.operator_id} for r in rows]
