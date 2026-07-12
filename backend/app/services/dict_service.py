from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found
from app.core import dict_cache
from app.models import DataDict
from app.repositories import data_dict_repo, operation_log_repo
from app.schemas.common import PageParams, paginate


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None


def _to_out(d: DataDict) -> dict:
    return {"id": d.id, "dict_type": d.dict_type, "dict_key": d.dict_key,
            "dict_label": d.dict_label, "sort_order": d.sort_order, "status": d.status}


def list_by_type(db: Session, redis, dict_type: str) -> dict:
    cached = dict_cache.get_cached(redis, dict_type)
    if cached is not None:
        return {"items": cached}
    rows = data_dict_repo.list_by_type(db, dict_type)
    items = [{"dict_key": r.dict_key, "dict_label": r.dict_label, "sort_order": r.sort_order}
             for r in rows]
    dict_cache.set_cached(redis, dict_type, items, settings.dict_cache_ttl)
    return {"items": items}


def list_dicts(db: Session, user: CurrentUser, params: PageParams, dict_type: str | None) -> dict:
    rows, total = data_dict_repo.paginate(db, params=params, dict_type=dict_type)
    return paginate([_to_out(r) for r in rows], total, params)


def create(db: Session, user: CurrentUser, redis, data, req: Request) -> dict:
    if data_dict_repo.get_by_type_key(db, data.dict_type, data.dict_key) is not None:
        raise biz(3005, "该分类下的键已存在")
    d = data_dict_repo.create(db, dict_type=data.dict_type, dict_key=data.dict_key,
                              dict_label=data.dict_label, sort_order=data.sort_order,
                              status=data.status)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="dict", action="create",
                              target_type="data_dict", target_id=d.id,
                              detail={"dict_type": d.dict_type, "dict_key": d.dict_key},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    dict_cache.invalidate(redis, d.dict_type)
    return _to_out(d)


def update(db: Session, user: CurrentUser, redis, id_: str, data, req: Request) -> dict:
    d = data_dict_repo.get(db, id_)
    if d is None:
        raise not_found("字典项不存在")
    fields = data.model_fields_set
    if "dict_label" in fields and data.dict_label is not None:
        d.dict_label = data.dict_label
    if "sort_order" in fields and data.sort_order is not None:
        d.sort_order = data.sort_order
    if "status" in fields and data.status is not None:
        d.status = data.status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="dict", action="update",
                              target_type="data_dict", target_id=d.id,
                              detail={"dict_type": d.dict_type, "dict_key": d.dict_key},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    dict_cache.invalidate(redis, d.dict_type)
    return _to_out(d)


def delete(db: Session, user: CurrentUser, redis, id_: str, req: Request) -> None:
    d = data_dict_repo.get(db, id_)
    if d is None:
        raise not_found("字典项不存在")
    dict_type = d.dict_type
    data_dict_repo.delete(db, d)
    operation_log_repo.create(db, user_id=user.id, module="dict", action="delete",
                              target_type="data_dict", target_id=id_,
                              detail={"dict_type": dict_type, "dict_key": d.dict_key},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    dict_cache.invalidate(redis, dict_type)
