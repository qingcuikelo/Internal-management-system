# 切片3（资产域 + 离职级联）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Workstation + device full lifecycle with transaction + optimistic-lock assign/checkout, asset data-scope (via current-employee), history tables, and the employee resign cascade — on top of merged slices 1-2.

**Architecture:** Same four layers. Optimistic locking = conditional `UPDATE ... WHERE status=<available> AND version=<expected>` returning rowcount; rowcount 0 → conflict (3001). Services own the transaction (main-table update + history write + log, single commit). Asset scope filters on `current_employee_id` (idle/in-stock assets have NULL → invisible to dept/self). No schema change (tables from slice 1).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, MySQL 8, Redis, Pydantic v2, pytest. venv at `backend/.venv`.

## Global Constraints

- Work in `backend/`; venv `backend/.venv`. MySQL 8 (`ims`/`ims_test`), Redis. No migration/schema changes.
- Unified envelope `{code,message,data,trace_id}`. Error codes: reuse 3002 (referenced entity missing), 3005 (unique conflict), 3404 (not_found/out-of-scope); NEW 3001 (conflict/occupied, HTTP 409), 3007 (invalid state transition, HTTP 409).
- Status constants (code, not dict): Workstation IDLE=1/OCCUPIED=2/RESERVED=3/DISABLED=4; Device IN_STOCK=1/IN_USE=2/REPAIR=3/SCRAPPED=4.
- Permissions per §3.2: workstation:view/manage (manage = super/hr/it), device:view/manage (view = super/it/dept/employee; **hr has NO device perms**; manage = super/it), employee:resign (super/hr). Every endpoint guarded by `require_permission`.
- Data-scope on VIEW: dept_manager sees assets whose `current_employee_id` ∈ own-subtree employees; employee sees `current_employee_id == self`; idle/in-stock (NULL) invisible to dept/self; global roles see all. Out-of-scope single-resource view → not_found (3404). Manage ops are all-scope roles (existence check only).
- Writes set created_by/updated_by + record operation_logs. Assign/release/checkout/return/resign are single-transaction (main + history + log, one commit).
- TDD; commit trailer `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`. ruff clean, 0 warnings.
- Tests hit `ims_test`; use slice-1 `db`/`client` fixtures and `seed_service.run_seed(db)` for roles.

Existing interfaces (verified): `deps.{CurrentUser,require_permission,get_current_user,data_scope_descriptor}`; `exceptions.{BizError,biz,not_found,forbidden}`; `response.envelope`; `schemas.common.{PageParams,paginate}`; `repositories.base.{get_by_id,get_active}`; `operation_log_repo.create(db,*,user_id,module,action,target_type,target_id,detail,ip,user_agent)`; `scope_service.{accessible_department_ids,employee_scope}`; `employee_repo.get_active`; `department_repo.get_active`; models `Workstation`, `Device`, `WorkstationAssignment`, `DeviceAssignment`, `Employee`, `User`; `api.v1.api_router`.

---

### Task 1: constants, error helpers, asset scope, employee ids-in-departments, asset schemas

**Files:**
- Create: `backend/app/core/constants.py`
- Modify: `backend/app/core/exceptions.py` (add `conflict`, `invalid_state`)
- Modify: `backend/app/services/scope_service.py` (add `asset_scope`)
- Modify: `backend/app/repositories/employee_repo.py` (add `ids_in_departments`)
- Modify: `backend/app/repositories/base.py` (add `apply_current_employee_scope`)
- Create: `backend/app/schemas/workstation.py`
- Create: `backend/app/schemas/device.py`
- Create: `backend/tests/test_asset_scope.py`

**Interfaces:**
- `constants.WorkstationStatus` (IDLE/OCCUPIED/RESERVED/DISABLED), `constants.DeviceStatus` (IN_STOCK/IN_USE/REPAIR/SCRAPPED).
- `exceptions.conflict(message="资源冲突，请刷新后重试") -> BizError(3001,.,409)`; `exceptions.invalid_state(message="当前状态不允许该操作") -> BizError(3007,.,409)`.
- `scope_service.asset_scope(db, user) -> dict`: `{"mode":"all"}` / `{"mode":"self","employee_id":..}` / `{"mode":"employees","employee_ids":set}`.
- `employee_repo.ids_in_departments(db, dept_ids:set[str]) -> set[str]`.
- `base.apply_current_employee_scope(stmt, scope:dict, model) -> stmt`.
- Schemas per §8.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_asset_scope.py`:
```python
from app.core.deps import CurrentUser
from app.core.exceptions import conflict, invalid_state, BizError
from app.core.constants import WorkstationStatus, DeviceStatus
from app.models import Department, Employee
from app.repositories import employee_repo
from app.services import scope_service


def test_error_helpers():
    assert isinstance(conflict(), BizError) and conflict().code == 3001 and conflict().http_status == 409
    assert invalid_state().code == 3007 and invalid_state().http_status == 409


def test_status_constants():
    assert WorkstationStatus.IDLE == 1 and WorkstationStatus.OCCUPIED == 2
    assert DeviceStatus.IN_STOCK == 1 and DeviceStatus.IN_USE == 2


def _u(scope, dept=None, emp=None):
    return CurrentUser(id="u", username="x", role_code="r", data_scope=scope,
                       permissions=set(), employee_id=emp, department_id=dept)


def test_ids_in_departments(db):
    a = Department(name="A", sort_order=0, status=1); db.add(a); db.flush()
    e1 = Employee(employee_no="E1", name="a", gender=1, department_id=a.id, status=1)
    e2 = Employee(employee_no="E2", name="b", gender=1, department_id=a.id, status=1)
    e3 = Employee(employee_no="E3", name="c", gender=1, status=1)  # no dept
    db.add_all([e1, e2, e3]); db.flush()
    ids = employee_repo.ids_in_departments(db, {a.id})
    assert ids == {e1.id, e2.id}
    assert employee_repo.ids_in_departments(db, set()) == set()


def test_asset_scope_modes(db):
    a = Department(name="A", sort_order=0, status=1); db.add(a); db.flush()
    e1 = Employee(employee_no="E1", name="a", gender=1, department_id=a.id, status=1)
    db.add(e1); db.flush()
    assert scope_service.asset_scope(db, _u("all")) == {"mode": "all"}
    assert scope_service.asset_scope(db, _u("self", emp="x")) == {"mode": "self", "employee_id": "x"}
    dept = scope_service.asset_scope(db, _u("dept", dept=a.id))
    assert dept["mode"] == "employees" and e1.id in dept["employee_ids"]
    none_dept = scope_service.asset_scope(db, _u("dept", dept=None))
    assert none_dept == {"mode": "employees", "employee_ids": set()}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_asset_scope.py -v` → FAIL (modules/functions missing).

- [ ] **Step 3: Implement constants + error helpers**

Create `backend/app/core/constants.py`:
```python
class WorkstationStatus:
    IDLE = 1
    OCCUPIED = 2
    RESERVED = 3
    DISABLED = 4


