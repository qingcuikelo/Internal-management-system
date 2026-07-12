from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.user import UserCreate, UserUpdate, UserStatusReq, ResetPasswordReq
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          status: int | None = None, role_code: str | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:user"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=user_service.list_users(db, user, params, status, role_code))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.get_one(db, user, id_))


@router.post("")
def create(body: UserCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: UserUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:user"))):
    user_service.delete(db, user, id_, request)
    return envelope(message="已删除")


@router.patch("/{id_}/status")
def set_status(id_: str, body: UserStatusReq, request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.set_status(db, user, id_, body.status, request))


@router.post("/{id_}/reset-password")
def reset_password(id_: str, body: ResetPasswordReq, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_permission("system:user"))):
    user_service.reset_password(db, user, id_, body.new_password, request)
    return envelope(message="密码已重置")
