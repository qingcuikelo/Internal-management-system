from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.workstation import (
    WorkstationCreate, WorkstationUpdate, WorkstationAssignReq, WorkstationStatusReq, BatchReleaseReq,
)
from app.services import workstation_service

router = APIRouter(prefix="/workstations", tags=["workstations"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          type: str | None = None, status: int | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("workstation:view"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=workstation_service.list_(db, user, params, type, status))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("workstation:view"))):
    return envelope(data=workstation_service.get_one(db, user, id_))


@router.post("")
def create(body: WorkstationCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: WorkstationUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.update(db, user, id_, body, request))


@router.post("/{id_}/assign")
def assign(id_: str, body: WorkstationAssignReq, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.assign(db, user, id_, body, request), message="分配成功")


@router.post("/{id_}/release")
def release(id_: str, request: Request, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.release(db, user, id_, request), message="已释放")


@router.post("/batch-release")
def batch_release(body: BatchReleaseReq, request: Request, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.batch_release(db, user, body.workstation_ids, request))


@router.patch("/{id_}/status")
def set_status(id_: str, body: WorkstationStatusReq, request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.set_status(db, user, id_, body.status, request))


@router.get("/{id_}/history")
def history(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("workstation:view"))):
    return envelope(data=workstation_service.history(db, user, id_))
