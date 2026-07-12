# 切片2（组织域：部门 + 员工）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implement department + employee management endpoints with delete pre-checks, parent/supervisor cycle prevention, and the first working row-level data-scope filtering (dept_manager subtree / employee self), on top of the merged slice-1 foundation.

**Architecture:** Same four-layer FastAPI (api→routers→services→repositories→models). Data-scope: `deps.data_scope_descriptor` (slice 1) → `scope_service` resolves it into concrete filters (unrestricted / department-id set / self-employee-id) → repositories apply them in queries. Services own transactions + operation logging + cycle checks + delete pre-checks. Tables already exist (slice-1 migration); no schema change.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, MySQL 8 (PyMySQL), Redis, Pydantic v2, pytest. venv at `backend/.venv`.

## Global Constraints

- Work in `backend/`; venv at `backend/.venv` (`source .venv/Scripts/activate`). Never global Python.
- MySQL 8 only; app DB `ims`, test DB `ims_test`. Redis test DB is dedicated (conftest). No schema/migration changes in this slice (tables exist).
- Unified response envelope `{code,message,data,trace_id}`; error ranges 1xxx/2xxx/3xxx/5xxx. New codes: 3002 (dept has children/active employees), 3003 (dept parent cycle), 3004 (employee supervisor cycle), 3005 (unique conflict), 3404 (not found, HTTP 404).
- API prefix `/api/v1`. Every endpoint guarded by `require_permission(<code>)` per the spec table. Write ops record `operation_logs` and set `created_by`/`updated_by`.
- Data-scope: `all`→no filter; `dept`→department_id ∈ subtree(own dept + descendants), None own-dept ⇒ zero rows; `self`→only own employee, None ⇒ zero rows. Out-of-scope single-resource access ⇒ `not_found()` (3404).
- Soft delete via `deleted_at`; all reads exclude soft-deleted rows.
- TDD: failing test → run → implement → run → commit. Commit trailer `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.
- Tests hit real `ims_test`; use the slice-1 `db`/`client` fixtures and `seed_service.run_seed(db)` to obtain the 5 built-in roles + permission matrix.

Existing interfaces you build on (verified):
- `app.core.deps`: `CurrentUser(id, username, role_code, data_scope, permissions, employee_id, department_id)`, `get_current_user`, `require_permission(code)`, `data_scope_descriptor(user)->dict`.
- `app.core.exceptions`: `BizError(code,message,http_status)`, `unauthorized/account_locked/forbidden/biz`, `register_exception_handlers`.
- `app.core.response.envelope(data=None, message="ok", code=0)`.
- `app.schemas.common`: `PageParams(page,page_size,sort,order,keyword)`, `paginate(items,total,params)`.
- `app.repositories.base`: `get_by_id(db,model,id_)`, `get_active(db,model,id_)`.
- `app.repositories.operation_log_repo.create(db,*,user_id,module,action,target_type=None,target_id=None,detail=None,ip=None,user_agent=None)`.
- `app.services.seed_service.run_seed(db)` seeds roles/permissions/dicts (+admin).
- Models: `Department(id,name,parent_id,manager_id,sort_order,status,created_by,updated_by,created_at,updated_at,deleted_at)`, `Employee(id,employee_no,name,gender,email,phone,department_id,direct_supervisor_id,position,hire_date,resign_date,status,created_by,updated_by,...,deleted_at)`.
- `app.api.v1.api_router` (include new routers here).

---

### Task 1: not_found helper + department repository

**Files:**
- Modify: `backend/app/core/exceptions.py` (add `not_found`)
- Create: `backend/app/repositories/department_repo.py`
- Create: `backend/tests/test_department_repo.py`

**Interfaces:**
- Produces: `exceptions.not_found(message="资源不存在") -> BizError(3404, message, 404)`.
- `department_repo`:
  - `get_active(db, id_) -> Department | None` (not soft-deleted)
  - `list_active(db) -> list[Department]` (all non-deleted, ordered by sort_order, id)
  - `all_id_parent_rows(db) -> list[tuple[str, str|None]]` (id, parent_id) for non-deleted — for subtree computation
  - `has_active_children(db, id_) -> bool`
  - `has_active_employees(db, id_) -> bool` (employees with department_id=id_, status/deleted filtered: any non-deleted employee)
  - `create(db, **fields) -> Department`; `soft_delete(db, dept) -> None`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_department_repo.py`:
```python
from app.models import Department, Employee
from app.repositories import department_repo
from app.core.exceptions import not_found, BizError


def test_not_found_helper():
    e = not_found()
    assert isinstance(e, BizError) and e.code == 3404 and e.http_status == 404


def _dept(db, name, parent_id=None):
    d = department_repo.create(db, name=name, parent_id=parent_id, sort_order=0, status=1)
    db.flush()
    return d


def test_list_and_rows(db):
    a = _dept(db, "A")
    b = _dept(db, "B", parent_id=a.id)
    rows = department_repo.all_id_parent_rows(db)
    assert (a.id, None) in rows and (b.id, a.id) in rows


def test_has_active_children(db):
    a = _dept(db, "A")
    assert department_repo.has_active_children(db, a.id) is False
    _dept(db, "B", parent_id=a.id)
    assert department_repo.has_active_children(db, a.id) is True


def test_has_active_employees(db):
    a = _dept(db, "A")
    assert department_repo.has_active_employees(db, a.id) is False
    db.add(Employee(employee_no="E1", name="x", gender=1, department_id=a.id, status=1))
    db.flush()
    assert department_repo.has_active_employees(db, a.id) is True


def test_soft_delete(db):
    a = _dept(db, "A")
    department_repo.soft_delete(db, a)
    db.flush()
    assert department_repo.get_active(db, a.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_department_repo.py -v`