class DeviceStatus:
    IN_STOCK = 1
    IN_USE = 2
    REPAIR = 3
    SCRAPPED = 4
```

Add to `backend/app/core/exceptions.py` (after `not_found`):
```python
def conflict(message: str = "资源冲突，请刷新后重试") -> BizError:
    return BizError(3001, message, 409)


def invalid_state(message: str = "当前状态不允许该操作") -> BizError:
    return BizError(3007, message, 409)
```

- [ ] **Step 4: Implement ids_in_departments, apply_current_employee_scope, asset_scope**

Add to `backend/app/repositories/employee_repo.py`:
```python
def ids_in_departments(db: Session, dept_ids: set[str]) -> set[str]:
    if not dept_ids:
        return set()
    stmt = select(Employee.id).where(
        Employee.department_id.in_(dept_ids), Employee.deleted_at.is_(None)
    )
    return set(db.execute(stmt).scalars().all())
```

Add to `backend/app/repositories/base.py`:
```python
from sqlalchemy import false


def apply_current_employee_scope(stmt, scope: dict, model):
    mode = scope["mode"]
    if mode == "all":
        return stmt
    if mode == "self":
        eid = scope.get("employee_id")
        return stmt.where(model.current_employee_id == eid) if eid else stmt.where(false())
    ids = scope.get("employee_ids") or set()
    return stmt.where(model.current_employee_id.in_(ids)) if ids else stmt.where(false())
```

Add to `backend/app/services/scope_service.py`:
```python
from app.repositories import employee_repo


def asset_scope(db: Session, user: CurrentUser) -> dict:
    desc = data_scope_descriptor(user)
    if desc["scope"] == "all":
        return {"mode": "all"}
    if desc["scope"] == "self":
        return {"mode": "self", "employee_id": desc.get("employee_id")}
    dept_ids = accessible_department_ids(db, user) or set()
    return {"mode": "employees", "employee_ids": employee_repo.ids_in_departments(db, dept_ids)}
```
> `scope_service` already imports `department_repo`; add `employee_repo` import at top if not present.

- [ ] **Step 5: Implement schemas**

Create `backend/app/schemas/workstation.py`:
```python
from datetime import date

from pydantic import BaseModel, Field


class WorkstationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    location: str | None = Field(default=None, max_length=128)
    type: str = Field(min_length=1, max_length=16)
    notes: str | None = Field(default=None, max_length=255)


class WorkstationUpdate(BaseModel):
    location: str | None = Field(default=None, max_length=128)
    type: str | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None, max_length=255)


class WorkstationAssignReq(BaseModel):
    employee_id: str
    assign_date: date | None = None
    version: int | None = None


class WorkstationStatusReq(BaseModel):
    status: int  # 1=idle,3=reserved,4=disabled (validated in service)


class BatchReleaseReq(BaseModel):
    workstation_ids: list[str] = Field(min_length=1)
```

Create `backend/app/schemas/device.py`:
```python
from datetime import date

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=32)
    type: str = Field(min_length=1, max_length=16)
    brand: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=64)
    specs: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    warranty_expire: date | None = None
    notes: str | None = Field(default=None, max_length=255)


class DeviceUpdate(BaseModel):
    type: str | None = Field(default=None, max_length=16)
    brand: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=64)
    specs: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    warranty_expire: date | None = None
    notes: str | None = Field(default=None, max_length=255)


class DeviceCheckoutReq(BaseModel):
    employee_id: str
    assign_date: date | None = None
    version: int | None = None
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_asset_scope.py -v` → PASS (5 passed). Then `pytest -v` full suite → no regressions (report count).

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/constants.py backend/app/core/exceptions.py backend/app/services/scope_service.py backend/app/repositories/employee_repo.py backend/app/repositories/base.py backend/app/schemas/workstation.py backend/app/schemas/device.py backend/tests/test_asset_scope.py
git commit -m "$(cat <<'EOF'
feat(assets): status constants, conflict/invalid-state errors, asset data-scope, schemas

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: workstation repository + workstation-assignment history (optimistic lock)

**Files:**
- Create: `backend/app/repositories/workstation_repo.py`
- Create: `backend/app/repositories/assignment_repo.py`
- Create: `backend/tests/test_workstation_repo.py`

**Interfaces:**
- `workstation_repo`: `get_active(db,id_)`, `get_by_code(db,code)`, `paginate(db,*,params,type=None,status=None,scope)->(items,total)`, `create(db,**fields)`, `assign_if_free(db,id_,employee_id,assign_date,expected_version,updated_by)->int`, `release_if_occupied(db,id_,updated_by)->int`, `set_status(db,id_,new_status,updated_by)->int` (WHERE status != OCCUPIED).
- `assignment_repo` (workstation part): `create_ws(db,workstation_id,employee_id,start_date,operator_id)`, `close_ws_open(db,workstation_id,end_date)->int`, `list_ws(db,workstation_id)->list[WorkstationAssignment]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_workstation_repo.py`:
```python
from datetime import date

from app.core.constants import WorkstationStatus
from app.models import Workstation, Employee
from app.repositories import workstation_repo, assignment_repo
from app.schemas.common import PageParams


def _ws(db, code, status=WorkstationStatus.IDLE):
    w = workstation_repo.create(db, code=code, type="fixed", status=status)
    db.flush()
    return w


def _emp(db, no):
    e = Employee(employee_no=no, name=no, gender=1, status=1)
    db.add(e); db.flush()
    return e


def test_assign_if_free_optimistic(db):
    w = _ws(db, "A-1")
    e = _emp(db, "E1")
    v = w.version
    n1 = workstation_repo.assign_if_free(db, w.id, e.id, date.today(), v, "op")
    assert n1 == 1
    db.flush()
    # second attempt with the STALE version must fail (row now has version+1, status occupied)
    n2 = workstation_repo.assign_if_free(db, w.id, e.id, date.today(), v, "op")
    assert n2 == 0


def test_release_if_occupied(db):
    w = _ws(db, "A-2")
    e = _emp(db, "E2")
    workstation_repo.assign_if_free(db, w.id, e.id, date.today(), w.version, "op")
    db.flush()
    n = workstation_repo.release_if_occupied(db, w.id, "op")
    assert n == 1
    db.flush()
    db.refresh(w)
    assert w.status == WorkstationStatus.IDLE and w.current_employee_id is None


def test_set_status_blocked_when_occupied(db):
    w = _ws(db, "A-3")
    e = _emp(db, "E3")
    workstation_repo.assign_if_free(db, w.id, e.id, date.today(), w.version, "op")
    db.flush()
    assert workstation_repo.set_status(db, w.id, WorkstationStatus.DISABLED, "op") == 0  # occupied -> blocked


