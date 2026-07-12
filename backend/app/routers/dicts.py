from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_permission
from app.core.redis import get_redis
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.dict import DictCreate, DictUpdate
from app.services import dict_service

router = APIRouter(prefix="/dicts", tags=["dicts"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          dict_type: str | None = None, db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:dict"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=dict_service.list_dicts(db, user, params, dict_type))


@router.get("/{dict_type}")
def by_type(dict_type: str, db: Session = Depends(get_db),
            redis=Depends(get_redis), user: CurrentUser = Depends(get_current_user)):
    return envelope(data=dict_service.list_by_type(db, redis, dict_type))


@router.post("")
def create(body: DictCreate, request: Request, db: Session = Depends(get_db),
           redis=Depends(get_redis),
           user: CurrentUser = Depends(require_permission("system:dict"))):
    return envelope(data=dict_service.create(db, user, redis, body, request))


@router.put("/{id_}")
def update(id_: str, body: DictUpdate, request: Request, db: Session = Depends(get_db),
           redis=Depends(get_redis),
           user: CurrentUser = Depends(require_permission("system:dict"))):
    return envelope(data=dict_service.update(db, user, redis, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           redis=Depends(get_redis),
           user: CurrentUser = Depends(require_permission("system:dict"))):
    dict_service.delete(db, user, redis, id_, request)
    return envelope(message="已删除")
