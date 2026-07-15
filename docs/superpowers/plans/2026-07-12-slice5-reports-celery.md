# Slice 5: Reports + Celery Async Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Celery async task infrastructure, 4 report endpoints with data-scope filtering, employee Excel import/export, task-status polling, file download, and a Celery Beat warranty-expiry scan.

**Architecture:** Celery with Redis broker+backend (DB1, separate from app Redis DB0). Reports are synchronous read-only queries with dept_manager row-level filtering. Import/export tasks run via Celery (default `always_eager=True` for dev/test synchronicity). Task status stored in Redis `task:{id}` + Celery AsyncResult backend. Exported files served via a guarded `/exports/{filename}` endpoint.

**Tech Stack:** Celery 5.x, redis-py (broker+backend), openpyxl 3.x, FastAPI, SQLAlchemy 2.0, MySQL 8, pytest.

## Global Constraints

- Python 3.11; run everything from `backend/` in the project venv. deps: `celery>=5.3,<6.0`, `openpyxl>=3.1`.
- All new endpoints under `/api/v1`. Responses use `envelope()`. Error codes reuse existing (1003, 3404, 3002, 3005); no new codes added.
- All `/reports/*` endpoints gated by `require_permission("report:view")`. Employee import/export gated by `employee:import`/`employee:export` (hr_admin and super_admin have these per seed). `/tasks/{id}` and `/exports/{filename}` login-only (`get_current_user`).
- dept_manager report data-scope: filter by employees in their department subtree. idle assets (NULL holder) invisible to dept_manager → idle-assets report returns null + note.
- Celery default `always_eager=True` for dev/test (tasks run synchronously, no worker needed). Tests verify task logic via eager execution.
- Excel import: individual row failures don't roll back other rows (row-by-row independent commits).
- `GET /exports/{filename}`: validate filename `^[\w\-]+\.xlsx$`, no path traversal.
- `GET /tasks/{task_id}`: check Redis `task:{id}` first (TTL 3600s), then Celery AsyncResult fallback.
- Do not modify DB tables/migrations. No new tables.
- ruff clean, 0 warnings, full suite green.

---

### Task 1: Celery Bootstrap + Dependencies + Config

**Files:**
- Modify: `backend/pyproject.toml` (add celery, openpyxl deps)
- Modify: `backend/app/core/config.py` (add 4 new fields)
- Create: `backend/app/core/celery_app.py`
- Create: `backend/app/tasks/__init__.py`
- Modify: `backend/.env.example` (add new optional vars)
- Test: `backend/tests/test_celery_config.py` (config smoke)
- Add to gitignore: `backend/uploads/`

**Interfaces:**
- Produces: `celery_app` instance, Beat schedule skeleton, `settings.{celery_broker_db, celery_task_always_eager, warranty_expiry_days, exports_dir}`.

- [ ] **Step 1: Add deps to pyproject.toml**

Modify `backend/pyproject.toml` — in the `dependencies` list, after `"python-multipart>=0.0.9"`, add:

```python
    "celery>=5.3,<6.0",
    "openpyxl>=3.1",
```

- [ ] **Step 2: Add config fields**

Modify `backend/app/core/config.py` — after `login_lock_minutes` add:

```python
    celery_broker_db: int = 1
    celery_task_always_eager: bool = True
    warranty_expiry_days: int = 30
    exports_dir: str = "uploads"
```

Also add a `celery_broker_url` and `celery_backend_url` property (or construct inline in celery_app). Actually, just construct them in `celery_app.py` from existing redis_host/redis_port — no new properties needed.

- [ ] **Step 3: Create Celery app**

Create `backend/app/core/celery_app.py`:

```python
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

_broker = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.celery_broker_db}"

celery_app = Celery("ims", broker=_broker, backend=_broker)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_always_eager=settings.celery_task_always_eager,
)

celery_app.conf.beat_schedule = {
    "scan-warranty-expiry": {
        "task": "app.tasks.warranty_scan.scan_warranty_expiry",
        "schedule": crontab(hour=9, minute=7),
    },
}
```

- [ ] **Step 4: Create tasks __init__**

Create `backend/app/tasks/__init__.py`:

```python
from app.core.celery_app import celery_app
```

- [ ] **Step 5: Install deps**

Run: `cd backend && .venv/Scripts/pip install celery openpyxl`

