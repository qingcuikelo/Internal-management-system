from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import unauthorized, account_locked, forbidden
from app.core.security import (
    verify_password, hash_password, create_access_token, create_refresh_token, decode_token,
)
from app.repositories import user_repo, role_repo, operation_log_repo


def _fail_key(username: str) -> str:
    return f"login_fail:{username}"


def _lock_key(username: str) -> str:
    return f"login_lock:{username}"


def _user_payload(db: Session, user) -> dict:
    role = role_repo.get_by_id(db, user.role_id)
    perms = sorted(role_repo.permission_codes_for_role(db, user.role_id))
    return {
        "id": user.id, "username": user.username,
        "role": role.code if role else None,
        "employee_id": user.employee_id, "permissions": perms,
    }


def login(db: Session, redis, username: str, password: str,
          ip: str | None = None, user_agent: str | None = None) -> dict:
    if redis.get(_lock_key(username)):
        raise account_locked()

    user = user_repo.get_active_by_username(db, username)
    if user is None or user.status != 1 or not verify_password(password, user.password_hash):
        fails = redis.incr(_fail_key(username))
        redis.expire(_fail_key(username), settings.login_lock_minutes * 60)
        if fails >= settings.login_max_fail:
            redis.setex(_lock_key(username), settings.login_lock_minutes * 60, "1")
        raise unauthorized("账号或密码错误")

    redis.delete(_fail_key(username))
    user_repo.update_last_login(db, user)
    operation_log_repo.create(db, user_id=user.id, module="auth", action="login",
                              ip=ip, user_agent=user_agent)
    db.commit()

    access, _, expires_in = create_access_token(user.id)
    refresh, _ = create_refresh_token(user.id)
    return {
        "access_token": access, "refresh_token": refresh, "token_type": "Bearer",
        "expires_in": expires_in, "user": _user_payload(db, user),
    }


def refresh(db: Session, redis, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise unauthorized()
    if redis.get(f"blacklist:{payload['jti']}"):
        raise unauthorized()
    user = user_repo.get_active_by_id(db, payload["sub"])
    if user is None or user.status != 1:
        raise unauthorized()
    access, _, expires_in = create_access_token(user.id)
    return {"access_token": access, "token_type": "Bearer", "expires_in": expires_in}


def logout(redis, access_payload: dict) -> None:
    ttl = access_payload["exp"] - int(datetime.now(timezone.utc).timestamp())
    if ttl > 0:
        redis.setex(f"blacklist:{access_payload['jti']}", ttl, "1")


def change_password(db: Session, user_id: str, old_password: str, new_password: str) -> None:
    user = user_repo.get_active_by_id(db, user_id)
    if user is None or not verify_password(old_password, user.password_hash):
        raise unauthorized("旧密码不正确")
    user_repo.set_password(db, user, hash_password(new_password))
    operation_log_repo.create(db, user_id=user.id, module="auth", action="change_password")
    db.commit()
