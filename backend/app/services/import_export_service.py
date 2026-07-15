import os
import uuid

from fastapi import UploadFile

from app.core.config import settings
from app.core.deps import CurrentUser


def submit_import(file: UploadFile, user: CurrentUser) -> str:
    task_id = uuid.uuid4().hex
    file_data = file.file.read()
    # Save a copy for inspection (optional)
    os.makedirs(os.path.join(settings.exports_dir, "imports"), exist_ok=True)
    filepath = os.path.join(settings.exports_dir, "imports", f"{task_id}.xlsx")
    with open(filepath, "wb") as f:
        f.write(file_data)
    from app.tasks.import_employees import run_import
    run_import.delay(file_data, user.id, task_id)
    return task_id


def submit_export(department_id: str | None, status: int | None, keyword: str | None,
                  user: CurrentUser) -> str:
    task_id = uuid.uuid4().hex
    from app.tasks.export_employees import run_export
    run_export.delay(department_id, status, keyword, user.id, task_id)
    return task_id