def test_history_open_and_close(db):
    w = _ws(db, "A-4")
    e = _emp(db, "E4")
    assignment_repo.create_ws(db, w.id, e.id, date.today(), "op")
    db.flush()
    assert len(assignment_repo.list_ws(db, w.id)) == 1
    n = assignment_repo.close_ws_open(db, w.id, date.today())
    assert n == 1


def test_paginate_scope(db):
    a = _ws(db, "A-5"); e = _emp(db, "E5")
    workstation_repo.assign_if_free(db, a.id, e.id, date.today(), a.version, "op")
    db.flush()
    idle = _ws(db, "A-6")  # idle, no occupant
    # dept scope with employee e -> sees occupied one, not the idle one
    items, total = workstation_repo.paginate(
        db, params=PageParams(), scope={"mode": "employees", "employee_ids": {e.id}})
    codes = {w.code for w in items}
    assert "A-5" in codes and "A-6" not in codes
    # empty employees -> nothing
    _, t0 = workstation_repo.paginate(db, params=PageParams(), scope={"mode": "employees", "employee_ids": set()})
    assert t0 == 0
```

- [ ] **Step 2: Run test to verify it fails** → `pytest tests/test_workstation_repo.py -v` FAIL.

- [ ] **Step 3: Implement workstation_repo**

Create `backend/app/repositories/workstation_repo.py`:
```python
from datetime import date

from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import Session

from app.core.constants import WorkstationStatus
from app.models import Workstation
from app.repositories.base import apply_current_employee_scope
from app.schemas.common import PageParams


