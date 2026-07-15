import json
import os

from openpyxl import Workbook

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.core.celery_app import celery_app
from app.models import Department

_HEADERS = ["工号", "姓名", "性别", "部门", "职位", "直属上级",
            "手机", "邮箱", "入职日期", "离职日期", "状态"]


@celery_app.task(name="app.tasks.export_employees.run")
def run_export(department_id: str | None, status: int | None, keyword: str | None,
               user_id: str, task_id: str) -> None:
    db = SessionLocal()
    try:
        wb = Workbook()
        ws = wb.active
        ws.append(_HEADERS)
        from app.repositories import employee_repo
        from app.schemas.common import PageParams
        page = 1
        total = 0
        while True:
            params = PageParams(page=page, page_size=100, keyword=keyword)
            scope = {"mode": "all"}
            rows, t = employee_repo.paginate(db, params=params, department_id=department_id,
                                              status=status, scope=scope)
            if page == 1:
                total = t
            dept_ids = {r.department_id for r in rows if r.department_id}
            depts = {}
            if dept_ids:
                dept_rows = db.execute(select(Department).where(Department.id.in_(dept_ids))).scalars().all()
                depts = {d.id: d.name for d in dept_rows}
            for emp in rows:
                gender_map = {0: "未知", 1: "男", 2: "女"}
                ws.append([
                    emp.employee_no, emp.name,
                    gender_map.get(emp.gender, ""),
                    depts.get(emp.department_id, ""),
                    emp.position or "",
                    str(emp.direct_supervisor_id or ""),
                    emp.phone or "", emp.email or "",
                    str(emp.hire_date) if emp.hire_date else "",
                    str(emp.resign_date) if emp.resign_date else "",
                    "在职" if emp.status == 1 else "离职",
                ])
            if len(rows) < params.page_size:
                break
            page += 1
        os.makedirs(os.path.join(settings.exports_dir, "exports"), exist_ok=True)
        filepath = os.path.join(settings.exports_dir, "exports", f"{task_id}.xlsx")
        wb.save(filepath)
        redis_client.set(f"task:{task_id}",
                         json.dumps({
                             "status": "success",
                             "result": {
                                 "total": total,
                                 "download_url": f"/exports/{task_id}.xlsx",
                             },
                             "error": None,
                         }, ensure_ascii=False),
                         ex=3600)
    except Exception as e:
        redis_client.set(f"task:{task_id}",
                         json.dumps({"status": "failed", "result": None, "error": str(e)}, ensure_ascii=False),
                         ex=3600)
    finally:
        db.close()
