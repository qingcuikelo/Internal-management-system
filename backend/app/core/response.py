from typing import Any

from app.core.context import get_trace_id


def envelope(data: Any = None, message: str = "ok", code: int = 0) -> dict:
    return {"code": code, "message": message, "data": data, "trace_id": get_trace_id()}
