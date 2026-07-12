from datetime import date

from sqlalchemy.exc import IntegrityError

from app.core.constants import DeviceStatus
from app.core.exceptions import biz, not_found, conflict, invalid_state
from app.models import Device
from app.repositories import device_repo, assignment_repo, employee_repo, operation_log_repo
from app.services import scope_service


def _ip(r): return r.client.host if r and r.client else None
def _ua(r): return r.headers.get("User-Agent") if r else None


def _out(d: Device) -> dict:
    return {"id": d.id, "asset_code": d.asset_code, "type": d.type, "brand": d.brand,
            "model": d.model, "serial_number": d.serial_number, "specs": d.specs,
            "purchase_date": d.purchase_date.isoformat() if d.purchase_date else None,
            "warranty_expire": d.warranty_expire.isoformat() if d.warranty_expire else None,
            "status": d.status, "current_employee_id": d.current_employee_id,
            "assign_date": d.assign_date.isoformat() if d.assign_date else None, "version": d.version,
            "notes": d.notes}


def _visible(db, user, d: Device) -> bool:
    scope = scope_service.asset_scope(db, user)
    if scope["mode"] == "all":
        return True
    if scope["mode"] == "self":
        return d.current_employee_id == scope.get("employee_id")
    return d.current_employee_id in (scope.get("employee_ids") or set())


def list_(db, user, params, type, status) -> dict:
    scope = scope_service.asset_scope(db, user)
    items, total = device_repo.paginate(db, params=params, type=type, status=status, scope=scope)
    return {"items": [_out(d) for d in items], "total": total, "page": params.page, "page_size": params.page_size}


def get_one(db, user, id_) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None or not _visible(db, user, d):
        raise not_found("设备不存在")
    return _out(d)


def create(db, user, data, req) -> dict:
    if device_repo.get_by_asset_code(db, data.asset_code) is not None:
        raise biz(3005, "资产编号已存在")
    d = device_repo.create(db, asset_code=data.asset_code, type=data.type, brand=data.brand,
                           model=data.model, serial_number=data.serial_number, specs=data.specs,
                           purchase_date=data.purchase_date, warranty_expire=data.warranty_expire,
                           status=DeviceStatus.IN_STOCK, notes=data.notes,
                           created_by=user.id, updated_by=user.id)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "资产编号/序列号已存在")
    operation_log_repo.create(db, user_id=user.id, module="device", action="create",
                              target_type="device", target_id=d.id, detail={"asset_code": d.asset_code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(d)


def update(db, user, id_, data, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    for f in ("type", "brand", "model", "serial_number", "specs", "purchase_date", "warranty_expire", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(d, f, v)
    d.updated_by = user.id
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "序列号已存在")
    operation_log_repo.create(db, user_id=user.id, module="device", action="update",
                              target_type="device", target_id=d.id, detail={"asset_code": d.asset_code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(d)


def checkout(db, user, id_, data, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    emp = employee_repo.get_active(db, data.employee_id)
    if emp is None or emp.status != 1:
        raise biz(3002, "目标员工不存在或已离职")
    day = data.assign_date or date.today()
    expected = data.version if data.version is not None else d.version
    n = device_repo.checkout_if_available(db, id_, data.employee_id, day, expected, user.id)
    if n == 0:
        raise conflict("该设备不可领用（非在库或已被他人领用），请刷新后重试")
    assignment_repo.create_dev(db, id_, data.employee_id, day, user.id)
    operation_log_repo.create(db, user_id=user.id, module="device", action="checkout",
                              target_type="device", target_id=id_, detail={"employee_id": data.employee_id},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(d)
    return _out(d)


def return_(db, user, id_, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    n = device_repo.return_if_in_use(db, id_, user.id)
    if n == 0:
        raise invalid_state("设备当前不在使用中")
    assignment_repo.close_dev_open(db, id_, date.today())
    operation_log_repo.create(db, user_id=user.id, module="device", action="return",
                              target_type="device", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(d)
    return _out(d)


def repair(db, user, id_, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    n = device_repo.to_repair(db, id_, user.id)
    if n == 0:
        raise invalid_state("仅在库设备可送修")
    operation_log_repo.create(db, user_id=user.id, module="device", action="repair",
                              target_type="device", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(d)
    return _out(d)


def scrap(db, user, id_, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    n = device_repo.to_scrap(db, id_, user.id)
    if n == 0:
        raise invalid_state("仅在库或维修中的设备可报废")
    operation_log_repo.create(db, user_id=user.id, module="device", action="scrap",
                              target_type="device", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(d)
    return _out(d)


def history(db, user, id_) -> list[dict]:
    d = device_repo.get_active(db, id_)
    if d is None or not _visible(db, user, d):
        raise not_found("设备不存在")
    rows = assignment_repo.list_dev(db, id_)
    return [{"employee_id": r.employee_id, "checkout_date": r.checkout_date.isoformat(),
             "return_date": r.return_date.isoformat() if r.return_date else None,
             "operator_id": r.operator_id} for r in rows]