- [ ] **Step 6: Add uploads to gitignore**

Append to repo-root `.gitignore`:
```
backend/uploads/
```

- [ ] **Step 7: Config smoke test**

Create `backend/tests/test_celery_config.py`:

```python
from app.core.config import Settings


def test_celery_config_defaults():
    s = Settings()
    assert s.celery_broker_db == 1
    assert s.celery_task_always_eager is True
    assert s.warranty_expiry_days == 30
    assert s.exports_dir == "uploads"


def test_celery_app_created():
    from app.core.celery_app import celery_app
    assert celery_app.conf.task_always_eager is True
    assert len(celery_app.conf.beat_schedule) == 1
```

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_celery_config.py -q`
Expected: 2 passing.

- [ ] **Step 8: Commit**

```bash
cd backend && git add pyproject.toml app/core/config.py app/core/celery_app.py app/tasks/__init__.py tests/test_celery_config.py && cd .. && git add .gitignore && git commit -m "feat(reports): Celery bootstrap — broker, app, beat schedule skeleton, config, deps"
```

---

### Task 2: Task Polling + File Download Endpoints

**Files:**
- Create: `backend/app/services/task_service.py`
- Create: `backend/app/routers/tasks.py`
- Modify: `backend/app/api/v1.py` (mount tasks router)
- Test: `backend/tests/test_task_service.py`

**Interfaces:**
- Produces: `task_service.get_task_status(redis_celery, task_id) -> dict | None`, router `GET /tasks/{task_id}` and `GET /exports/{filename}`.
- Consumes: `get_redis` (app Redis DB0 for `task:{id}` key), `celery_app.AsyncResult` for Celery backend.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_task_service.py`:

```python
import pytest
import json

from app.models import Role, User
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db)
    db.flush()
    return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _make_user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_task_not_found(client, seeded, redis_conn):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.get("/api/v1/tasks/no-such-task", headers=_h(tok))
    assert r.json()["code"] == 3404


def test_task_from_redis_hit(client, seeded, redis_conn):
    redis_conn.set("task:test-123", json.dumps({"status": "success", "result": {"ok": True}, "error": None}), ex=3600)
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.get("/api/v1/tasks/test-123", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["status"] == "success"
    assert r["data"]["result"] == {"ok": True}


def test_exports_download_requires_login(client, seeded):
    r = client.get("/api/v1/exports/test.xlsx")
    assert r.json()["code"] == 1001


def test_exports_download(client, seeded):
    import os
    os.makedirs("uploads/exports", exist_ok=True)
    with open("uploads/exports/test.xlsx", "wb") as f:
        f.write(b"fake")
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.get("/api/v1/exports/test.xlsx", headers=_h(tok))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_exports_rejects_path_traversal(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.get("/api/v1/exports/../etc/passwd", headers=_h(tok))
    assert r.json()["code"] == 3404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_task_service.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Create task_service**

Create `backend/app/services/task_service.py`:

```python
import json

from celery.result import AsyncResult

from app.core.celery_app import celery_app


def get_task_status(redis, task_id: str) -> dict | None:
    raw = redis.get(f"task:{task_id}")
    if raw:
        return json.loads(raw)
    result = AsyncResult(task_id, app=celery_app)
    if result.state is None or result.state == "PENDING":
        return None
    return {"status": result.state.lower(), "result": result.result, "error": str(result.traceback) if result.traceback else None}
```

- [ ] **Step 4: Create tasks router**

Create `backend/app/routers/tasks.py`:

```python
import os
import re

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.exceptions import not_found
from app.core.redis import get_redis
from app.core.response import envelope
from app.services import task_service

router = APIRouter(tags=["tasks"])

_FILENAME_RE = re.compile(r"^[\w\-]+\.xlsx$")


@router.get("/tasks/{task_id}")
def get_task(task_id: str, redis=Depends(get_redis),
             user: CurrentUser = Depends(get_current_user)):
    data = task_service.get_task_status(redis, task_id)
    if data is None:
        raise not_found("任务不存在或已过期")
    return envelope(data=data)


