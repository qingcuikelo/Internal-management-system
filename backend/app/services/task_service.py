import json
import warnings

from celery.result import AsyncResult

from app.core.celery_app import celery_app


def get_task_status(redis, task_id: str) -> dict | None:
    raw = redis.get(f"task:{task_id}")
    if raw:
        return json.loads(raw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = AsyncResult(task_id, app=celery_app)
        if result.state is None or result.state == "PENDING":
            return None
    return {"status": result.state.lower(), "result": result.result, "error": str(result.traceback) if result.traceback else None}
