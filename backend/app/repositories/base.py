from sqlalchemy.orm import Session


def get_by_id(db: Session, model, id_: str):
    return db.get(model, id_)


def get_active(db: Session, model, id_: str):
    obj = db.get(model, id_)
    if obj is None:
        return None
    if hasattr(obj, "deleted_at") and obj.deleted_at is not None:
        return None
    return obj