@router.get("/exports/{filename}")
def download_export(filename: str, user: CurrentUser = Depends(get_current_user)):
    if not _FILENAME_RE.match(filename):
        raise not_found("文件不存在")
    filepath = os.path.join(settings.exports_dir, "exports", filename)
    if not os.path.isfile(filepath):
        raise not_found("文件不存在")
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )
```

- [ ] **Step 5: Mount in v1.py**

In `backend/app/api/v1.py`, add:
```python
from app.routers.tasks import router as tasks_router
# ...
api_router.include_router(tasks_router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_task_service.py -q`
Expected: 5 passing.

- [ ] **Step 7: Create uploads dirs**

```bash
mkdir -p backend/uploads/imports backend/uploads/exports
```

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/services/task_service.py app/routers/tasks.py app/api/v1.py tests/test_task_service.py uploads/imports/.gitkeep uploads/exports/.gitkeep && git commit -m "feat(reports): task status polling + export file download endpoints"
```

---

### Task 3: Report Endpoints (4) with Data-Scope

**Files:**
- Create: `backend/app/services/report_service.py`
- Create: `backend/app/routers/reports.py`
- Create: `backend/app/schemas/report.py`
- Modify: `backend/app/api/v1.py` (mount reports router)
- Test: `backend/tests/test_reports.py`

**Interfaces:**
- Produces: `report_service.{employee_assets, idle_assets, device_by_department, warranty_expiring}`
- Consumes: `scope_service.report_scope(db, user)` (or inline logic using `accessible_department_ids`), `device_repo`, `workstation_repo`, `employee_repo`.

- [ ] **Step 1: Write tests**

Create `backend/tests/test_reports.py`:

```python
import pytest
from datetime import date, timedelta

from app.models import Role, Employee, User, Department, Workstation, Device
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db)
    db.flush()
    return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _make_user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_employee_assets_as_super(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    emp = Employee(employee_no="E1", name="x", gender=1, department_id=dept.id, status=1)
    seeded.add(emp)
    ws = Workstation(code="W1", type="fixed", status=2, current_employee_id=emp.id)
    d1 = Device(asset_code="D1", type="laptop", status=2, current_employee_id=emp.id, warranty_expire=date.today() + timedelta(days=60))
    seeded.add_all([ws, d1])
    seeded.flush()
    r = client.get(f"/api/v1/reports/employee-assets?employee_id={emp.id}", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["workstation"] is not None
    assert len(r["data"]["devices"]) >= 1


def test_employee_assets_out_of_scope_for_dept_manager(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    boss = _login(client, "boss")
    dept_a = Department(name="A", status=1)
    dept_b = Department(name="B", status=1)
    seeded.add_all([dept_a, dept_b])
    seeded.flush()
    emp_a = Employee(employee_no="E1", name="a", gender=1, department_id=dept_a.id, status=1)
    emp_b = Employee(employee_no="E2", name="b", gender=1, department_id=dept_b.id, status=1)
    seeded.add_all([emp_a, emp_b])
    seeded.flush()
    mgr = _make_user(seeded, "mgr", "dept_manager", employee_id=emp_a.id)
    tok = _login(client, "mgr")
    # dept_manager in dept A queries employee in dept B -> 3404
    r = client.get(f"/api/v1/reports/employee-assets?employee_id={emp_b.id}", headers=_h(tok)).json()
    assert r["code"] == 3404


def test_idle_assets_as_global(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    seeded.add_all([
        Workstation(code="W1", type="fixed", status=1),
        Device(asset_code="D1", type="laptop", status=1, warranty_expire=date.today() + timedelta(days=30)),
    ])
    seeded.flush()
    r = client.get("/api/v1/reports/idle-assets", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["idle_workstations"] >= 1
    assert r["data"]["idle_devices"] >= 1


def test_idle_assets_dept_manager_gets_null(client, seeded):
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    emp = Employee(employee_no="E1", name="x", gender=1, department_id=dept.id, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "mgr", "dept_manager", employee_id=emp.id)
    tok = _login(client, "mgr")
    seeded.add_all([
        Workstation(code="W1", type="fixed", status=1),
        Device(asset_code="D1", type="laptop", status=1, warranty_expire=date.today() + timedelta(days=30)),
    ])
    seeded.flush()
    r = client.get("/api/v1/reports/idle-assets", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["idle_workstations"] is None


def test_device_by_department(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    emp = Employee(employee_no="E1", name="x", gender=1, department_id=dept.id, status=1)
    seeded.add(emp)
    seeded.flush()
    d = Device(asset_code="D1", type="laptop", status=2, current_employee_id=emp.id, warranty_expire=date.today() + timedelta(days=30))
    seeded.add(d)
    seeded.flush()
    r = client.get("/api/v1/reports/device-by-department", headers=_h(tok)).json()
    assert r["code"] == 0
    assert any(item["department_id"] == dept.id and item["count"] >= 1 for item in r["data"]["items"])


def test_warranty_expiring(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    d = Device(asset_code="D1", type="laptop", status=2, warranty_expire=date.today() + timedelta(days=10))
    seeded.add(d)
    seeded.flush()
    r = client.get("/api/v1/reports/warranty-expiring?days=30", headers=_h(tok)).json()
    assert r["code"] == 0
    assert len(r["data"]["items"]) >= 1


def test_non_holder_forbidden(client, seeded):
    emp = Employee(employee_no="E1", name="x", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    # employee role has no report:view
    r = client.get("/api/v1/reports/idle-assets", headers=_h(tok)).json()
    assert r["code"] == 1003
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_reports.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add report_scope to scope_service**

Append to `backend/app/services/scope_service.py`:

```python
def report_scope(db: Session, user: CurrentUser) -> dict:
    return employee_scope(db, user)
```

(Reports reuse the same data-scope logic as employee queries — `employee_scope` already returns `{"mode":"all"}`, `{"mode":"self","employee_id":...}`, or `{"mode":"dept","dept_ids":set}`. The employee role has no `report:view` so they won't reach this; only super/hr/it/dept_manager can. For dept_manager, `dept_ids` is the accessible department subtree.)

- [ ] **Step 4: Create report_service**

Create `backend/app/services/report_service.py`:

```python
from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import not_found
from app.models import Employee, Department, Workstation, Device
from app.repositories import employee_repo, device_repo, workstation_repo
from app.services import scope_service


def _dept_filtered_employee_ids(db: Session, user: CurrentUser) -> set[str] | None:
    scope = scope_service.report_scope(db, user)
    if scope["mode"] == "all":
        return None  # no filter
    if scope["mode"] == "self":
        eid = scope.get("employee_id")
        return {eid} if eid else set()
    return scope.get("dept_ids", set())


def employee_assets(db: Session, user: CurrentUser, employee_id: str) -> dict:
    # scope check: dept_manager can only see own-dept employees
    allowed = _dept_filtered_employee_ids(db, user)
    if allowed is not None:
        emp = employee_repo.get_active(db, employee_id)
        if emp is None or emp.department_id not in allowed:
            raise not_found("员工不存在")
    ws = db.execute(
        select(Workstation).where(
            Workstation.current_employee_id == employee_id,
            Workstation.status == 2,
            Workstation.deleted_at.is_(None),
        )
    ).scalars().first()
    devices = db.execute(
        select(Device).where(
            Device.current_employee_id == employee_id,
            Device.status == 2,
            Device.deleted_at.is_(None),
        )
    ).scalars().all()
    return {
        "workstation": {"id": ws.id, "code": ws.code, "location": ws.location} if ws else None,
        "devices": [{"id": d.id, "asset_code": d.asset_code, "type": d.type, "brand": d.brand, "model": d.model} for d in devices],
    }


def idle_assets(db: Session, user: CurrentUser) -> dict:
    scope = scope_service.report_scope(db, user)
    if scope["mode"] == "dept":
        return {"idle_workstations": None, "idle_devices": None,
                "note": "闲置资产归属全局管理，本角色不可见"}
    ws_count = db.execute(
        select(func.count()).select_from(Workstation).where(
            Workstation.status == 1, Workstation.deleted_at.is_(None)
        )
    ).scalar_one()
    d_count = db.execute(
        select(func.count()).select_from(Device).where(
            Device.status == 1, Device.deleted_at.is_(None)
        )
    ).scalar_one()
    return {"idle_workstations": ws_count, "idle_devices": d_count}


def device_by_department(db: Session, user: CurrentUser,
                          department_id: str | None = None) -> dict:
    allowed = _dept_filtered_employee_ids(db, user)
    # devices with a holder in visible scope
    base = (select(Employee.department_id, func.count(Device.id).label("cnt"))
            .select_from(Device)
            .join(Employee, Employee.id == Device.current_employee_id)
            .where(Device.status == 2, Device.deleted_at.is_(None),
                   Employee.deleted_at.is_(None), Employee.status == 1))
    if allowed is not None:
        base = base.where(Employee.department_id.in_(allowed))
    if department_id:
        base = base.where(Employee.department_id == department_id)
    base = base.group_by(Employee.department_id)
    rows = db.execute(base).all()
    dept_names = {}
    if rows:
        ids = [r[0] for r in rows]
        depts = db.execute(select(Department).where(Department.id.in_(ids))).scalars().all()
        dept_names = {d.id: d.name for d in depts}
    items = [{"department_id": r[0], "department_name": dept_names.get(r[0], ""), "count": r[1]}
             for r in rows]
    return {"items": items}


def warranty_expiring(db: Session, user: CurrentUser, days: int = 30) -> dict:
    today = date.today()
    cutoff = today + timedelta(days=days)
    allowed = _dept_filtered_employee_ids(db, user)
    base = (select(Device)
            .where(Device.warranty_expire.between(today, cutoff),
                   Device.status != 4,
                   Device.deleted_at.is_(None))
            .order_by(Device.warranty_expire.asc()))
    devices = db.execute(base).scalars().all()
    if allowed is not None:
        devices = [d for d in devices if d.current_employee_id is not None
                   and employee_repo.get_active(db, d.current_employee_id) is not None
                   and employee_repo.get_active(db, d.current_employee_id).department_id in allowed]
    return {"items": [{"id": d.id, "asset_code": d.asset_code, "type": d.type,
                        "brand": d.brand, "model": d.model,
                        "current_employee_id": d.current_employee_id,
                        "warranty_expire": str(d.warranty_expire)}
                      for d in devices]}
```

- [ ] **Step 5: Create report schemas**

Create `backend/app/schemas/report.py`:

```python
# Report output shapes are plain dicts from the service; no Pydantic models needed.
# This file exists for future strongly-typed report responses.
```

(Reports return plain dicts, consistent with codebase convention. The file is a placeholder for possible future typed schemas.)

- [ ] **Step 6: Create reports router**

Create `backend/app/routers/reports.py`:

```python
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
```

- [ ] **Step 7: Mount in v1.py**

In `backend/app/api/v1.py`:
```python
from app.routers.reports import router as reports_router
# ...
api_router.include_router(reports_router)
```

- [ ] **Step 8: Run tests**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_reports.py -q`
Expected: 8 passing.

- [ ] **Step 9: Commit**

```bash
cd backend && git add app/services/scope_service.py app/services/report_service.py app/routers/reports.py app/schemas/report.py app/api/v1.py tests/test_reports.py && git commit -m "feat(reports): 4 report endpoints with dept_manager data-scope"
```

---

### Task 4: Employee Import/Export + Warranty Beat Scan

**Files:**
- Create: `backend/app/tasks/import_employees.py`
- Create: `backend/app/tasks/export_employees.py`
- Create: `backend/app/tasks/warranty_scan.py`
- Create: `backend/app/services/import_export_service.py` (upload/shared logic)
- Modify: `backend/app/routers/employees.py` (add import/export endpoints)
- Test: `backend/tests/test_import_export.py`, `backend/tests/test_warranty_scan.py`

**Interfaces:**
- Produces: Celery tasks `import_employees`, `export_employees`, `scan_warranty_expiry`. Router endpoints `POST /employees/import`, `POST /employees/export`.
- Consumes: `celery_app`, `redis_client` (for `task:{id}`), `employee_repo`, `department_repo`, `openpyxl`.

- [ ] **Step 1: Write import/export tests**

Create `backend/tests/test_import_export.py`:

```python
import io
import pytest
from datetime import date

from openpyxl import Workbook

from app.models import Role, Employee, User, Department
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db)
    db.flush()
    return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _make_user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _make_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def test_import_returns_task_id(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    xlsx = _make_xlsx([["employee_no", "name", "gender", "department_id", "status"],
                       ["IMP001", "测试", "1", dept.id, "1"]])
    r = client.post("/api/v1/employees/import", headers=_h(tok),
                    files={"file": ("test.xlsx", xlsx,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 202
    assert "task_id" in r.json()["data"]
    task_id = r.json()["data"]["task_id"]
    # With always_eager=True, the task runs synchronously and the result key is set
    import json
    from app.core.redis import redis_client
    raw = redis_client.get(f"task:{task_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["status"] == "success"
    assert data["result"]["success_count"] == 1


def test_import_non_super_forbidden(client, seeded):
    _make_user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    xlsx = _make_xlsx([["employee_no", "name", "gender"], ["X", "x", "1"]])
    r = client.post("/api/v1/employees/import", headers=_h(tok),
                    files={"file": ("test.xlsx", xlsx)})
    # hr_admin HAS employee:import
    assert r.status_code == 202


def test_import_employee_role_forbidden(client, seeded):
    from app.models import Employee as Emp
    emp = Emp(employee_no="E1", name="x", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    xlsx = _make_xlsx([["employee_no", "name", "gender"], ["X", "x", "1"]])
    r = client.post("/api/v1/employees/import", headers=_h(tok),
                    files={"file": ("test.xlsx", xlsx)})
    assert r.json()["code"] == 1003


def test_export_returns_task_id(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.post("/api/v1/employees/export", headers=_h(tok), json={})
    assert r.status_code == 202
    assert "task_id" in r.json()["data"]
    task_id = r.json()["data"]["task_id"]
    import json
    from app.core.redis import redis_client
    raw = redis_client.get(f"task:{task_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["status"] == "success"


def test_export_non_super_forbidden(client, seeded):
    from app.models import Employee as Emp
    emp = Emp(employee_no="E1", name="x", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    r = client.post("/api/v1/employees/export", headers=_h(tok), json={})
    assert r.json()["code"] == 1003
```

- [ ] **Step 2: Write warranty scan test**

Create `backend/tests/test_warranty_scan.py`:

```python
import pytest
from datetime import date, timedelta

from app.models import Device
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db)
    db.flush()
    return db


def test_scan_warranty_expiry_finds_expiring(db, seeded):
    # add a device expiring in 10 days
    d = Device(asset_code="SCAN1", type="laptop", status=2, warranty_expire=date.today() + timedelta(days=10))
    db.add(d)
    db.flush()
    from app.tasks.warranty_scan import scan_warranty_expiry
    result = scan_warranty_expiry(days=30)
    assert result["count"] >= 1
    assert any(item["asset_code"] == "SCAN1" for item in result["items"])


def test_scan_warranty_skips_scrapped(db, seeded):
    d = Device(asset_code="SCRAP", type="laptop", status=4, warranty_expire=date.today() + timedelta(days=5))
    db.add(d)
    db.flush()
    from app.tasks.warranty_scan import scan_warranty_expiry
    result = scan_warranty_expiry(days=30)
    codes = {item["asset_code"] for item in result["items"]}
    assert "SCRAP" not in codes


def test_scan_warranty_skips_expired(db, seeded):
    d = Device(asset_code="OLD", type="laptop", status=2, warranty_expire=date.today() - timedelta(days=10))
    db.add(d)
    db.flush()
    from app.tasks.warranty_scan import scan_warranty_expiry
    result = scan_warranty_expiry(days=30)
    codes = {item["asset_code"] for item in result["items"]}
    assert "OLD" not in codes
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_import_export.py tests/test_warranty_scan.py -q`
Expected: FAIL.

- [ ] **Step 4: Create import task**

Create `backend/app/tasks/import_employees.py`:

```python
import json
import io

from openpyxl import load_workbook

from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.core.celery_app import celery_app
from app.models import Employee
from app.repositories import employee_repo, department_repo, operation_log_repo

_FIELDS = ["employee_no", "name", "gender", "department_id", "position",
           "direct_supervisor_id", "phone", "email", "entry_date", "status"]


@celery_app.task(name="app.tasks.import_employees.run")
def run_import(file_data: bytes, user_id: str, task_id: str) -> None:
    wb = load_workbook(io.BytesIO(file_data), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        _save(task_id, "failed", None, "Excel 文件为空")
        return
    headers = [str(h).strip() if h else "" for h in rows[0]]
    idx = {h: i for i, h in enumerate(headers)}
    errors: list[dict] = []
    success = 0
    db = SessionLocal()
    try:
        for i, row in enumerate(rows[1:], start=2):
            vals = {}
            for f in _FIELDS:
                if f in idx and idx[f] < len(row):
                    vals[f] = row[idx[f]]
            err = _validate_row(vals, i, db)
            if err:
                errors.append(err)
                continue
            _create_employee(vals, db)
            success += 1
        operation_log_repo.create(db, user_id=user_id, module="employee", action="import",
                                  target_type="employee", target_id=None,
                                  detail={"success": success, "fail": len(errors), "errors": errors})
        db.commit()
        _save(task_id, "success", {"success_count": success, "error_count": len(errors), "errors": errors}, None)
    except Exception as e:
        db.rollback()
        _save(task_id, "failed", None, str(e))
    finally:
        db.close()


def _validate_row(vals: dict, row_num: int, db) -> dict | None:
    if not vals.get("employee_no") or not vals.get("name"):
        return {"row": row_num, "error": "工号和姓名为必填"}
    eno = str(vals["employee_no"]).strip()
    if employee_repo.get_by_employee_no(db, eno) is not None:
        return {"row": row_num, "error": f"工号 {eno} 已存在"}
    try:
        gender = int(vals.get("gender", 1))
        if gender not in (0, 1, 2):
            return {"row": row_num, "error": "性别必须为 0/1/2"}
    except (ValueError, TypeError):
        return {"row": row_num, "error": "性别格式错误"}
    dept_id = vals.get("department_id")
    if dept_id:
        from app.repositories import department_repo
        if department_repo.get_active(db, str(dept_id)) is None:
            return {"row": row_num, "error": f"部门 {dept_id} 不存在"}
    sup_id = vals.get("direct_supervisor_id")
    if sup_id:
        try:
            sup = employee_repo.get_active(db, str(sup_id))
            if sup is None:
                return {"row": row_num, "error": f"上级 {sup_id} 不存在"}
        except Exception:
            return {"row": row_num, "error": f"上级 {sup_id} 不存在"}
    return None


def _create_employee(vals: dict, db) -> None:
    fields = {"employee_no": str(vals["employee_no"]).strip(),
              "name": str(vals["name"]).strip(),
              "gender": int(vals.get("gender", 1)),
              "status": int(vals.get("status", 1))}
    for f in ["department_id", "position", "direct_supervisor_id", "phone", "email"]:
        v = vals.get(f)
        if v is not None and str(v).strip() != "":
            fields[f] = str(v).strip()
    entry = vals.get("entry_date")
    if entry:
        try:
            from datetime import datetime
            if isinstance(entry, datetime):
                fields["hire_date"] = entry.date()
            elif isinstance(entry, str):
                fields["hire_date"] = datetime.strptime(entry, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    employee_repo.create(db, **fields)


def _save(task_id: str, status: str, result, error: str | None) -> None:
    redis_client.set(f"task:{task_id}",
                     json.dumps({"status": status, "result": result, "error": error}, ensure_ascii=False),
                     ex=3600)
```

- [ ] **Step 5: Create export task**

Create `backend/app/tasks/export_employees.py`:

```python
import json
import os

from openpyxl import Workbook

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.core.celery_app import celery_app

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
        from app.repositories import employee_repo, department_repo
        from app.schemas.common import PageParams
        page = 1
        total = 0
        while True:
            params = PageParams(page=page, page_size=100)
            scope = {"mode": "all"}
            rows, t = employee_repo.paginate(db, params=params, department_id=department_id,
                                              status=status, scope=scope)
            if page == 1:
                total = t
            dept_ids = {r.department_id for r in rows if r.department_id}
            depts = {}
            if dept_ids:
                from app.models import Department
                from sqlalchemy import select
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
```

- [ ] **Step 6: Create warranty scan task**

Create `backend/app/tasks/warranty_scan.py`:

```python
import json
from datetime import date, timedelta

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.models import Device
from sqlalchemy import select


@celery_app.task(name="app.tasks.warranty_scan.scan_warranty_expiry")
def scan_warranty_expiry(days: int | None = None) -> dict:
    days = days or settings.warranty_expiry_days
    today = date.today()
    cutoff = today + timedelta(days=days)
    db = SessionLocal()
    try:
        devices = db.execute(
            select(Device).where(
                Device.warranty_expire.between(today, cutoff),
                Device.status != 4,
                Device.deleted_at.is_(None),
            ).order_by(Device.warranty_expire.asc())
        ).scalars().all()
        items = [{"id": d.id, "asset_code": d.asset_code, "type": d.type,
                  "brand": d.brand, "model": d.model,
                  "warranty_expire": str(d.warranty_expire),
                  "current_employee_id": d.current_employee_id}
                 for d in devices]
        result = {"count": len(items), "items": items, "scan_date": str(today)}
        redis_client.set(f"warranty_expiring:{days}", json.dumps(result, ensure_ascii=False), ex=86400)
        return result
    finally:
        db.close()
```

- [ ] **Step 7: Create import_export_service (upload handling)**

Create `backend/app/services/import_export_service.py`:

```python
import os
import uuid

from fastapi import UploadFile

from app.core.config import settings
from app.core.redis import redis_client
from app.core.deps import CurrentUser


def submit_import(file: UploadFile, user: CurrentUser) -> str:
    task_id = uuid.uuid4().hex
    file_data = file.file.read()
    # Save a copy for inspection (optional)
    os.makedirs(os.path.join(settings.exports_dir, "imports"), exist_ok=True)
    filepath = os.path.join(settings.exports_dir, "imports", f"{task_id}.xlsx")
    with open(filepath, "wb") as f:
        f.write(file_data)
    from app.tasks.import_employees import run_import
    run_import.delay(file_data, user.id, task_id)
    return task_id


def submit_export(department_id: str | None, status: int | None, keyword: str | None,
                  user: CurrentUser) -> str:
    task_id = uuid.uuid4().hex
    from app.tasks.export_employees import run_export
    run_export.delay(department_id, status, keyword, user.id, task_id)
    return task_id
```

- [ ] **Step 8: Add import/export router endpoints**

Append to `backend/app/routers/employees.py`:

```python
from fastapi import UploadFile, File

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
```

Also need to add import at top of employees.py:
```python
from fastapi.responses import JSONResponse
```

- [ ] **Step 9: Run tests**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest tests/test_import_export.py tests/test_warranty_scan.py -q`
Expected: all passing (8 import/export + 3 warranty = 11).

- [ ] **Step 10: Run full suite**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest -q`
Expected: all passing (127 prev + ~15 new ≈ 142).

- [ ] **Step 11: Ruff**

Run: `cd backend && .venv/Scripts/python -m ruff check app tests`

- [ ] **Step 12: Commit**

```bash
cd backend && git add app/tasks/ app/services/import_export_service.py app/routers/employees.py tests/test_import_export.py tests/test_warranty_scan.py && git commit -m "feat(reports): employee import/export async tasks + Celery beat warranty scan"
```

---

### Task 5: Integration + Full Suite + Ruff Sweep

**Files:**
- Verify: all router mounts in `v1.py`
- Possibly touch: import cleanup across new files
- Test: whole suite

- [ ] **Step 1: Verify router mounts**

Run: `cd backend && grep -n "include_router" app/api/v1.py`
Expected: auth, departments, employees, workstations, devices, users, roles, permissions, dicts, operation_logs, **tasks, reports** all present.

- [ ] **Step 2: Full suite**

Run: `cd backend && PATH="$PWD/.venv/Scripts:$PATH" .venv/Scripts/python -m pytest -q`

- [ ] **Step 3: Ruff**

Run: `cd backend && .venv/Scripts/python -m ruff check app tests`
If issues: `cd backend && .venv/Scripts/python -m ruff check --fix app tests` then re-run suite.

- [ ] **Step 4: Edge coverage check**

Add a focused test if any clear gap surfaces:
- dept_manager warranty-expiring sees only own-dept employees' devices.
- export creates a downloadable .xlsx file.

- [ ] **Step 5: Commit**

```bash
cd backend && git add -A && git commit -m "chore(reports): mount routers, ruff clean, full suite green for slice 5"
```

---

## Self-Review Notes (author)

- **Spec coverage:** Reports §8.6 (4 endpoints) → T3; async tasks + import/export → T4; /tasks/{id} + /exports → T2; Celery bootstrap → T1.
- **Dependency ordering:** T1 (infra) → T2/T3/T4 (parallel-capable, but executed sequentially for simplicity). T2 and T3 are independent; T4 depends on T1+T2.
- **Data-scope:** report_service._dept_filtered_employee_ids reuses scope_service, consistent with existing employee/asset scope patterns.
- **Import/export:** Always eager=True in tests means tasks execute synchronously and test assertions run right after the HTTP call. SessionLocal is used inside tasks (not request-scoped db session).
- **Warranty scan:** Redis key `warranty_expiring:{days}` set by beat task, TTL 24h; report endpoint does direct DB query (not reading this cache).
- **No new DB tables:** Task state persists in Redis; uploads to local filesystem.
