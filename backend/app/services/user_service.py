from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found, invalid_state
from app.core.security import hash_password
from app.models import Role, User
from app.repositories import user_repo, role_repo, employee_repo, operation_log_repo
from app.schemas.common import PageParams, paginate


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None


def _to_out(db: Session, u: User) -> dict:
    role = role_repo.get_by_id(db, u.role_id)
    return {"id": u.id, "username": u.username, "role_id": u.role_id,
            "role_code": role.code if role else None,
            "role_name": role.name if role else None,
            "employee_id": u.employee_id, "status": u.status,
            "last_login_at": u.last_login_at, "created_at": u.created_at}


def _check_role(db: Session, role_id: str) -> Role:
    role = role_repo.get_by_id(db, role_id)
    if role is None:
        raise biz(3002, "角色不存在")
    return role


def _check_employee(db: Session, employee_id: str, exclude_user_id: str | None = None) -> None:
    if employee_repo.get_active(db, employee_id) is None:
        raise biz(3002, "绑定的员工不存在")
    if user_repo.employee_bound_by(db, employee_id, exclude_user_id) is not None:
        raise biz(3005, "该员工已绑定其他账号")


def list_users(db: Session, user: CurrentUser, params: PageParams,
               status: int | None, role_code: str | None) -> dict:
    rows, total = user_repo.paginate(db, params=params, keyword=params.keyword,
                                     status=status, role_code=role_code)
    return paginate([_to_out(db, u) for u in rows], total, params)


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    return _to_out(db, u)


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if user_repo.get_active_by_username(db, data.username) is not None:
        raise biz(3005, "用户名已存在")
    _check_role(db, data.role_id)
    if data.employee_id:
        _check_employee(db, data.employee_id)
    u = user_repo.create(db, username=data.username,
                         password_hash=hash_password(data.password),
                         role_id=data.role_id, employee_id=data.employee_id or None,
                         status=data.status)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="create",
                              target_type="user", target_id=u.id,
                              detail={"username": u.username}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(db, u)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    fields = data.model_fields_set
    if "role_id" in fields and data.role_id:
        _check_role(db, data.role_id)
        u.role_id = data.role_id
    if "employee_id" in fields:
        if data.employee_id:
            _check_employee(db, data.employee_id, exclude_user_id=u.id)
        u.employee_id = data.employee_id or None
    if "status" in fields and data.status is not None:
        u.status = data.status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="update",
                              target_type="user", target_id=u.id,
                              detail={"username": u.username}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(db, u)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    if u.id == user.id:
        raise invalid_state("不能删除自己的账号")
    user_repo.soft_delete(db, u)
    operation_log_repo.create(db, user_id=user.id, module="user", action="delete",
                              target_type="user", target_id=u.id,
                              detail={"username": u.username}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def set_status(db: Session, user: CurrentUser, id_: str, status: int, req: Request) -> dict:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    if u.id == user.id and status == 0:
        raise invalid_state("不能禁用自己的账号")
    u.status = status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="status",
                              target_type="user", target_id=u.id,
                              detail={"status": status}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(db, u)


def reset_password(db: Session, user: CurrentUser, id_: str, new_password: str, req: Request) -> None:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    user_repo.set_password(db, u, hash_password(new_password))
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="reset_password",
                              target_type="user", target_id=u.id, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
