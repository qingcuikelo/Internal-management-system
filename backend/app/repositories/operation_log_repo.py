from sqlalchemy.orm import Session

from app.models import OperationLog


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
