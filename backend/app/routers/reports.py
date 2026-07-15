from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/employee-assets")
def employee_assets(employee_id: str, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_permission("report:view"))):
    return envelope(data=report_service.employee_assets(db, user, employee_id))


@router.get("/idle-assets")
def idle_assets(db: Session = Depends(get_db),
                user: CurrentUser = Depends(require_permission("report:view"))):
    return envelope(data=report_service.idle_assets(db, user))


@router.get("/device-by-department")
def device_by_department(department_id: str | None = None,
                          db: Session = Depends(get_db),
                          user: CurrentUser = Depends(require_permission("report:view"))):
    return envelope(data=report_service.device_by_department(db, user, department_id))


@router.get("/warranty-expiring")
def warranty_expiring(days: int = 30, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(require_permission("report:view"))):
    return envelope(data=report_service.warranty_expiring(db, user, days))
