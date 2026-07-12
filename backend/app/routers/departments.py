from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("/tree")
def tree(db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission("department:view"))):
    return envelope(data=department_service.get_tree(db, user))


@router.get("")
def list_(db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission("department:view"))):
    return envelope(data={"items": department_service.list_departments(db, user)})


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("department:view"))):
    return envelope(data=department_service.get_one(db, user, id_))


@router.post("")
def create(body: DepartmentCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("department:create"))):
    return envelope(data=department_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: DepartmentUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("department:update"))):
    return envelope(data=department_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("department:delete"))):
    department_service.delete(db, user, id_, request)
    return envelope(message="已删除")
