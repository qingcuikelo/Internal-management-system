from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found
from app.models import Department
from app.repositories import department_repo, operation_log_repo
from app.services import scope_service
from app.utils.tree import descendant_ids


def _visible(db: Session, user: CurrentUser, dept: Department) -> bool:
    ids = scope_service.accessible_department_ids(db, user)
    return ids is None or dept.id in ids


def _to_out(d: Department) -> dict:
    return {"id": d.id, "name": d.name, "parent_id": d.parent_id,
            "manager_id": d.manager_id, "sort_order": d.sort_order, "status": d.status}


def list_departments(db: Session, user: CurrentUser) -> list[dict]:
    ids = scope_service.accessible_department_ids(db, user)
    rows = department_repo.list_active(db)
    if ids is not None:
        rows = [d for d in rows if d.id in ids]
    return [_to_out(d) for d in rows]


def get_tree(db: Session, user: CurrentUser) -> list[dict]:
    ids = scope_service.accessible_department_ids(db, user)
    rows = department_repo.list_active(db)
    if ids is not None:
        rows = [d for d in rows if d.id in ids]
    by_parent: dict = {}
    for d in rows:
        by_parent.setdefault(d.parent_id, []).append(d)
    visible_ids = {d.id for d in rows}

    def build(parent_id):
        out = []
        for d in by_parent.get(parent_id, []):
            out.append({"id": d.id, "name": d.name, "sort_order": d.sort_order,
                        "status": d.status, "children": build(d.id)})
        return out

    # roots = nodes whose parent is None OR whose parent is not visible (subtree roots)
    roots = [d for d in rows if d.parent_id is None or d.parent_id not in visible_ids]
    result = []
    for d in roots:
        result.append({"id": d.id, "name": d.name, "sort_order": d.sort_order,
                       "status": d.status, "children": build(d.id)})
    return result


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    dept = department_repo.get_active(db, id_)
    if dept is None or not _visible(db, user, dept):
        raise not_found("部门不存在")
    return _to_out(dept)


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if data.parent_id and department_repo.get_active(db, data.parent_id) is None:
        raise biz(3002, "上级部门不存在")
    dept = department_repo.create(
        db, name=data.name, parent_id=data.parent_id, manager_id=data.manager_id,
        sort_order=data.sort_order, status=data.status,
        created_by=user.id, updated_by=user.id,
    )
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="department", action="create",
                              target_type="department", target_id=dept.id,
                              detail={"name": dept.name}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(dept)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    dept = department_repo.get_active(db, id_)
    if dept is None or not _visible(db, user, dept):
        raise not_found("部门不存在")
    if data.parent_id is not None:
        if data.parent_id == id_:
            raise biz(3003, "上级部门不能是自己或其下级")
        rows = department_repo.all_id_parent_rows(db)
        if data.parent_id in descendant_ids(rows, id_):
            raise biz(3003, "上级部门不能是自己或其下级")
        if department_repo.get_active(db, data.parent_id) is None:
            raise biz(3002, "上级部门不存在")
        dept.parent_id = data.parent_id
    for field in ("name", "manager_id", "sort_order", "status"):
        val = getattr(data, field)
        if val is not None:
            setattr(dept, field, val)
    dept.updated_by = user.id
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="department", action="update",
                              target_type="department", target_id=dept.id,
                              detail={"name": dept.name}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(dept)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    dept = department_repo.get_active(db, id_)
    if dept is None or not _visible(db, user, dept):
        raise not_found("部门不存在")
    if department_repo.has_active_children(db, id_):
        raise biz(3002, "部门下有子部门，不能删除")
    if department_repo.has_active_employees(db, id_):
        raise biz(3002, "部门下有在职员工，不能删除")
    department_repo.soft_delete(db, dept)
    operation_log_repo.create(db, user_id=user.id, module="department", action="delete",
                              target_type="department", target_id=id_,
                              detail={"name": dept.name}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None
