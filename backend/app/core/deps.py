from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import unauthorized, forbidden
from app.core.redis import get_redis
from app.core.security import decode_token, password_changed_after_issue
from app.repositories import user_repo, role_repo


@dataclass
class CurrentUser:
    id: str
    username: str
    role_code: str
    data_scope: str
    permissions: set[str]
    employee_id: str | None
    department_id: str | None


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise unauthorized()
    return header[len("Bearer "):]


def get_current_user(request: Request, db: Session = Depends(get_db),
                     redis=Depends(get_redis)) -> CurrentUser:
    token = _extract_token(request)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise unauthorized()
    if redis.get(f"blacklist:{payload['jti']}"):
        raise unauthorized()

    user = user_repo.get_active_by_id(db, payload["sub"])
    if user is None or user.status != 1:
        raise unauthorized()
    if password_changed_after_issue(payload["iat"], user.pwd_updated_at):
        raise unauthorized()

    role = role_repo.get_by_id(db, user.role_id)
    if role is None:
        raise unauthorized()
    perms = role_repo.permission_codes_for_role(db, role.id)

    department_id = None
    if user.employee_id:
        from app.models import Employee
        emp = db.get(Employee, user.employee_id)
        department_id = emp.department_id if emp else None

    return CurrentUser(
        id=user.id, username=user.username, role_code=role.code,
        data_scope=role.data_scope, permissions=perms,
        employee_id=user.employee_id, department_id=department_id,
    )


def require_permission(code: str):
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in user.permissions:
            raise forbidden()
        return user
    return _dep


def data_scope_descriptor(user: CurrentUser) -> dict:
    if user.data_scope == "all":
        return {"scope": "all"}
    if user.data_scope == "self":
        return {"scope": "self", "employee_id": user.employee_id}
    return {"scope": "dept", "department_id": user.department_id}