def get_active(db: Session, id_: str) -> Workstation | None:
    stmt = select(Workstation).where(Workstation.id == id_, Workstation.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_by_code(db: Session, code: str) -> Workstation | None:
    stmt = select(Workstation).where(Workstation.code == code, Workstation.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def paginate(db: Session, *, params: PageParams, type: str | None = None,
             status: int | None = None, scope: dict) -> tuple[list[Workstation], int]:
    base = select(Workstation).where(Workstation.deleted_at.is_(None))
    base = apply_current_employee_scope(base, scope, Workstation)
    if type:
        base = base.where(Workstation.type == type)
    if status is not None:
        base = base.where(Workstation.status == status)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(Workstation.code.like(kw), Workstation.location.like(kw)))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    order = Workstation.created_at.desc() if params.order == "desc" else Workstation.created_at.asc()
    stmt = base.order_by(order).offset((params.page - 1) * params.page_size).limit(params.page_size)
    return list(db.execute(stmt).scalars().all()), total


def create(db: Session, **fields) -> Workstation:
    w = Workstation(**fields)
    db.add(w)
    return w


def assign_if_free(db: Session, id_: str, employee_id: str, assign_date: date,
                   expected_version: int, updated_by: str) -> int:
    stmt = (update(Workstation)
            .where(Workstation.id == id_, Workstation.status == WorkstationStatus.IDLE,
                   Workstation.version == expected_version, Workstation.deleted_at.is_(None))
            .values(current_employee_id=employee_id, status=WorkstationStatus.OCCUPIED,
                    assign_date=assign_date, version=Workstation.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def release_if_occupied(db: Session, id_: str, updated_by: str) -> int:
    stmt = (update(Workstation)
            .where(Workstation.id == id_, Workstation.status == WorkstationStatus.OCCUPIED,
                   Workstation.deleted_at.is_(None))
            .values(current_employee_id=None, status=WorkstationStatus.IDLE, assign_date=None,
                    version=Workstation.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def set_status(db: Session, id_: str, new_status: int, updated_by: str) -> int:
    stmt = (update(Workstation)
            .where(Workstation.id == id_, Workstation.status != WorkstationStatus.OCCUPIED,
                   Workstation.deleted_at.is_(None))
            .values(status=new_status, version=Workstation.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount
```

- [ ] **Step 4: Implement assignment_repo (workstation part)**

Create `backend/app/repositories/assignment_repo.py`:
```python
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import WorkstationAssignment, DeviceAssignment


# --- workstation history ---
def create_ws(db: Session, workstation_id: str, employee_id: str,
              start_date: date, operator_id: str) -> WorkstationAssignment:
    row = WorkstationAssignment(workstation_id=workstation_id, employee_id=employee_id,
                                start_date=start_date, operator_id=operator_id)
    db.add(row)
    return row


def close_ws_open(db: Session, workstation_id: str, end_date: date) -> int:
    stmt = (update(WorkstationAssignment)
            .where(WorkstationAssignment.workstation_id == workstation_id,
                   WorkstationAssignment.end_date.is_(None))
            .values(end_date=end_date))
    return db.execute(stmt).rowcount


def list_ws(db: Session, workstation_id: str) -> list[WorkstationAssignment]:
    stmt = (select(WorkstationAssignment)
            .where(WorkstationAssignment.workstation_id == workstation_id)
            .order_by(WorkstationAssignment.created_at.desc()))
    return list(db.execute(stmt).scalars().all())


# --- device history (used in Task 4/5) ---
def create_dev(db: Session, device_id: str, employee_id: str,
               checkout_date: date, operator_id: str) -> DeviceAssignment:
    row = DeviceAssignment(device_id=device_id, employee_id=employee_id,
                           checkout_date=checkout_date, operator_id=operator_id)
    db.add(row)
    return row


def close_dev_open(db: Session, device_id: str, return_date: date) -> int:
    stmt = (update(DeviceAssignment)
            .where(DeviceAssignment.device_id == device_id,
                   DeviceAssignment.return_date.is_(None))
            .values(return_date=return_date))
    return db.execute(stmt).rowcount


def list_dev(db: Session, device_id: str) -> list[DeviceAssignment]:
    stmt = (select(DeviceAssignment)
            .where(DeviceAssignment.device_id == device_id)
            .order_by(DeviceAssignment.created_at.desc()))
    return list(db.execute(stmt).scalars().all())
```

- [ ] **Step 5: Run test to verify it passes** → `pytest tests/test_workstation_repo.py -v` PASS (5). Full suite green.

- [ ] **Step 6: Commit**
```bash
git add backend/app/repositories/workstation_repo.py backend/app/repositories/assignment_repo.py backend/tests/test_workstation_repo.py
git commit -m "$(cat <<'EOF'
feat(assets): workstation repo with optimistic-lock assign/release and history repo

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: workstation service + router (assign/release/batch/status/history + scope + tx)

**Files:**
- Create: `backend/app/services/workstation_service.py`
- Create: `backend/app/routers/workstations.py`
- Modify: `backend/app/api/v1.py`
- Create: `backend/tests/test_workstations.py`

**Interfaces:**
- Endpoints `/api/v1/workstations`: GET "", GET /{id_}, POST "", PUT /{id_}, POST /{id_}/assign, POST /{id_}/release, POST /batch-release, PATCH /{id_}/status, GET /{id_}/history.
- `workstation_service`: `list_/get_one/create/update/assign/release/batch_release/set_status/history`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_workstations.py`:
```python
import pytest

from app.models import Role, Employee, User, Department
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db); db.flush(); return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u); db.flush(); return u


def _login(client, u):
    return client.post("/api/v1/auth/login", json={"username": u, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _emp(db, no, dept=None):
    e = Employee(employee_no=no, name=no, gender=1, department_id=dept, status=1)
    db.add(e); db.flush(); return e


def test_create_assign_release_history(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E1")
    wid = client.post("/api/v1/workstations", headers=_h(tok),
                      json={"code": "A-1", "type": "fixed"}).json()["data"]["id"]
    r = client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok),
                    json={"employee_id": e.id})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == 2
    # double assign -> conflict 3001
    r2 = client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok),
                     json={"employee_id": e.id})
    assert r2.json()["code"] == 3001
    assert client.post(f"/api/v1/workstations/{wid}/release", headers=_h(tok)).json()["code"] == 0
    hist = client.get(f"/api/v1/workstations/{wid}/history", headers=_h(tok)).json()["data"]
    assert len(hist) == 1 and hist[0]["end_date"] is not None


def test_stale_version_conflict(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E2")
    wid = client.post("/api/v1/workstations", headers=_h(tok),
                      json={"code": "A-2", "type": "fixed"}).json()["data"]["id"]
    # assign with explicit stale version 999 -> conflict
    r = client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok),
                    json={"employee_id": e.id, "version": 999})
    assert r.json()["code"] == 3001


def test_batch_release(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E3")
    ids = []
    for c in ("B-1", "B-2"):
        wid = client.post("/api/v1/workstations", headers=_h(tok), json={"code": c, "type": "fixed"}).json()["data"]["id"]
        client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok), json={"employee_id": e.id})
        ids.append(wid)
    r = client.post("/api/v1/workstations/batch-release", headers=_h(tok), json={"workstation_ids": ids})
    assert r.json()["data"]["released"] == 2


def test_status_reserve(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    wid = client.post("/api/v1/workstations", headers=_h(tok), json={"code": "C-1", "type": "fixed"}).json()["data"]["id"]
    r = client.patch(f"/api/v1/workstations/{wid}/status", headers=_h(tok), json={"status": 3})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == 3


def test_data_scope_and_idle_invisible(client, seeded):
    _user(seeded, "it", "it_admin")
    it = _login(client, "it")
    a = Department(name="A", sort_order=0, status=1); seeded.add(a); seeded.flush()
    mgr = _emp(seeded, "M", dept=a.id)
    occupied = client.post("/api/v1/workstations", headers=_h(it), json={"code": "D-1", "type": "fixed"}).json()["data"]["id"]
    client.post(f"/api/v1/workstations/{occupied}/assign", headers=_h(it), json={"employee_id": mgr.id})
    client.post("/api/v1/workstations", headers=_h(it), json={"code": "D-2", "type": "fixed"})  # idle
    _user(seeded, "mgr", "dept_manager", employee_id=mgr.id)
    tok = _login(client, "mgr")
    data = client.get("/api/v1/workstations", headers=_h(tok)).json()["data"]
    codes = {w["code"] for w in data["items"]}
    assert codes == {"D-1"}  # occupied by in-scope employee; idle D-2 invisible


def test_hr_can_manage_workstations_but_not_devices_perm(client, seeded):
    # workstation:manage includes hr_admin
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    r = client.post("/api/v1/workstations", headers=_h(tok), json={"code": "H-1", "type": "fixed"})
    assert r.json()["code"] == 0
```

- [ ] **Step 2: Run test to verify it fails** → FAIL.

- [ ] **Step 3: Implement workstation_service**

Create `backend/app/services/workstation_service.py`:
```python
from datetime import date

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import WorkstationStatus
from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found, conflict, invalid_state
from app.models import Workstation
from app.repositories import workstation_repo, assignment_repo, employee_repo, operation_log_repo
from app.services import scope_service


def _ip(r): return r.client.host if r and r.client else None
def _ua(r): return r.headers.get("User-Agent") if r else None


def _out(w: Workstation) -> dict:
    return {"id": w.id, "code": w.code, "location": w.location, "type": w.type,
            "status": w.status, "current_employee_id": w.current_employee_id,
            "assign_date": w.assign_date.isoformat() if w.assign_date else None,
            "version": w.version, "notes": w.notes}


def _visible(db, user, w: Workstation) -> bool:
    scope = scope_service.asset_scope(db, user)
    if scope["mode"] == "all":
        return True
    if scope["mode"] == "self":
        return w.current_employee_id == scope.get("employee_id")
    return w.current_employee_id in (scope.get("employee_ids") or set())


def list_(db, user, params, type, status) -> dict:
    scope = scope_service.asset_scope(db, user)
    items, total = workstation_repo.paginate(db, params=params, type=type, status=status, scope=scope)
    return {"items": [_out(w) for w in items], "total": total, "page": params.page, "page_size": params.page_size}


def get_one(db, user, id_) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None or not _visible(db, user, w):
        raise not_found("工位不存在")
    return _out(w)


def create(db, user, data, req) -> dict:
    if workstation_repo.get_by_code(db, data.code) is not None:
        raise biz(3005, "工位编号已存在")
    w = workstation_repo.create(db, code=data.code, location=data.location, type=data.type,
                                status=WorkstationStatus.IDLE, notes=data.notes,
                                created_by=user.id, updated_by=user.id)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise biz(3005, "工位编号已存在")
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="create",
                              target_type="workstation", target_id=w.id, detail={"code": w.code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(w)


def update(db, user, id_, data, req) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    for f in ("location", "type", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(w, f, v)
    w.updated_by = user.id
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="update",
                              target_type="workstation", target_id=w.id, detail={"code": w.code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(w)


def assign(db, user, id_, data, req) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    emp = employee_repo.get_active(db, data.employee_id)
    if emp is None or emp.status != 1:
        raise biz(3002, "目标员工不存在或已离职")
    d = data.assign_date or date.today()
    expected = data.version if data.version is not None else w.version
    n = workstation_repo.assign_if_free(db, id_, data.employee_id, d, expected, user.id)
    if n == 0:
        raise conflict("该工位已被占用，请刷新后重试")
    assignment_repo.create_ws(db, id_, data.employee_id, d, user.id)
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="assign",
                              target_type="workstation", target_id=id_,
                              detail={"employee_id": data.employee_id}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(w)
    return _out(w)


def release(db, user, id_, req) -> dict:
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    n = workstation_repo.release_if_occupied(db, id_, user.id)
    if n == 0:
        raise invalid_state("工位当前未被占用")
    assignment_repo.close_ws_open(db, id_, date.today())
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="release",
                              target_type="workstation", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(w)
    return _out(w)


def batch_release(db, user, ids, req) -> dict:
    released = 0
    for id_ in ids:
        n = workstation_repo.release_if_occupied(db, id_, user.id)
        if n == 1:
            assignment_repo.close_ws_open(db, id_, date.today())
            released += 1
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="batch_release",
                              target_type="workstation", target_id=None,
                              detail={"ids": ids, "released": released}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"released": released}


def set_status(db, user, id_, new_status, req) -> dict:
    if new_status not in (WorkstationStatus.IDLE, WorkstationStatus.RESERVED, WorkstationStatus.DISABLED):
        raise biz(2001, "非法的目标状态")
    w = workstation_repo.get_active(db, id_)
    if w is None:
        raise not_found("工位不存在")
    n = workstation_repo.set_status(db, id_, new_status, user.id)
    if n == 0:
        raise invalid_state("占用中的工位不能直接改状态，请先释放")
    operation_log_repo.create(db, user_id=user.id, module="workstation", action="set_status",
                              target_type="workstation", target_id=id_, detail={"status": new_status},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    db.refresh(w)
    return _out(w)


def history(db, user, id_) -> list[dict]:
    w = workstation_repo.get_active(db, id_)
    if w is None or not _visible(db, user, w):
        raise not_found("工位不存在")
    rows = assignment_repo.list_ws(db, id_)
    return [{"employee_id": r.employee_id, "start_date": r.start_date.isoformat(),
             "end_date": r.end_date.isoformat() if r.end_date else None,
             "operator_id": r.operator_id} for r in rows]
```

- [ ] **Step 4: Implement router + wire**

Create `backend/app/routers/workstations.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.workstation import (
    WorkstationCreate, WorkstationUpdate, WorkstationAssignReq, WorkstationStatusReq, BatchReleaseReq,
)
from app.services import workstation_service

router = APIRouter(prefix="/workstations", tags=["workstations"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          type: str | None = None, status: int | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("workstation:view"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=workstation_service.list_(db, user, params, type, status))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("workstation:view"))):
    return envelope(data=workstation_service.get_one(db, user, id_))


@router.post("")
def create(body: WorkstationCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: WorkstationUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.update(db, user, id_, body, request))


@router.post("/{id_}/assign")
def assign(id_: str, body: WorkstationAssignReq, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.assign(db, user, id_, body, request), message="分配成功")


@router.post("/{id_}/release")
def release(id_: str, request: Request, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.release(db, user, id_, request), message="已释放")


@router.post("/batch-release")
def batch_release(body: BatchReleaseReq, request: Request, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.batch_release(db, user, body.workstation_ids, request))


@router.patch("/{id_}/status")
def set_status(id_: str, body: WorkstationStatusReq, request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_permission("workstation:manage"))):
    return envelope(data=workstation_service.set_status(db, user, id_, body.status, request))


@router.get("/{id_}/history")
def history(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("workstation:view"))):
    return envelope(data=workstation_service.history(db, user, id_))
```

Modify `backend/app/api/v1.py` — add:
```python
from app.routers.workstations import router as workstations_router
...
api_router.include_router(workstations_router)
```

- [ ] **Step 5: Run test to verify it passes** → `pytest tests/test_workstations.py -v` PASS (6). Full suite green.

- [ ] **Step 6: Commit**
```bash
git add backend/app/services/workstation_service.py backend/app/routers/workstations.py backend/app/api/v1.py backend/tests/test_workstations.py
git commit -m "$(cat <<'EOF'
feat(assets): workstation service+router (assign/release/batch/status/history, tx, scope)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: device repository (optimistic lock + state transitions)

**Files:**
- Create: `backend/app/repositories/device_repo.py`
- Create: `backend/tests/test_device_repo.py`

**Interfaces:**
- `device_repo`: `get_active`, `get_by_asset_code`, `paginate(db,*,params,type=None,status=None,scope)`, `create`, `checkout_if_available(db,id_,employee_id,assign_date,expected_version,updated_by)->int`, `return_if_in_use(db,id_,updated_by)->int`, `to_repair(db,id_,updated_by)->int` (from IN_STOCK), `to_scrap(db,id_,updated_by)->int` (from IN_STOCK or REPAIR).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_device_repo.py`:
```python
from datetime import date

from app.core.constants import DeviceStatus
from app.models import Employee
from app.repositories import device_repo
from app.schemas.common import PageParams


def _dev(db, code, status=DeviceStatus.IN_STOCK):
    d = device_repo.create(db, asset_code=code, type="laptop", status=status)
    db.flush(); return d


def _emp(db, no):
    e = Employee(employee_no=no, name=no, gender=1, status=1); db.add(e); db.flush(); return e


def test_checkout_optimistic(db):
    d = _dev(db, "AST-1"); e = _emp(db, "E1")
    v = d.version
    assert device_repo.checkout_if_available(db, d.id, e.id, date.today(), v, "op") == 1
    db.flush()
    assert device_repo.checkout_if_available(db, d.id, e.id, date.today(), v, "op") == 0  # stale


def test_return_and_repair_scrap(db):
    d = _dev(db, "AST-2"); e = _emp(db, "E2")
    device_repo.checkout_if_available(db, d.id, e.id, date.today(), d.version, "op"); db.flush()
    assert device_repo.return_if_in_use(db, d.id, "op") == 1; db.flush()
    assert device_repo.to_repair(db, d.id, "op") == 1; db.flush()  # in-stock -> repair
    db.refresh(d); assert d.status == DeviceStatus.REPAIR
    assert device_repo.to_scrap(db, d.id, "op") == 1  # repair -> scrap


def test_repair_blocked_when_in_use(db):
    d = _dev(db, "AST-3"); e = _emp(db, "E3")
    device_repo.checkout_if_available(db, d.id, e.id, date.today(), d.version, "op"); db.flush()
    assert device_repo.to_repair(db, d.id, "op") == 0  # in-use cannot go to repair directly


def test_paginate_scope(db):
    d = _dev(db, "AST-4"); e = _emp(db, "E4")
    device_repo.checkout_if_available(db, d.id, e.id, date.today(), d.version, "op"); db.flush()
    _dev(db, "AST-5")  # in-stock, no holder
    items, total = device_repo.paginate(db, params=PageParams(), scope={"mode": "employees", "employee_ids": {e.id}})
    codes = {x.asset_code for x in items}
    assert "AST-4" in codes and "AST-5" not in codes
```

- [ ] **Step 2: Run test to verify it fails** → FAIL.

- [ ] **Step 3: Implement device_repo**

Create `backend/app/repositories/device_repo.py`:
```python
from datetime import date

from sqlalchemy import select, func, or_, update
from sqlalchemy.orm import Session

from app.core.constants import DeviceStatus
from app.models import Device
from app.repositories.base import apply_current_employee_scope
from app.schemas.common import PageParams


def get_active(db: Session, id_: str) -> Device | None:
    return db.execute(select(Device).where(Device.id == id_, Device.deleted_at.is_(None))).scalar_one_or_none()


def get_by_asset_code(db: Session, code: str) -> Device | None:
    return db.execute(select(Device).where(Device.asset_code == code, Device.deleted_at.is_(None))).scalar_one_or_none()


def paginate(db: Session, *, params: PageParams, type: str | None = None,
             status: int | None = None, scope: dict) -> tuple[list[Device], int]:
    base = select(Device).where(Device.deleted_at.is_(None))
    base = apply_current_employee_scope(base, scope, Device)
    if type:
        base = base.where(Device.type == type)
    if status is not None:
        base = base.where(Device.status == status)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(Device.asset_code.like(kw), Device.serial_number.like(kw)))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    order = Device.created_at.desc() if params.order == "desc" else Device.created_at.asc()
    stmt = base.order_by(order).offset((params.page - 1) * params.page_size).limit(params.page_size)
    return list(db.execute(stmt).scalars().all()), total


def create(db: Session, **fields) -> Device:
    d = Device(**fields)
    db.add(d)
    return d


def checkout_if_available(db, id_, employee_id, assign_date, expected_version, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status == DeviceStatus.IN_STOCK,
                   Device.version == expected_version, Device.deleted_at.is_(None))
            .values(current_employee_id=employee_id, status=DeviceStatus.IN_USE,
                    assign_date=assign_date, version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def return_if_in_use(db, id_, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status == DeviceStatus.IN_USE, Device.deleted_at.is_(None))
            .values(current_employee_id=None, status=DeviceStatus.IN_STOCK, assign_date=None,
                    version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def to_repair(db, id_, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status == DeviceStatus.IN_STOCK, Device.deleted_at.is_(None))
            .values(status=DeviceStatus.REPAIR, version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount


def to_scrap(db, id_, updated_by) -> int:
    stmt = (update(Device)
            .where(Device.id == id_, Device.status.in_([DeviceStatus.IN_STOCK, DeviceStatus.REPAIR]),
                   Device.deleted_at.is_(None))
            .values(status=DeviceStatus.SCRAPPED, version=Device.version + 1, updated_by=updated_by))
    return db.execute(stmt).rowcount
```

- [ ] **Step 4: Run test to verify it passes** → `pytest tests/test_device_repo.py -v` PASS (4). Full suite green.

- [ ] **Step 5: Commit**
```bash
git add backend/app/repositories/device_repo.py backend/tests/test_device_repo.py
git commit -m "$(cat <<'EOF'
feat(assets): device repo with optimistic-lock checkout/return and repair/scrap transitions

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: device service + router (checkout/return/repair/scrap/history + scope + tx)

**Files:**
- Create: `backend/app/services/device_service.py`
- Create: `backend/app/routers/devices.py`
- Modify: `backend/app/api/v1.py`
- Create: `backend/tests/test_devices.py`

**Interfaces:**
- Endpoints `/api/v1/devices`: GET "", GET /{id_}, POST "", PUT /{id_}, POST /{id_}/checkout, POST /{id_}/return, POST /{id_}/repair, POST /{id_}/scrap, GET /{id_}/history.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_devices.py`:
```python
import pytest

from app.models import Role, Employee, User
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db); db.flush(); return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u); db.flush(); return u


def _login(client, u):
    return client.post("/api/v1/auth/login", json={"username": u, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _emp(db, no):
    e = Employee(employee_no=no, name=no, gender=1, status=1); db.add(e); db.flush(); return e


def test_checkout_return_history(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E1")
    did = client.post("/api/v1/devices", headers=_h(tok),
                      json={"asset_code": "AST-1", "type": "laptop"}).json()["data"]["id"]
    r = client.post(f"/api/v1/devices/{did}/checkout", headers=_h(tok), json={"employee_id": e.id})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == 2
    assert client.post(f"/api/v1/devices/{did}/checkout", headers=_h(tok), json={"employee_id": e.id}).json()["code"] == 3001
    assert client.post(f"/api/v1/devices/{did}/return", headers=_h(tok)).json()["code"] == 0
    hist = client.get(f"/api/v1/devices/{did}/history", headers=_h(tok)).json()["data"]
    assert len(hist) == 1 and hist[0]["return_date"] is not None


def test_repair_scrap(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    did = client.post("/api/v1/devices", headers=_h(tok), json={"asset_code": "AST-2", "type": "laptop"}).json()["data"]["id"]
    assert client.post(f"/api/v1/devices/{did}/repair", headers=_h(tok)).json()["data"]["status"] == 3
    # in repair, checkout must fail (not in stock)
    e = _emp(seeded, "E2")
    assert client.post(f"/api/v1/devices/{did}/checkout", headers=_h(tok), json={"employee_id": e.id}).json()["code"] == 3001
    assert client.post(f"/api/v1/devices/{did}/scrap", headers=_h(tok)).json()["data"]["status"] == 4


def test_hr_admin_has_no_device_access(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    assert client.get("/api/v1/devices", headers=_h(tok)).json()["code"] == 1003


def test_device_self_scope(client, seeded):
    _user(seeded, "it", "it_admin")
    it = _login(client, "it")
    me = _emp(seeded, "SELF")
    other = _emp(seeded, "OTH")
    d1 = client.post("/api/v1/devices", headers=_h(it), json={"asset_code": "S-1", "type": "laptop"}).json()["data"]["id"]
    client.post(f"/api/v1/devices/{d1}/checkout", headers=_h(it), json={"employee_id": me.id})
    d2 = client.post("/api/v1/devices", headers=_h(it), json={"asset_code": "S-2", "type": "laptop"}).json()["data"]["id"]
    client.post(f"/api/v1/devices/{d2}/checkout", headers=_h(it), json={"employee_id": other.id})
    _user(seeded, "self1", "employee", employee_id=me.id)
    tok = _login(client, "self1")
    data = client.get("/api/v1/devices", headers=_h(tok)).json()["data"]
    assert {x["asset_code"] for x in data["items"]} == {"S-1"}
    assert client.get(f"/api/v1/devices/{d2}", headers=_h(tok)).json()["code"] == 3404
```

- [ ] **Step 2: Run test to verify it fails** → FAIL.

- [ ] **Step 3: Implement device_service**

Create `backend/app/services/device_service.py`:
```python
from datetime import date

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import DeviceStatus
from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found, conflict, invalid_state
from app.models import Device
from app.repositories import device_repo, assignment_repo, employee_repo, operation_log_repo
from app.services import scope_service


def _ip(r): return r.client.host if r and r.client else None
def _ua(r): return r.headers.get("User-Agent") if r else None


def _out(d: Device) -> dict:
    return {"id": d.id, "asset_code": d.asset_code, "type": d.type, "brand": d.brand,
            "model": d.model, "serial_number": d.serial_number, "specs": d.specs,
            "purchase_date": d.purchase_date.isoformat() if d.purchase_date else None,
            "warranty_expire": d.warranty_expire.isoformat() if d.warranty_expire else None,
            "status": d.status, "current_employee_id": d.current_employee_id,
            "assign_date": d.assign_date.isoformat() if d.assign_date else None, "version": d.version,
            "notes": d.notes}


def _visible(db, user, d: Device) -> bool:
    scope = scope_service.asset_scope(db, user)
    if scope["mode"] == "all":
        return True
    if scope["mode"] == "self":
        return d.current_employee_id == scope.get("employee_id")
    return d.current_employee_id in (scope.get("employee_ids") or set())


def list_(db, user, params, type, status) -> dict:
    scope = scope_service.asset_scope(db, user)
    items, total = device_repo.paginate(db, params=params, type=type, status=status, scope=scope)
    return {"items": [_out(d) for d in items], "total": total, "page": params.page, "page_size": params.page_size}


def get_one(db, user, id_) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None or not _visible(db, user, d):
        raise not_found("设备不存在")
    return _out(d)


def create(db, user, data, req) -> dict:
    if device_repo.get_by_asset_code(db, data.asset_code) is not None:
        raise biz(3005, "资产编号已存在")
    d = device_repo.create(db, asset_code=data.asset_code, type=data.type, brand=data.brand,
                           model=data.model, serial_number=data.serial_number, specs=data.specs,
                           purchase_date=data.purchase_date, warranty_expire=data.warranty_expire,
                           status=DeviceStatus.IN_STOCK, notes=data.notes,
                           created_by=user.id, updated_by=user.id)
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise biz(3005, "资产编号/序列号已存在")
    operation_log_repo.create(db, user_id=user.id, module="device", action="create",
                              target_type="device", target_id=d.id, detail={"asset_code": d.asset_code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(d)


def update(db, user, id_, data, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    for f in ("type", "brand", "model", "serial_number", "specs", "purchase_date", "warranty_expire", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(d, f, v)
    d.updated_by = user.id
    try:
        db.flush()
    except IntegrityError:
        db.rollback(); raise biz(3005, "序列号已存在")
    operation_log_repo.create(db, user_id=user.id, module="device", action="update",
                              target_type="device", target_id=d.id, detail={"asset_code": d.asset_code},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _out(d)


def checkout(db, user, id_, data, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    emp = employee_repo.get_active(db, data.employee_id)
    if emp is None or emp.status != 1:
        raise biz(3002, "目标员工不存在或已离职")
    day = data.assign_date or date.today()
    expected = data.version if data.version is not None else d.version
    n = device_repo.checkout_if_available(db, id_, data.employee_id, day, expected, user.id)
    if n == 0:
        raise conflict("该设备不可领用（非在库或已被他人领用），请刷新后重试")
    assignment_repo.create_dev(db, id_, data.employee_id, day, user.id)
    operation_log_repo.create(db, user_id=user.id, module="device", action="checkout",
                              target_type="device", target_id=id_, detail={"employee_id": data.employee_id},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit(); db.refresh(d)
    return _out(d)


def return_(db, user, id_, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    n = device_repo.return_if_in_use(db, id_, user.id)
    if n == 0:
        raise invalid_state("设备当前不在使用中")
    assignment_repo.close_dev_open(db, id_, date.today())
    operation_log_repo.create(db, user_id=user.id, module="device", action="return",
                              target_type="device", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit(); db.refresh(d)
    return _out(d)


def repair(db, user, id_, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    n = device_repo.to_repair(db, id_, user.id)
    if n == 0:
        raise invalid_state("仅在库设备可送修")
    operation_log_repo.create(db, user_id=user.id, module="device", action="repair",
                              target_type="device", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit(); db.refresh(d)
    return _out(d)


def scrap(db, user, id_, req) -> dict:
    d = device_repo.get_active(db, id_)
    if d is None:
        raise not_found("设备不存在")
    n = device_repo.to_scrap(db, id_, user.id)
    if n == 0:
        raise invalid_state("仅在库或维修中的设备可报废")
    operation_log_repo.create(db, user_id=user.id, module="device", action="scrap",
                              target_type="device", target_id=id_, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit(); db.refresh(d)
    return _out(d)


def history(db, user, id_) -> list[dict]:
    d = device_repo.get_active(db, id_)
    if d is None or not _visible(db, user, d):
        raise not_found("设备不存在")
    rows = assignment_repo.list_dev(db, id_)
    return [{"employee_id": r.employee_id, "checkout_date": r.checkout_date.isoformat(),
             "return_date": r.return_date.isoformat() if r.return_date else None,
             "operator_id": r.operator_id} for r in rows]
```

- [ ] **Step 4: Implement router + wire**

Create `backend/app/routers/devices.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceCheckoutReq
from app.services import device_service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          type: str | None = None, status: int | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("device:view"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=device_service.list_(db, user, params, type, status))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("device:view"))):
    return envelope(data=device_service.get_one(db, user, id_))


@router.post("")
def create(body: DeviceCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: DeviceUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.update(db, user, id_, body, request))


@router.post("/{id_}/checkout")
def checkout(id_: str, body: DeviceCheckoutReq, request: Request, db: Session = Depends(get_db),
             user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.checkout(db, user, id_, body, request), message="领用成功")


@router.post("/{id_}/return")
def return_(id_: str, request: Request, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.return_(db, user, id_, request), message="已退还")


@router.post("/{id_}/repair")
def repair(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.repair(db, user, id_, request), message="已送修")


@router.post("/{id_}/scrap")
def scrap(id_: str, request: Request, db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("device:manage"))):
    return envelope(data=device_service.scrap(db, user, id_, request), message="已报废")


@router.get("/{id_}/history")
def history(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("device:view"))):
    return envelope(data=device_service.history(db, user, id_))
```

Modify `backend/app/api/v1.py` — add `from app.routers.devices import router as devices_router` and `api_router.include_router(devices_router)`.

- [ ] **Step 5: Run test to verify it passes** → `pytest tests/test_devices.py -v` PASS (4). Full suite green.

- [ ] **Step 6: Commit**
```bash
git add backend/app/services/device_service.py backend/app/routers/devices.py backend/app/api/v1.py backend/tests/test_devices.py
git commit -m "$(cat <<'EOF'
feat(assets): device service+router (checkout/return/repair/scrap/history, tx, scope)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: employee resign cascade + full suite + ruff

**Files:**
- Modify: `backend/app/services/employee_service.py` (add `resign`)
- Modify: `backend/app/routers/employees.py` (add `POST /{id_}/resign`)
- Create: `backend/app/schemas/employee.py` addition or inline (ResignReq)
- Create: `backend/tests/test_resign.py`

**Interfaces:**
- `employee_service.resign(db, user, id_, resign_date, req) -> dict` returns `{released_workstations, returned_devices, account_disabled}`.
- Endpoint `POST /api/v1/employees/{id_}/resign` guarded by `employee:resign`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_resign.py`:
```python
from datetime import date

import pytest

from app.models import Role, Employee, User, Workstation, Device
from app.core.constants import WorkstationStatus, DeviceStatus
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db); db.flush(); return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u); db.flush(); return u


def _login(client, u):
    return client.post("/api/v1/auth/login", json={"username": u, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_resign_cascade(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    # employee with an occupied workstation, 2 checked-out devices, and a bound account
    emp = Employee(employee_no="R1", name="r", gender=1, status=1)
    seeded.add(emp); seeded.flush()
    ws = Workstation(code="W-1", type="fixed", status=WorkstationStatus.OCCUPIED,
                     current_employee_id=emp.id, assign_date=date.today())
    d1 = Device(asset_code="D-1", type="laptop", status=DeviceStatus.IN_USE, current_employee_id=emp.id)
    d2 = Device(asset_code="D-2", type="laptop", status=DeviceStatus.IN_USE, current_employee_id=emp.id)
    seeded.add_all([ws, d1, d2]); seeded.flush()
    bound = _user(seeded, "empacct", "employee", employee_id=emp.id)

    r = client.post(f"/api/v1/employees/{emp.id}/resign", headers=_h(tok),
                    json={"resign_date": date.today().isoformat()})
    data = r.json()["data"]
    assert r.json()["code"] == 0
    assert data["released_workstations"] == 1
    assert data["returned_devices"] == 2
    assert data["account_disabled"] is True

    seeded.refresh(emp); seeded.refresh(ws); seeded.refresh(d1); seeded.refresh(d2); seeded.refresh(bound)
    assert emp.status == 0 and emp.resign_date is not None
    assert ws.status == WorkstationStatus.IDLE and ws.current_employee_id is None
    assert d1.status == DeviceStatus.IN_STOCK and d1.current_employee_id is None
    assert d2.status == DeviceStatus.IN_STOCK and d2.current_employee_id is None
    assert bound.status == 0


def test_resign_requires_permission(client, seeded):
    emp = Employee(employee_no="R2", name="r", gender=1, status=1); seeded.add(emp); seeded.flush()
    _user(seeded, "itx", "it_admin")  # it_admin has NO employee:resign
    tok = _login(client, "itx")
    assert client.post(f"/api/v1/employees/{emp.id}/resign", headers=_h(tok),
                       json={"resign_date": date.today().isoformat()}).json()["code"] == 1003
```

- [ ] **Step 2: Run test to verify it fails** → FAIL.

- [ ] **Step 3: Add ResignReq schema**

Add to `backend/app/schemas/employee.py`:
```python
from datetime import date as _date


class ResignReq(BaseModel):
    resign_date: _date | None = None
```
> `date` is already imported in employee.py as `from datetime import date`; reuse it — do NOT double-import. Add `class ResignReq(BaseModel): resign_date: date | None = None` using the existing `date` import.

- [ ] **Step 4: Implement resign in employee_service**

Add to `backend/app/services/employee_service.py` (import the asset repos + constants at top):
```python
from datetime import date

from app.core.constants import WorkstationStatus, DeviceStatus
from app.repositories import workstation_repo, device_repo, assignment_repo, user_repo
from sqlalchemy import select, update
from app.models import Workstation, Device, User


def resign(db: Session, user: CurrentUser, id_: str, resign_date, req: Request) -> dict:
    emp = employee_repo.get_active(db, id_)
    if emp is None:
        raise not_found("员工不存在")
    day = resign_date or date.today()

    # 1) release occupied workstations
    ws_ids = db.execute(
        select(Workstation.id).where(Workstation.current_employee_id == id_,
                                     Workstation.deleted_at.is_(None))
    ).scalars().all()
    released = 0
    for wid in ws_ids:
        if workstation_repo.release_if_occupied(db, wid, user.id) == 1:
            assignment_repo.close_ws_open(db, wid, day)
            released += 1

    # 2) return in-use devices
    dev_ids = db.execute(
        select(Device.id).where(Device.current_employee_id == id_, Device.deleted_at.is_(None))
    ).scalars().all()
    returned = 0
    for did in dev_ids:
        if device_repo.return_if_in_use(db, did, user.id) == 1:
            assignment_repo.close_dev_open(db, did, day)
            returned += 1

    # 3) mark employee resigned
    emp.status = 0
    emp.resign_date = day
    emp.updated_by = user.id

    # 4) disable bound accounts
    disabled = db.execute(
        update(User).where(User.employee_id == id_, User.deleted_at.is_(None)).values(status=0)
    ).rowcount
    account_disabled = disabled > 0

    operation_log_repo.create(db, user_id=user.id, module="employee", action="resign",
                              target_type="employee", target_id=id_,
                              detail={"released_workstations": released, "returned_devices": returned,
                                      "account_disabled": account_disabled},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"released_workstations": released, "returned_devices": returned,
            "account_disabled": account_disabled}
```
> Note: `_ip`/`_ua` helpers already exist in employee_service.py (slice 2). Reuse them. Add the new imports at the top of the file, avoiding duplicates.

- [ ] **Step 5: Add resign endpoint**

Add to `backend/app/routers/employees.py`:
```python
from app.schemas.employee import ResignReq
...

@router.post("/{id_}/resign")
def resign(id_: str, body: ResignReq, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("employee:resign"))):
    return envelope(data=employee_service.resign(db, user, id_, body.resign_date, request),
                    message="离职处理完成")
```
> Ensure `Request` is imported in employees.py (it is, from slice 2).

- [ ] **Step 6: Run tests + full suite + ruff**

Run: `pytest tests/test_resign.py -v` → PASS (2).
Run: `pytest -v` → all green (report total), 0 warnings.
Run: `ruff check .` → all checks passed (fix any unused imports with `ruff check . --fix`, re-run suite if it changed anything).

- [ ] **Step 7: Commit**
```bash
git add backend/app/services/employee_service.py backend/app/routers/employees.py backend/app/schemas/employee.py backend/tests/test_resign.py
git commit -m "$(cat <<'EOF'
feat(emp): resign cascade — release workstations, return devices, disable account (single tx)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (against spec)

**Spec coverage:** workstation CRUD/assign/release/batch/status/history (T2-3); device CRUD/checkout/return/repair/scrap/history (T4-5); optimistic lock + 3001 conflict (T2/T4 repos, T3/T5 services); asset data-scope incl. idle-invisible (T1 scope + repos + service _visible); resign cascade single-tx (T6); new codes 3001/3007 (T1); permission guards per §3.2 incl. hr-no-device (tests). Excluded (reports/import-export/system-admin/celery) absent.

**Placeholder scan:** none — real code + commands throughout.

**Type consistency:** `asset_scope` dict shape `{"mode":...}` consumed by `apply_current_employee_scope` and both services' `_visible`; `assign_if_free`/`checkout_if_available` return rowcount int checked for 0→conflict; `release_if_occupied`/`return_if_in_use` return rowcount; `assignment_repo.close_ws_open`/`close_dev_open` return rowcount; resign returns the documented `{released_workstations, returned_devices, account_disabled}`.

**Known choices:** version optional (service reads current if absent); batch-release counts successes; state machine via constants (not dict).
