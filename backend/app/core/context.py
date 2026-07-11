from contextvars import ContextVar

trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return trace_id_ctx.get()


def set_trace_id(value: str) -> None:
    trace_id_ctx.set(value)