Expected: FAIL — module/function not found.

- [ ] **Step 3: Implement not_found + department_repo**

Add to `backend/app/core/exceptions.py` (after `forbidden`):
```python
def not_found(message: str = "资源不存在") -> BizError:
    return BizError(3404, message, 404)
```

Create `backend/app/repositories/department_repo.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Department, Employee


def get_active(db: Session, id_: str) -> Department | None:
    stmt = select(Department).where(Department.id == id_, Department.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def list_active(db: Session) -> list[Department]:
    stmt = (
        select(Department)
        .where(Department.deleted_at.is_(None))
        .order_by(Department.sort_order, Department.id)
    )
    return list(db.execute(stmt).scalars().all())


def all_id_parent_rows(db: Session) -> list[tuple[str, str | None]]:
    stmt = select(Department.id, Department.parent_id).where(Department.deleted_at.is_(None))
    return [(r[0], r[1]) for r in db.execute(stmt).all()]


def has_active_children(db: Session, id_: str) -> bool:
    stmt = select(func.count()).select_from(Department).where(
        Department.parent_id == id_, Department.deleted_at.is_(None)
    )
    return db.execute(stmt).scalar_one() > 0


def has_active_employees(db: Session, id_: str) -> bool:
    stmt = select(func.count()).select_from(Employee).where(
        Employee.department_id == id_, Employee.deleted_at.is_(None)
    )
    return db.execute(stmt).scalar_one() > 0


def create(db: Session, **fields) -> Department:
    dept = Department(**fields)
    db.add(dept)
    return dept


def soft_delete(db: Session, dept: Department) -> None:
    dept.deleted_at = datetime.now(timezone.utc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_department_repo.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/exceptions.py backend/app/repositories/department_repo.py backend/tests/test_department_repo.py
git commit -m "$(cat <<'EOF'
feat(dept): not_found helper and department repository

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: scope service (resolve data-scope descriptor into filters)

**Files:**
- Create: `backend/app/services/scope_service.py`
- Create: `backend/tests/test_scope_service.py`

**Interfaces:**
- Consumes: `deps.data_scope_descriptor`, `department_repo.all_id_parent_rows`, `utils.tree.descendant_ids`, `CurrentUser`.
- Produces:
  - `accessible_department_ids(db, user) -> set[str] | None`: `None` = unrestricted (scope all); a set (possibly empty) for dept scope = own dept + descendants; for self scope returns a set — but departments aren't used by self-scope roles, so return empty set (employee has no dept access anyway).
  - `employee_scope(db, user) -> dict`: one of `{"mode":"all"}`, `{"mode":"dept","dept_ids":set[str]}`, `{"mode":"self","employee_id":str|None}`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_scope_service.py`:
```python
from app.core.deps import CurrentUser
from app.repositories import department_repo
from app.services import scope_service


def _u(scope, dept=None, emp=None):
    return CurrentUser(id="u", username="x", role_code="r", data_scope=scope,
                       permissions=set(), employee_id=emp, department_id=dept)


def test_all_scope_unrestricted(db):
    assert scope_service.accessible_department_ids(db, _u("all")) is None
    assert scope_service.employee_scope(db, _u("all")) == {"mode": "all"}


def test_dept_scope_subtree(db):
    a = department_repo.create(db, name="A", sort_order=0, status=1); db.flush()
    b = department_repo.create(db, name="B", parent_id=a.id, sort_order=0, status=1); db.flush()
    c = department_repo.create(db, name="C", sort_order=0, status=1); db.flush()
    ids = scope_service.accessible_department_ids(db, _u("dept", dept=a.id))
    assert ids == {a.id, b.id}
    assert c.id not in ids
    es = scope_service.employee_scope(db, _u("dept", dept=a.id))
    assert es["mode"] == "dept" and es["dept_ids"] == {a.id, b.id}


def test_dept_scope_none_department_is_empty(db):
    assert scope_service.accessible_department_ids(db, _u("dept", dept=None)) == set()
    assert scope_service.employee_scope(db, _u("dept", dept=None))["dept_ids"] == set()


def test_self_scope(db):
    es = scope_service.employee_scope(db, _u("self", emp="e-1"))
    assert es == {"mode": "self", "employee_id": "e-1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scope_service.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement scope_service**

Create `backend/app/services/scope_service.py`:
```python
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, data_scope_descriptor
from app.repositories import department_repo
from app.utils.tree import descendant_ids


