from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.models import DataDict
from app.schemas.common import PageParams


def list_by_type(db: Session, dict_type: str) -> list[DataDict]:
    stmt = (select(DataDict)
            .where(DataDict.dict_type == dict_type, DataDict.status == 1)
            .order_by(DataDict.sort_order.asc()))
    return list(db.execute(stmt).scalars().all())


def paginate(db: Session, *, params: PageParams,
             dict_type: str | None = None) -> tuple[list[DataDict], int]:
    base = select(DataDict)
    if dict_type:
        base = base.where(DataDict.dict_type == dict_type)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(DataDict.dict_key.like(kw), DataDict.dict_label.like(kw)))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = (base.order_by(DataDict.dict_type.asc(), DataDict.sort_order.asc())
            .offset((params.page - 1) * params.page_size).limit(params.page_size))
    return list(db.execute(stmt).scalars().all()), total


def get(db: Session, id_: str) -> DataDict | None:
    return db.get(DataDict, id_)


def get_by_type_key(db: Session, dict_type: str, dict_key: str) -> DataDict | None:
    stmt = select(DataDict).where(DataDict.dict_type == dict_type, DataDict.dict_key == dict_key)
    return db.execute(stmt).scalar_one_or_none()


def create(db: Session, **fields) -> DataDict:
    d = DataDict(**fields)
    db.add(d)
    return d


def delete(db: Session, d: DataDict) -> None:
    db.delete(d)
