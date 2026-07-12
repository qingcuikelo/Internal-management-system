from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models import OperationLog
from app.repositories import operation_log_repo
from app.schemas.common import PageParams, paginate


def _to_out(log: OperationLog, username: str | None) -> dict:
    return {"id": log.id, "user_id": log.user_id, "username": username,
            "module": log.module, "action": log.action,
            "target_type": log.target_type, "target_id": log.target_id,
            "detail": log.detail, "ip": log.ip, "created_at": log.created_at}


def list_logs(db: Session, user: CurrentUser, params: PageParams, *,
              user_id: str | None, module: str | None, action: str | None,
              start: str | None, end: str | None) -> dict:
    rows, total = operation_log_repo.paginate(
        db, params=params, user_id=user_id, module=module, action=action, start=start, end=end)
    return paginate([_to_out(log, name) for log, name in rows], total, params)
