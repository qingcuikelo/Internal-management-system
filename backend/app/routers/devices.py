from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceCheckoutReq
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          type: str | None = None, status: int | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("device:view"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=device_service.list_(db, user, params, type, status))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("device:view"))):
    return envelope(data=device_service.get_one(db, user, id_))


@router.post("")
def create(body: DeviceCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: DeviceUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.update(db, user, id_, body, request))


@router.post("/{id_}/checkout")
def checkout(id_: str, body: DeviceCheckoutReq, request: Request, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.checkout(db, user, id_, body, request), message="领用成功")


@router.post("/{id_}/return")
def return_(id_: str, request: Request, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.return_(db, user, id_, request), message="已退还")


@router.post("/{id_}/repair")
def repair(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.repair(db, user, id_, request), message="已送修")


@router.post("/{id_}/scrap")
def scrap(id_: str, request: Request, db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.scrap(db, user, id_, request), message="已报废")


@router.get("/{id_}/history")
def history(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("device:view"))):
    return envelope(data=device_service.history(db, user, id_))