def accessible_department_ids(db: Session, user: CurrentUser) -> set[str] | None:
    desc = data_scope_descriptor(user)
    if desc["scope"] == "all":
        return None
    if desc["scope"] == "dept":
        dept_id = desc.get("department_id")
        if not dept_id:
            return set()
        rows = department_repo.all_id_parent_rows(db)
        return descendant_ids(rows, dept_id)
    # self scope has no department visibility
    return set()


def employee_scope(db: Session, user: CurrentUser) -> dict:
    desc = data_scope_descriptor(user)
    if desc["scope"] == "all":
        return {"mode": "all"}
    if desc["scope"] == "self":
        return {"mode": "self", "employee_id": desc.get("employee_id")}
    ids = accessible_department_ids(db, user) or set()
    return {"mode": "dept", "dept_ids": ids}
```
> Redis caching of the subtree is intentionally deferred (spec §10). The DB read + `descendant_ids` is the single source here; a later slice can wrap `all_id_parent_rows` with a cache + invalidation on department writes.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scope_service.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/scope_service.py backend/tests/test_scope_service.py
git commit -m "$(cat <<'EOF'
feat(scope): resolve data-scope descriptor into department/employee filters

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Department schemas, service, router (CRUD + tree + delete precheck + cycle + data-scope)

**Files:**
- Create: `backend/app/schemas/department.py`
- Create: `backend/app/services/department_service.py`
- Create: `backend/app/routers/departments.py`
- Modify: `backend/app/api/v1.py` (include departments router)
- Create: `backend/tests/test_departments.py`

**Interfaces:**
- Consumes: department_repo, scope_service, operation_log_repo, deps (`get_current_user`, `require_permission`), exceptions, envelope.
- Produces endpoints under `/api/v1/departments`: `GET /tree`, `GET ""`, `GET /{id}`, `POST ""`, `PUT /{id}`, `DELETE /{id}`.
- `department_service`: `get_tree(db, user)`, `list(db, user)`, `get_one(db, user, id_)`, `create(db, user, data, req)`, `update(db, user, id_, data, req)`, `delete(db, user, id_, req)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_departments.py`:
```python
import pytest

