from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found, invalid_state
from app.models import Role
from app.repositories import role_repo, permission_repo, operation_log_repo


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None


def _to_out(r: Role) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name,
            "is_builtin": r.is_builtin, "data_scope": r.data_scope, "status": r.status}


def list_roles(db: Session, user: CurrentUser) -> dict:
    return {"items": [_to_out(r) for r in role_repo.list_all(db)]}


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    return _to_out(role)


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if role_repo.get_by_code(db, data.code) is not None:
        raise biz(3005, "角色编码已存在")
    role = role_repo.create(db, code=data.code, name=data.name, is_builtin=0,
                            data_scope=data.data_scope, status=data.status)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="create",
                              target_type="role", target_id=role.id,
                              detail={"code": role.code}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(role)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    fields = data.model_fields_set
    if role.is_builtin == 1 and (fields - {"name"}):
        raise invalid_state("内置角色仅允许修改名称")
    if "name" in fields and data.name is not None:
        role.name = data.name
    if "data_scope" in fields and data.data_scope is not None:
        role.data_scope = data.data_scope
    if "status" in fields and data.status is not None:
        role.status = data.status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="update",
                              target_type="role", target_id=role.id,
                              detail={"code": role.code}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(role)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    if role.is_builtin == 1:
        raise invalid_state("内置角色不可删除")
    if role_repo.users_count(db, role.id) > 0:
        raise biz(3002, "角色下有账号，不能删除")
    role_repo.delete(db, role)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="delete",
                              target_type="role", target_id=id_,
                              detail={"code": role.code}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def get_permissions(db: Session, user: CurrentUser, id_: str) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    return {"codes": sorted(role_repo.permission_codes_for_role(db, role.id))}


def assign_permissions(db: Session, user: CurrentUser, id_: str, codes: list[str], req: Request) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    if role.code == "super_admin":
        raise invalid_state("超级管理员权限不可修改")
    ids: set[str] = set()
    for code in set(codes):
        perm = permission_repo.get_by_code(db, code)
        if perm is None:
            raise biz(3002, f"权限点不存在: {code}")
        ids.add(perm.id)
    role_repo.set_permissions(db, role.id, ids)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="assign",
                              target_type="role", target_id=role.id,
                              detail={"codes": sorted(set(codes))}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"codes": sorted(set(codes))}


def all_permissions(db: Session, user: CurrentUser) -> dict:
    perms = permission_repo.list_all(db)
    grouped: dict[str, list] = {}
    for p in perms:
        grouped.setdefault(p.module, []).append({"code": p.code, "name": p.name})
    items = [{"module": m, "permissions": grouped[m]} for m in sorted(grouped)]
    return {"items": items}
