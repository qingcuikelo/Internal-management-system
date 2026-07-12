from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import OperationLog, User
from app.schemas.common import PageParams


def _parse_bound(value: str, *, end: bool) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:  # date only 'YYYY-MM-DD'
            d = datetime.fromisoformat(value)
            return d + timedelta(days=1) if end else d
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def paginate(db, *, params: PageParams, user_id: str | None = None, module: str | None = None,
             action: str | None = None, start: str | None = None,
             end: str | None = None) -> tuple[list[tuple[OperationLog, str]], int]:
    base = (select(OperationLog, User.username)
            .join(User, User.id == OperationLog.user_id))
    if user_id:
        base = base.where(OperationLog.user_id == user_id)
    if module:
        base = base.where(OperationLog.module == module)
    if action:
        base = base.where(OperationLog.action == action)
    start_dt = _parse_bound(start, end=False) if start else None
    end_dt = _parse_bound(end, end=True) if end else None
    if start_dt is not None:
        base = base.where(OperationLog.created_at >= start_dt)
    if end_dt is not None:
        op = OperationLog.created_at < end_dt if (end and len(end) == 10) else OperationLog.created_at <= end_dt
        base = base.where(op)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()
    stmt = (base.order_by(OperationLog.created_at.desc())
            .offset((params.page - 1) * params.page_size).limit(params.page_size))
    rows = db.execute(stmt).all()
    return [(r[0], r[1]) for r in rows], total


def create(db: Session, *, user_id: str, module: str, action: str,
           target_type: str | None = None, target_id: str | None = None,
           detail: dict | None = None, ip: str | None = None,
           user_agent: str | None = None) -> OperationLog:
    log = OperationLog(
        user_id=user_id, module=module, action=action,
        target_type=target_type, target_id=target_id, detail=detail,
        ip=ip, user_agent=user_agent,
    )
    db.add(log)
    return log
