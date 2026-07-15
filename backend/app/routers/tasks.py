import os
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import not_found
from app.core.redis import get_redis
from app.core.response import envelope
from app.services import task_service

router = APIRouter(tags=["tasks"])

_FILENAME_RE = re.compile(r"^[\w\-]+\.xlsx$")


@router.get("/tasks/{task_id}")
def get_task(task_id: str, redis=Depends(get_redis),
             user: CurrentUser = Depends(get_current_user)):
    data = task_service.get_task_status(redis, task_id)
    if data is None:
        raise not_found("任务不存在或已过期")
    return envelope(data=data)


@router.get("/exports/{filename}")
def download_export(filename: str, user: CurrentUser = Depends(get_current_user)):
    if not _FILENAME_RE.match(filename):
        raise not_found("文件不存在")
    filepath = os.path.join(settings.exports_dir, "exports", filename)
    if not os.path.isfile(filepath):
        raise not_found("文件不存在")
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )
