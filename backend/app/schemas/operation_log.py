from datetime import datetime

from pydantic import BaseModel


class OperationLogOut(BaseModel):
    id: str
    user_id: str
    username: str | None = None
    module: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    detail: dict | None = None
    ip: str | None = None
    created_at: datetime | None = None
