from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import TraceIdMiddleware
from app.core.redis import get_redis
from app.core.response import envelope


def create_app() -> FastAPI:
    app = FastAPI(title="Internal Management System API")

    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health")
    def health():
        db_ok = "ok"
        redis_ok = "ok"
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_ok = "down"
        try:
            get_redis().ping()
        except Exception:
            redis_ok = "down"
        healthy = db_ok == "ok" and redis_ok == "ok"
        return envelope(data={"healthy": healthy, "db": db_ok, "redis": redis_ok})

    return app


app = create_app()
