from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import set_trace_id
from app.utils.uuidv7 import uuid7


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid7()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
