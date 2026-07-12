from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.services import log_service

router = APIRouter(prefix="/operation-logs", tags=["operation-logs"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, user_id: str | None = None,
          module: str | None = None, action: str | None = None,
          start: str | None = None, end: str | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:log"))):
    params = PageParams(page=page, page_size=page_size)
    return envelope(data=log_service.list_logs(db, user, params, user_id=user_id,
                                               module=module, action=action, start=start, end=end))