from app.models import Role, Employee, User
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
    db.add(u); db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_department_crud_and_tree_as_admin(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    # create root + child
    r = client.post("/api/v1/departments", headers=_h(tok), json={"name": "总部"})
    assert r.json()["code"] == 0
    root_id = r.json()["data"]["id"]
    c = client.post("/api/v1/departments", headers=_h(tok),
                    json={"name": "研发部", "parent_id": root_id})
    assert c.json()["code"] == 0
    tree = client.get("/api/v1/departments/tree", headers=_h(tok)).json()["data"]
    assert tree[0]["name"] == "总部" and tree[0]["children"][0]["name"] == "研发部"


def test_delete_blocked_by_children(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    root_id = client.post("/api/v1/departments", headers=_h(tok), json={"name": "A"}).json()["data"]["id"]
    client.post("/api/v1/departments", headers=_h(tok), json={"name": "B", "parent_id": root_id})
    r = client.delete(f"/api/v1/departments/{root_id}", headers=_h(tok))
    assert r.json()["code"] == 3002


def test_delete_blocked_by_employees(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    did = client.post("/api/v1/departments", headers=_h(tok), json={"name": "A"}).json()["data"]["id"]
    seeded.add(Employee(employee_no="E9", name="y", gender=1, department_id=did, status=1)); seeded.flush()
    r = client.delete(f"/api/v1/departments/{did}", headers=_h(tok))
    assert r.json()["code"] == 3002


def test_update_parent_cycle_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    a = client.post("/api/v1/departments", headers=_h(tok), json={"name": "A"}).json()["data"]["id"]
    b = client.post("/api/v1/departments", headers=_h(tok), json={"name": "B", "parent_id": a}).json()["data"]["id"]
    # make A's parent = B (B is A's descendant) -> cycle
    r = client.put(f"/api/v1/departments/{a}", headers=_h(tok), json={"parent_id": b})
    assert r.json()["code"] == 3003


def test_dept_manager_sees_only_subtree(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    boss = _login(client, "boss")
    a = client.post("/api/v1/departments", headers=_h(boss), json={"name": "A"}).json()["data"]["id"]
    b = client.post("/api/v1/departments", headers=_h(boss), json={"name": "B", "parent_id": a}).json()["data"]["id"]
    other = client.post("/api/v1/departments", headers=_h(boss), json={"name": "Other"}).json()["data"]["id"]
    # a manager employee in dept A
    mgr_emp = Employee(employee_no="M1", name="mgr", gender=1, department_id=a, status=1)
    seeded.add(mgr_emp); seeded.flush()
    _make_user(seeded, "mgr", "dept_manager", employee_id=mgr_emp.id)
    tok = _login(client, "mgr")
    listing = client.get("/api/v1/departments", headers=_h(tok)).json()["data"]["items"]
    names = {d["name"] for d in listing}
    assert names == {"A", "B"}  # not "Other"
    # out-of-scope detail -> 404 (3404)
    assert client.get(f"/api/v1/departments/{other}", headers=_h(tok)).json()["code"] == 3404


def test_employee_role_has_no_department_access(client, seeded):
    emp = Employee(employee_no="P1", name="p", gender=1, status=1)
    seeded.add(emp); seeded.flush()
    _make_user(seeded, "self1", "employee", employee_id=emp.id)
    tok = _login(client, "self1")
    assert client.get("/api/v1/departments", headers=_h(tok)).json()["code"] == 1003
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_departments.py -v`
Expected: FAIL — schemas/service/router not found (404/import errors).

- [ ] **Step 3: Implement schemas**

Create `backend/app/schemas/department.py`:
```python
from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    parent_id: str | None = None
    manager_id: str | None = None
    sort_order: int = 0
    status: int = 1


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    parent_id: str | None = None
    manager_id: str | None = None
    sort_order: int | None = None
    status: int | None = None


class DepartmentOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    manager_id: str | None
    sort_order: int
    status: int
```

- [ ] **Step 4: Implement department_service**

Create `backend/app/services/department_service.py`:
```python
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found
from app.models import Department
from app.repositories import department_repo, operation_log_repo
from app.services import scope_service
from app.utils.tree import descendant_ids


def _visible(db: Session, user: CurrentUser, dept: Department) -> bool:
    ids = scope_service.accessible_department_ids(db, user)
    return ids is None or dept.id in ids


def _to_out(d: Department) -> dict:
    return {"id": d.id, "name": d.name, "parent_id": d.parent_id,
            "manager_id": d.manager_id, "sort_order": d.sort_order, "status": d.status}


def list_departments(db: Session, user: CurrentUser) -> list[dict]:
    ids = scope_service.accessible_department_ids(db, user)
    rows = department_repo.list_active(db)
    if ids is not None:
        rows = [d for d in rows if d.id in ids]
    return [_to_out(d) for d in rows]


def get_tree(db: Session, user: CurrentUser) -> list[dict]:
    ids = scope_service.accessible_department_ids(db, user)
    rows = department_repo.list_active(db)
    if ids is not None:
        rows = [d for d in rows if d.id in ids]
    by_parent: dict = {}
    for d in rows:
        by_parent.setdefault(d.parent_id, []).append(d)
    visible_ids = {d.id for d in rows}

    def build(parent_id):
        out = []
        for d in by_parent.get(parent_id, []):
            out.append({"id": d.id, "name": d.name, "sort_order": d.sort_order,
                        "status": d.status, "children": build(d.id)})
        return out

    # roots = nodes whose parent is None OR whose parent is not visible (subtree roots)
    roots = [d for d in rows if d.parent_id is None or d.parent_id not in visible_ids]
    result = []
    for d in roots:
        result.append({"id": d.id, "name": d.name, "sort_order": d.sort_order,
                       "status": d.status, "children": build(d.id)})
    return result


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    dept = department_repo.get_active(db, id_)
    if dept is None or not _visible(db, user, dept):
        raise not_found("部门不存在")
    return _to_out(dept)


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if data.parent_id and department_repo.get_active(db, data.parent_id) is None:
        raise biz(3002, "上级部门不存在")
    dept = department_repo.create(
        db, name=data.name, parent_id=data.parent_id, manager_id=data.manager_id,
        sort_order=data.sort_order, status=data.status,
        created_by=user.id, updated_by=user.id,
    )
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="department", action="create",
                              target_type="department", target_id=dept.id,
                              detail={"name": dept.name}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(dept)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    dept = department_repo.get_active(db, id_)
    if dept is None or not _visible(db, user, dept):
        raise not_found("部门不存在")
    if data.parent_id is not None:
        if data.parent_id == id_:
            raise biz(3003, "上级部门不能是自己或其下级")
        rows = department_repo.all_id_parent_rows(db)
        if data.parent_id in descendant_ids(rows, id_):
            raise biz(3003, "上级部门不能是自己或其下级")
        if department_repo.get_active(db, data.parent_id) is None:
            raise biz(3002, "上级部门不存在")
        dept.parent_id = data.parent_id
    for field in ("name", "manager_id", "sort_order", "status"):
        val = getattr(data, field)
        if val is not None:
            setattr(dept, field, val)
    dept.updated_by = user.id
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="department", action="update",
                              target_type="department", target_id=dept.id,
                              detail={"name": dept.name}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(dept)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    dept = department_repo.get_active(db, id_)
    if dept is None or not _visible(db, user, dept):
        raise not_found("部门不存在")
    if department_repo.has_active_children(db, id_):
        raise biz(3002, "部门下有子部门，不能删除")
    if department_repo.has_active_employees(db, id_):
        raise biz(3002, "部门下有在职员工，不能删除")
    department_repo.soft_delete(db, dept)
    operation_log_repo.create(db, user_id=user.id, module="department", action="delete",
                              target_type="department", target_id=id_,
                              detail={"name": dept.name}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None
```

- [ ] **Step 5: Implement router + wire it**

Create `backend/app/routers/departments.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("/tree")
def tree(db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission("department:view"))):
    return envelope(data=department_service.get_tree(db, user))


@router.get("")
def list_(db: Session = Depends(get_db), user: CurrentUser = Depends(require_permission("department:view"))):
    return envelope(data={"items": department_service.list_departments(db, user)})


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("department:view"))):
    return envelope(data=department_service.get_one(db, user, id_))


@router.post("")
def create(body: DepartmentCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("department:create"))):
    return envelope(data=department_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: DepartmentUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("department:update"))):
    return envelope(data=department_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("department:delete"))):
    department_service.delete(db, user, id_, request)
    return envelope(message="已删除")
