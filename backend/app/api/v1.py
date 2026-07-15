from fastapi import APIRouter

from app.core.config import settings
from app.routers.auth import router as auth_router
from app.routers.departments import router as departments_router
from app.routers.employees import router as employees_router
from app.routers.workstations import router as workstations_router
from app.routers.devices import router as devices_router
from app.routers.users import router as users_router
from app.routers.roles import router as roles_router, permissions_router
from app.routers.dicts import router as dicts_router
from app.routers.operation_logs import router as operation_logs_router
from app.routers.tasks import router as tasks_router
from app.routers.reports import router as reports_router

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(auth_router)
api_router.include_router(departments_router)
api_router.include_router(employees_router)
api_router.include_router(workstations_router)
api_router.include_router(devices_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
api_router.include_router(dicts_router)
api_router.include_router(operation_logs_router)
api_router.include_router(tasks_router)
api_router.include_router(reports_router)
