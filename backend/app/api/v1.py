from fastapi import APIRouter

from app.core.config import settings

api_router = APIRouter(prefix=settings.api_prefix)

# Business routers are included here as slices land.
# Task 9 adds: from app.routers.auth import router as auth_router; api_router.include_router(auth_router)
