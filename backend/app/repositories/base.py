from sqlalchemy import false
from sqlalchemy.orm import Session


def get_by_id(db: Session, model, id_: str):
    return db.get(model, id_)


def apply_current_employee_scope(stmt, scope: dict, model):
    mode = scope["mode"]
    if mode == "all":
        return stmt
    if mode == "self":
        eid = scope.get("employee_id")
        return stmt.where(model.current_employee_id == eid) if eid else stmt.where(false())
    ids = scope.get("employee_ids") or set()
    return stmt.where(model.current_employee_id.in_(ids)) if ids else stmt.where(false())


def get_active(db: Session, model, id_: str):
    obj = db.get(model, id_)
    if obj is None:
        return None
    if hasattr(obj, "deleted_at") and obj.deleted_at is not None:
        return None
    return obj
