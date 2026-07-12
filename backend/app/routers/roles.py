from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.role import RoleCreate, RoleUpdate, PermissionAssignReq
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["roles"])
permissions_router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("")
def list_(db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.list_roles(db, user))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.get_one(db, user, id_))


@router.post("")
def create(body: RoleCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: RoleUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:role"))):
    role_service.delete(db, user, id_, request)
    return envelope(message="已删除")


@router.get("/{id_}/permissions")
def get_permissions(id_: str, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.get_permissions(db, user, id_))


@router.put("/{id_}/permissions")
def assign_permissions(id_: str, body: PermissionAssignReq, request: Request,
                       db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.assign_permissions(db, user, id_, body.codes, request))


@permissions_router.get("")
def all_permissions(db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.all_permissions(db, user))