```

Modify `backend/app/api/v1.py`:
```python
from fastapi import APIRouter

from app.core.config import settings
from app.routers.auth import router as auth_router
from app.routers.departments import router as departments_router

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(auth_router)
api_router.include_router(departments_router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_departments.py -v`
Expected: PASS (6 passed).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/department.py backend/app/services/department_service.py backend/app/routers/departments.py backend/app/api/v1.py backend/tests/test_departments.py
git commit -m "$(cat <<'EOF'
feat(dept): department CRUD, tree, delete pre-checks, parent-cycle guard, data-scope

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Employee repository (paginated filter + data-scope + create/update/delete/batch/dup-check)

**Files:**
- Create: `backend/app/repositories/employee_repo.py`
- Create: `backend/tests/test_employee_repo.py`

**Interfaces:**
- Produces `employee_repo`:
  - `get_active(db, id_) -> Employee | None`
  - `get_by_employee_no(db, no) -> Employee | None` (active only)
  - `paginate(db, *, params, department_id=None, status=None, scope) -> tuple[list[Employee], int]` where `scope` is the dict from `scope_service.employee_scope`.
  - `create(db, **fields) -> Employee`; `soft_delete(db, emp)`; `batch_set_department(db, ids, department_id) -> int`.
  - `supervisor_chain_has(db, start_supervisor_id, target_id) -> bool` (walk direct_supervisor_id upward from start; True if target encountered).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_employee_repo.py`:
```python
from app.models import Employee
from app.schemas.common import PageParams
from app.repositories import employee_repo


def _emp(db, no, name, dept=None, sup=None, status=1):
    e = employee_repo.create(db, employee_no=no, name=name, gender=1,
                             department_id=dept, direct_supervisor_id=sup, status=status)
    db.flush()
    return e


def test_paginate_keyword_and_filter_all_scope(db):
    _emp(db, "E1", "张三", dept="d1")
    _emp(db, "E2", "李四", dept="d2")
    items, total = employee_repo.paginate(
        db, params=PageParams(keyword="张"), scope={"mode": "all"})
    assert total == 1 and items[0].name == "张三"
    items, total = employee_repo.paginate(
        db, params=PageParams(), department_id="d2", scope={"mode": "all"})
    assert total == 1 and items[0].employee_no == "E2"


def test_paginate_dept_scope(db):
    _emp(db, "E1", "a", dept="d1")
    _emp(db, "E2", "b", dept="d2")
    items, total = employee_repo.paginate(
        db, params=PageParams(), scope={"mode": "dept", "dept_ids": {"d1"}})
    assert total == 1 and items[0].department_id == "d1"
    # empty dept set -> no rows
    _, total0 = employee_repo.paginate(db, params=PageParams(), scope={"mode": "dept", "dept_ids": set()})
    assert total0 == 0


def test_paginate_self_scope(db):
    e = _emp(db, "E1", "a")
    _emp(db, "E2", "b")
    items, total = employee_repo.paginate(
        db, params=PageParams(), scope={"mode": "self", "employee_id": e.id})
    assert total == 1 and items[0].id == e.id
    _, total0 = employee_repo.paginate(db, params=PageParams(), scope={"mode": "self", "employee_id": None})
    assert total0 == 0


def test_dup_check_and_batch_and_chain(db):
    a = _emp(db, "E1", "a")
    b = _emp(db, "E2", "b", sup=a.id)  # b's supervisor is a
    assert employee_repo.get_by_employee_no(db, "E1").id == a.id
    n = employee_repo.batch_set_department(db, [a.id, b.id], "dX")
    assert n == 2
    # chain: starting from b, walking up hits a
    assert employee_repo.supervisor_chain_has(db, b.id, a.id) is True
    assert employee_repo.supervisor_chain_has(db, a.id, b.id) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_employee_repo.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement employee_repo**

Create `backend/app/repositories/employee_repo.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import select, func, or_, false, update
from sqlalchemy.orm import Session

from app.models import Employee
from app.schemas.common import PageParams


def get_active(db: Session, id_: str) -> Employee | None:
    stmt = select(Employee).where(Employee.id == id_, Employee.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_by_employee_no(db: Session, no: str) -> Employee | None:
    stmt = select(Employee).where(Employee.employee_no == no, Employee.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def _apply_scope(stmt, scope: dict):
    mode = scope["mode"]
    if mode == "all":
        return stmt
    if mode == "self":
        eid = scope.get("employee_id")
        return stmt.where(Employee.id == eid) if eid else stmt.where(false())
    ids = scope.get("dept_ids") or set()
    return stmt.where(Employee.department_id.in_(ids)) if ids else stmt.where(false())


def paginate(db: Session, *, params: PageParams, department_id: str | None = None,
             status: int | None = None, scope: dict) -> tuple[list[Employee], int]:
    base = select(Employee).where(Employee.deleted_at.is_(None))
    base = _apply_scope(base, scope)
    if department_id:
        base = base.where(Employee.department_id == department_id)
    if status is not None:
        base = base.where(Employee.status == status)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(Employee.name.like(kw), Employee.employee_no.like(kw)))

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    order_col = Employee.created_at.desc() if params.order == "desc" else Employee.created_at.asc()
    stmt = base.order_by(order_col).offset((params.page - 1) * params.page_size).limit(params.page_size)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def create(db: Session, **fields) -> Employee:
    emp = Employee(**fields)
    db.add(emp)
    return emp


def soft_delete(db: Session, emp: Employee) -> None:
    emp.deleted_at = datetime.now(timezone.utc)


def batch_set_department(db: Session, ids: list[str], department_id: str | None) -> int:
    stmt = (update(Employee)
            .where(Employee.id.in_(ids), Employee.deleted_at.is_(None))
            .values(department_id=department_id))
    result = db.execute(stmt)
    return result.rowcount


def supervisor_chain_has(db: Session, start_supervisor_id: str, target_id: str) -> bool:
    seen: set[str] = set()
    current = start_supervisor_id
    while current is not None and current not in seen:
        if current == target_id:
            return True
        seen.add(current)
        emp = db.get(Employee, current)
        current = emp.direct_supervisor_id if emp else None
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_employee_repo.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/employee_repo.py backend/tests/test_employee_repo.py
git commit -m "$(cat <<'EOF'
feat(emp): employee repository with paginated filter, data-scope, batch, cycle walk

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Employee schemas, service, router (list/detail/create/update/delete/batch + cycle + dup + data-scope)

**Files:**
- Create: `backend/app/schemas/employee.py`
- Create: `backend/app/services/employee_service.py`
- Create: `backend/app/routers/employees.py`
- Modify: `backend/app/api/v1.py` (include employees router)
- Create: `backend/tests/test_employees.py`

**Interfaces:**
- Produces endpoints under `/api/v1/employees`: `GET ""` (paged), `GET /{id}`, `POST ""`, `PUT /{id}`, `DELETE /{id}`, `PATCH /batch-department`.
- `employee_service`: `list(db,user,params,department_id,status)`, `get_one(db,user,id_)`, `create(db,user,data,req)`, `update(db,user,id_,data,req)`, `delete(db,user,id_,req)`, `batch_department(db,user,data,req)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_employees.py`:
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


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _dept(db, name, parent=None):
    d = Department(name=name, parent_id=parent, sort_order=0, status=1)
    db.add(d); db.flush(); return d


def test_create_list_filter(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    d = _dept(seeded, "研发")
    r = client.post("/api/v1/employees", headers=_h(tok),
                    json={"employee_no": "E100", "name": "张三", "gender": 1, "department_id": d.id})
    assert r.json()["code"] == 0
    data = client.get("/api/v1/employees?keyword=张", headers=_h(tok)).json()["data"]
    assert data["total"] == 1 and data["items"][0]["name"] == "张三"


def test_duplicate_employee_no_rejected(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    body = {"employee_no": "E1", "name": "a", "gender": 1}
    assert client.post("/api/v1/employees", headers=_h(tok), json=body).json()["code"] == 0
    assert client.post("/api/v1/employees", headers=_h(tok), json=body).json()["code"] == 3005


def test_supervisor_cycle_rejected(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    a = client.post("/api/v1/employees", headers=_h(tok),
                    json={"employee_no": "A", "name": "a", "gender": 1}).json()["data"]["id"]
    b = client.post("/api/v1/employees", headers=_h(tok),
                    json={"employee_no": "B", "name": "b", "gender": 1, "direct_supervisor_id": a}).json()["data"]["id"]
    # set a's supervisor = b (b already reports to a) -> cycle
    r = client.put(f"/api/v1/employees/{a}", headers=_h(tok), json={"direct_supervisor_id": b})
    assert r.json()["code"] == 3004


def test_batch_department(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    d = _dept(seeded, "新部门")
    ids = [client.post("/api/v1/employees", headers=_h(tok),
                       json={"employee_no": f"N{i}", "name": f"n{i}", "gender": 1}).json()["data"]["id"]
           for i in range(2)]
    r = client.patch("/api/v1/employees/batch-department", headers=_h(tok),
                     json={"employee_ids": ids, "department_id": d.id})
    assert r.json()["code"] == 0 and r.json()["data"]["updated"] == 2


def test_dept_manager_scope_and_out_of_scope_404(client, seeded):
    _user(seeded, "hr", "hr_admin")
    hr = _login(client, "hr")
    a = _dept(seeded, "A"); b = _dept(seeded, "B", parent=a.id); other = _dept(seeded, "Other")
    mgr = Employee(employee_no="M", name="m", gender=1, department_id=a.id, status=1)
    seeded.add(mgr); seeded.flush()
    in_b = client.post("/api/v1/employees", headers=_h(hr),
                       json={"employee_no": "IB", "name": "inb", "gender": 1, "department_id": b.id}).json()["data"]["id"]
    out = client.post("/api/v1/employees", headers=_h(hr),
                      json={"employee_no": "OUT", "name": "o", "gender": 1, "department_id": other.id}).json()["data"]["id"]
    _user(seeded, "mgr", "dept_manager", employee_id=mgr.id)
    tok = _login(client, "mgr")
    data = client.get("/api/v1/employees", headers=_h(tok)).json()["data"]
    nos = {i["employee_no"] for i in data["items"]}
    assert "IB" in nos and "M" in nos and "OUT" not in nos
    assert client.get(f"/api/v1/employees/{out}", headers=_h(tok)).json()["code"] == 3404
    assert client.get(f"/api/v1/employees/{in_b}", headers=_h(tok)).json()["code"] == 0


def test_employee_self_scope(client, seeded):
    _user(seeded, "hr", "hr_admin")
    hr = _login(client, "hr")
    me = Employee(employee_no="SELF", name="me", gender=1, status=1)
    other = Employee(employee_no="OTH", name="oth", gender=1, status=1)
    seeded.add_all([me, other]); seeded.flush()
    _user(seeded, "self1", "employee", employee_id=me.id)
    tok = _login(client, "self1")
    data = client.get("/api/v1/employees", headers=_h(tok)).json()["data"]
    assert data["total"] == 1 and data["items"][0]["employee_no"] == "SELF"
    assert client.get(f"/api/v1/employees/{other.id}", headers=_h(tok)).json()["code"] == 3404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_employees.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement schemas**

Create `backend/app/schemas/employee.py`:
```python
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmployeeCreate(BaseModel):
    employee_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    gender: int
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    department_id: str | None = None
    direct_supervisor_id: str | None = None
    position: str | None = Field(default=None, max_length=64)
    hire_date: date | None = None

    @field_validator("gender")
    @classmethod
    def _g(cls, v: int) -> int:
        if v not in (0, 1, 2):
            raise ValueError("gender must be 0/1/2")
        return v


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    gender: int | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    department_id: str | None = None
    direct_supervisor_id: str | None = None
    position: str | None = Field(default=None, max_length=64)
    hire_date: date | None = None
    status: int | None = None

    @field_validator("gender")
    @classmethod
    def _g(cls, v):
        if v is not None and v not in (0, 1, 2):
            raise ValueError("gender must be 0/1/2")
        return v


class BatchDepartmentReq(BaseModel):
    employee_ids: list[str] = Field(min_length=1)
    department_id: str | None = None
```
> `EmailStr` requires the `email-validator` package. Add `email-validator` to `pyproject.toml` dependencies in this task (see Step 6 install note).

- [ ] **Step 4: Implement employee_service**

Create `backend/app/services/employee_service.py`:
```python
from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found
from app.models import Employee, Department
from app.repositories import employee_repo, department_repo, operation_log_repo
from app.services import scope_service


def _ip(req):
    return req.client.host if req and req.client else None


def _ua(req):
    return req.headers.get("User-Agent") if req else None


def _dept_name(db, dept_id):
    if not dept_id:
        return None
    d = department_repo.get_active(db, dept_id)
    return d.name if d else None


def _list_item(db, e: Employee) -> dict:
    return {"id": e.id, "employee_no": e.employee_no, "name": e.name,
            "department_name": _dept_name(db, e.department_id),
            "position": e.position, "status": e.status}


def _detail(db, e: Employee) -> dict:
    sup_name = None
    if e.direct_supervisor_id:
        sup = employee_repo.get_active(db, e.direct_supervisor_id)
        sup_name = sup.name if sup else None
    return {"id": e.id, "employee_no": e.employee_no, "name": e.name, "gender": e.gender,
            "email": e.email, "phone": e.phone, "department_id": e.department_id,
            "department_name": _dept_name(db, e.department_id),
            "direct_supervisor_id": e.direct_supervisor_id, "supervisor_name": sup_name,
            "position": e.position, "hire_date": e.hire_date.isoformat() if e.hire_date else None,
            "status": e.status}


def _visible(db, user, emp: Employee) -> bool:
    scope = scope_service.employee_scope(db, user)
    if scope["mode"] == "all":
        return True
    if scope["mode"] == "self":
        return emp.id == scope.get("employee_id")
    return emp.department_id in (scope.get("dept_ids") or set())


def list_employees(db: Session, user: CurrentUser, params, department_id, status) -> dict:
    scope = scope_service.employee_scope(db, user)
    items, total = employee_repo.paginate(db, params=params, department_id=department_id,
                                          status=status, scope=scope)
    return {"items": [_list_item(db, e) for e in items], "total": total,
            "page": params.page, "page_size": params.page_size}


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    emp = employee_repo.get_active(db, id_)
    if emp is None or not _visible(db, user, emp):
        raise not_found("员工不存在")
    return _detail(db, emp)


def _check_refs(db, department_id, supervisor_id):
    if department_id and department_repo.get_active(db, department_id) is None:
        raise biz(3002, "部门不存在")
    if supervisor_id and employee_repo.get_active(db, supervisor_id) is None:
        raise biz(3004, "直属上级不存在")


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if employee_repo.get_by_employee_no(db, data.employee_no) is not None:
        raise biz(3005, "工号已存在")
    _check_refs(db, data.department_id, data.direct_supervisor_id)
    emp = employee_repo.create(
        db, employee_no=data.employee_no, name=data.name, gender=data.gender,
        email=data.email, phone=data.phone, department_id=data.department_id,
        direct_supervisor_id=data.direct_supervisor_id, position=data.position,
        hire_date=data.hire_date, status=1, created_by=user.id, updated_by=user.id,
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "工号/邮箱/手机号已存在")
    operation_log_repo.create(db, user_id=user.id, module="employee", action="create",
                              target_type="employee", target_id=emp.id,
                              detail={"employee_no": emp.employee_no}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _detail(db, emp)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    emp = employee_repo.get_active(db, id_)
    if emp is None or not _visible(db, user, emp):
        raise not_found("员工不存在")
    if data.direct_supervisor_id is not None:
        if data.direct_supervisor_id == id_:
            raise biz(3004, "直属上级不能形成环")
        if employee_repo.get_active(db, data.direct_supervisor_id) is None:
            raise biz(3004, "直属上级不存在")
        # walking up from the new supervisor must not reach this employee
        if employee_repo.supervisor_chain_has(db, data.direct_supervisor_id, id_):
            raise biz(3004, "直属上级不能形成环")
        emp.direct_supervisor_id = data.direct_supervisor_id
    if data.department_id is not None:
        if data.department_id and department_repo.get_active(db, data.department_id) is None:
            raise biz(3002, "部门不存在")
        emp.department_id = data.department_id
    for field in ("name", "gender", "email", "phone", "position", "hire_date", "status"):
        val = getattr(data, field)
        if val is not None:
            setattr(emp, field, val)
    emp.updated_by = user.id
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise biz(3005, "邮箱/手机号已存在")
    operation_log_repo.create(db, user_id=user.id, module="employee", action="update",
                              target_type="employee", target_id=emp.id,
                              detail={"employee_no": emp.employee_no}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _detail(db, emp)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    emp = employee_repo.get_active(db, id_)
    if emp is None or not _visible(db, user, emp):
        raise not_found("员工不存在")
    employee_repo.soft_delete(db, emp)
    operation_log_repo.create(db, user_id=user.id, module="employee", action="delete",
                              target_type="employee", target_id=id_,
                              detail={"employee_no": emp.employee_no}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def batch_department(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if data.department_id and department_repo.get_active(db, data.department_id) is None:
        raise biz(3002, "部门不存在")
    n = employee_repo.batch_set_department(db, data.employee_ids, data.department_id)
    operation_log_repo.create(db, user_id=user.id, module="employee", action="batch_update",
                              target_type="employee", target_id=None,
                              detail={"ids": data.employee_ids, "department_id": data.department_id},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"updated": n}
```

- [ ] **Step 5: Implement router + wire it**

Create `backend/app/routers/employees.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, BatchDepartmentReq
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


@router.patch("/batch-department")
def batch_department(body: BatchDepartmentReq, request: Request, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require_permission("employee:update"))):
    return envelope(data=employee_service.batch_department(db, user, body, request))
```
> IMPORTANT: register the `/batch-department` route so it does not collide with `/{id_}`. Because it is a PATCH and the others are GET/PUT/DELETE, and FastAPI matches by method+path, `/batch-department` (PATCH) and `/{id_}` (PUT/DELETE) do not conflict. Keep `/batch-department` defined as shown.

Modify `backend/app/api/v1.py` to also include the employees router:
```python
from app.routers.employees import router as employees_router
...
api_router.include_router(employees_router)
```

- [ ] **Step 6: Install email-validator, run test**

Add `"email-validator>=2.0"` to `[project].dependencies` in `backend/pyproject.toml`, then:
```bash
pip install -e ".[dev]"
```
Run: `pytest tests/test_employees.py -v`
Expected: PASS (6 passed).

- [ ] **Step 7: Full suite + ruff**

Run: `pytest -v` (expect all prior slice-1 tests + slice-2 tests green) and `ruff check .` (clean).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/employee.py backend/app/services/employee_service.py backend/app/routers/employees.py backend/app/api/v1.py backend/pyproject.toml backend/tests/test_employees.py
git commit -m "$(cat <<'EOF'
feat(emp): employee CRUD, filters, supervisor-cycle guard, batch-department, data-scope

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (against spec)

**Spec coverage:** departments tree/list/detail/CRUD + delete pre-checks (Task 3); department parent cycle (Task 3); employees list/filter/detail/CRUD + batch-department (Tasks 4-5); supervisor cycle (Tasks 4-5); data-scope for departments (Task 3) and employees (Tasks 4-5) incl. out-of-scope 404; permission guards on every endpoint; operation logging on writes; new error codes 3002/3003/3004/3005/3404. Excluded (resign, import/export) correctly absent.

**Placeholder scan:** none — all steps have real code and commands.

**Type consistency:** `scope_service.employee_scope` returns `{"mode":...}` consumed identically by `employee_repo.paginate._apply_scope` and `employee_service._visible`; `accessible_department_ids` returns `set|None` consumed by department_service; `PageParams` reused from slice 1; `not_found()` (3404) used across both domains.

**Known deferrals:** Redis subtree cache (compute-from-DB now); resign/import/export (later slices).
