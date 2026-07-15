from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.employee import (BatchDepartmentReq, EmployeeCreate,
                                  EmployeeUpdate, ResignReq)
from app.services import employee_service

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          department_id: str | None = None, status: int | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("employee:view"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=employee_service.list_employees(db, user, params, department_id, status))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("employee:view"))):
    return envelope(data=employee_service.get_one(db, user, id_))


@router.post("")
def create(body: EmployeeCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("employee:create"))):
    return envelope(data=employee_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: EmployeeUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("employee:update"))):
    return envelope(data=employee_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("employee:delete"))):
    employee_service.delete(db, user, id_, request)
    return envelope(message="已删除")


@router.post("/{id_}/resign")
def resign(id_: str, body: ResignReq, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("employee:resign"))):
    return envelope(data=employee_service.resign(db, user, id_, body.resign_date, request),
                    message="离职处理完成")


@router.patch("/batch-department")
def batch_department(body: BatchDepartmentReq, request: Request, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_permission("employee:update"))):
    return envelope(data=employee_service.batch_department(db, user, body, request))


@router.post("/import")
def import_employees(file: UploadFile = File(...),
                     user: CurrentUser = Depends(require_permission("employee:import"))):
    from app.services.import_export_service import submit_import
    task_id = submit_import(file, user)
    return JSONResponse(status_code=202, content=envelope(data={"task_id": task_id}))


@router.post("/export")
def export_employees(body: dict | None = None,
                     user: CurrentUser = Depends(require_permission("employee:export"))):
    from app.services.import_export_service import submit_export
    kw = body.get("keyword") if body else None
    did = body.get("department_id") if body else None
    st = body.get("status") if body else None
    task_id = submit_export(did, st, kw, user)
    return JSONResponse(status_code=202, content=envelope(data={"task_id": task_id}))
