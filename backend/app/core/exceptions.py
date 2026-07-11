from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import envelope


class BizError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def unauthorized(message: str = "未登录或登录已失效") -> BizError:
    return BizError(1001, message, 401)


def account_locked(message: str = "账号已锁定，请稍后再试") -> BizError:
    return BizError(1002, message, 423)


def forbidden(message: str = "无权访问该资源") -> BizError:
    return BizError(1003, message, 403)


def validation(message: str = "参数校验失败") -> BizError:
    return BizError(2001, message, 422)


def biz(code: int, message: str, http_status: int = 409) -> BizError:
    return BizError(code, message, http_status)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz(_: Request, exc: BizError):
        return JSONResponse(
            status_code=exc.http_status,
            content=envelope(data=None, message=exc.message, code=exc.code),
        )

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
        return JSONResponse(status_code=422, content=envelope(data=None, message=msg, code=2001))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=envelope(data=None, message="服务器内部错误", code=5000),
        )
