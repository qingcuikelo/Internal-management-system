from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.redis import get_redis
from app.core.response import envelope
from app.core.security import decode_token
from app.schemas.auth import LoginRequest, RefreshRequest, ChangePasswordRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db), redis=Depends(get_redis)):
    data = auth_service.login(
        db, redis, body.username, body.password,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return envelope(data=data)


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db), redis=Depends(get_redis)):
    return envelope(data=auth_service.refresh(db, redis, body.refresh_token))


@router.post("/logout")
def logout(request: Request, redis=Depends(get_redis), user: CurrentUser = Depends(get_current_user)):
    token = request.headers["Authorization"][len("Bearer "):]
    auth_service.logout(redis, decode_token(token))
    return envelope(message="已登出")


@router.get("/me")
def me(request: Request, user: CurrentUser = Depends(get_current_user)):
    return envelope(data={
        "id": user.id, "username": user.username, "role": user.role_code,
        "employee_id": user.employee_id, "permissions": sorted(user.permissions),
    })


@router.put("/password")
def change_password(body: ChangePasswordRequest, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    auth_service.change_password(db, user.id, body.old_password, body.new_password)
    return envelope(message="密码修改成功")
