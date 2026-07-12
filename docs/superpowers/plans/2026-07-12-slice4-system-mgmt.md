# Slice 4: System Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the system-management domain — account CRUD/status/reset-password, role CRUD + permission assignment, read-only operation-log query, and data-dictionary CRUD with Redis cache — all gated behind `system:*` (super_admin only), per spec `docs/superpowers/specs/2026-07-12-slice4-system-mgmt-design.md`.

**Architecture:** Four independent sub-modules layered as router→service→repository over the existing (slice-1) tables. Follows established codebase patterns: services take `(db, user, ..., req)`, commit their own transaction, and write `operation_logs`; routers wrap responses in `envelope()` and gate with `require_permission(code)`. Data-dict reads go through a small Redis cache helper (`core/dict_cache.py`); the router injects the redis client (via `get_redis`) so tests can override it.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, MySQL 8, Redis 7 (redis-py, `decode_responses=True`), Pydantic v2, pytest, ruff.

## Global Constraints

- Python 3.11; run everything from `backend/` in the project venv.
- All new endpoints under prefix `/api/v1` (via `settings.api_prefix`); responses use `app.core.response.envelope`.
- Permission gating: `system:user` / `system:role` / `system:log` / `system:dict` — all super_admin-only per §3.2 (already seeded). `GET /dicts/{dict_type}` requires login only.
- Passwords: bcrypt via `app.core.security.hash_password`; **never** return `password_hash` in any response.
- Error codes (reuse, no new): `3002` referenced/undeletable, `3005` unique conflict, `3007` invalid-state, `3404` not-found, `1003` forbidden, `1001` unauthorized.
- Write operations record `operation_logs` (module=`user`/`role`/`dict`); reads do not.
- All tests run against `ims_test` via the `client`/`db`/`redis_conn` fixtures in `tests/conftest.py`; seed with `seed_service.run_seed`.
- ruff must be clean with 0 warnings at the end of the slice.
- Do not modify DB tables/migrations (schema is fixed from slice 1).

---

### Task 1: Account (Users) Management

**Files:**
- Create: `backend/app/schemas/user.py`
- Modify: `backend/app/repositories/user_repo.py` (add paginate/create/update helpers)
- Create: `backend/app/services/user_service.py`
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/api/v1.py` (mount users router)
- Test: `backend/tests/test_users.py`

**Interfaces:**
- Consumes: `hash_password` (`app.core.security`), `CurrentUser`/`require_permission` (`app.core.deps`), `operation_log_repo.create`, `role_repo` (existing `get_by_id`), `employee_repo.get_active`.
- Produces:
  - `user_repo.paginate(db, *, params, keyword=None, status=None, role_code=None) -> tuple[list[User], int]`
  - `user_repo.create(db, **fields) -> User`
  - `user_repo.soft_delete(db, user) -> None`
  - `user_repo.employee_bound_by(db, employee_id, exclude_user_id=None) -> User | None`
  - `user_service.{list_users,get_one,create,update,delete,set_status,reset_password}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_users.py`:

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
    db.add(u)
    db.flush()
    return u


def _login(client, username, password="Passw0rd"):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": password}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_super_creates_and_lists_user(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = _role_id(seeded, "hr_admin")
    r = client.post("/api/v1/users", headers=_h(tok),
                    json={"username": "hr1", "password": "Secret123", "role_id": rid})
    assert r.json()["code"] == 0
    assert "password_hash" not in r.json()["data"]
    listing = client.get("/api/v1/users", headers=_h(tok)).json()["data"]["items"]
    assert any(u["username"] == "hr1" for u in listing)


def test_duplicate_username_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = _role_id(seeded, "hr_admin")
    client.post("/api/v1/users", headers=_h(tok),
                json={"username": "dup", "password": "Secret123", "role_id": rid})
    r = client.post("/api/v1/users", headers=_h(tok),
                    json={"username": "dup", "password": "Secret123", "role_id": rid})
    assert r.json()["code"] == 3005


def test_bind_nonexistent_employee_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = _role_id(seeded, "employee")
    r = client.post("/api/v1/users", headers=_h(tok),
                    json={"username": "e1", "password": "Secret123", "role_id": rid,
                          "employee_id": "no-such-emp"})
    assert r.json()["code"] == 3002


def test_employee_already_bound_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    emp = Employee(employee_no="E1", name="a", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    rid = _role_id(seeded, "employee")
    client.post("/api/v1/users", headers=_h(tok),
                json={"username": "u1", "password": "Secret123", "role_id": rid, "employee_id": emp.id})
    r = client.post("/api/v1/users", headers=_h(tok),
                    json={"username": "u2", "password": "Secret123", "role_id": rid, "employee_id": emp.id})
    assert r.json()["code"] in (3002, 3005)


def test_cannot_disable_or_delete_self(client, seeded):
    boss = _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    assert client.patch(f"/api/v1/users/{boss.id}/status", headers=_h(tok),
                        json={"status": 0}).json()["code"] == 3007
    assert client.delete(f"/api/v1/users/{boss.id}", headers=_h(tok)).json()["code"] == 3007


def test_reset_password_revokes_old_token(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    victim = _make_user(seeded, "victim", "employee")
    boss = _login(client, "boss")
    victim_tok = _login(client, "victim")
    # victim's login-only token works BEFORE reset
    assert client.get("/api/v1/auth/me", headers=_h(victim_tok)).json()["code"] == 0
    r = client.post(f"/api/v1/users/{victim.id}/reset-password", headers=_h(boss),
                    json={"new_password": "Brandnew123"})
    assert r.json()["code"] == 0
    # old token now rejected (pwd_updated_at advanced past token iat)
    assert client.get("/api/v1/auth/me", headers=_h(victim_tok)).json()["code"] == 1001


def test_non_super_forbidden(client, seeded):
    _make_user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    assert client.get("/api/v1/users", headers=_h(tok)).json()["code"] == 1003
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_users.py -q`
Expected: FAIL (404/route missing — users router not mounted yet).

- [ ] **Step 3: Add repository helpers**

Append to `backend/app/repositories/user_repo.py` (keep existing functions; add imports at top):

```python
from sqlalchemy import select, func
from app.models import User, Role
from app.schemas.common import PageParams


def paginate(db: Session, *, params: PageParams, keyword: str | None = None,
             status: int | None = None, role_code: str | None = None) -> tuple[list[User], int]:
    base = select(User).where(User.deleted_at.is_(None))
    if keyword:
        base = base.where(User.username.like(f"%{keyword}%"))
    if status is not None:
        base = base.where(User.status == status)
    if role_code:
        base = base.join(Role, Role.id == User.role_id).where(Role.code == role_code)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = (base.order_by(User.created_at.desc())
            .offset((params.page - 1) * params.page_size).limit(params.page_size))
    return list(db.execute(stmt).scalars().all()), total


def create(db: Session, **fields) -> User:
    user = User(**fields)
    db.add(user)
    return user


def soft_delete(db: Session, user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)


def employee_bound_by(db: Session, employee_id: str, exclude_user_id: str | None = None) -> User | None:
    stmt = select(User).where(User.employee_id == employee_id, User.deleted_at.is_(None))
    if exclude_user_id:
        stmt = stmt.where(User.id != exclude_user_id)
    return db.execute(stmt).scalar_one_or_none()
```

Note: `user_repo.py` already imports `datetime, timezone` and `select`; ensure `func` and `Role` are imported (extend the existing import lines rather than duplicating). `set_password` already exists (used by reset).

- [ ] **Step 4: Add schemas**

Create `backend/app/schemas/user.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role_id: str
    employee_id: str | None = None
    status: int = 1


class UserUpdate(BaseModel):
    role_id: str | None = None
    employee_id: str | None = None
    status: int | None = None


class UserStatusReq(BaseModel):
    status: int = Field(ge=0, le=1)


class ResetPasswordReq(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    role_id: str
    role_code: str | None = None
    role_name: str | None = None
    employee_id: str | None = None
    status: int
    last_login_at: datetime | None = None
    created_at: datetime | None = None
```

- [ ] **Step 5: Add service**

Create `backend/app/services/user_service.py`:

```python
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found, invalid_state
from app.core.security import hash_password
from app.models import Role, User
from app.repositories import user_repo, role_repo, employee_repo, operation_log_repo
from app.schemas.common import PageParams, paginate


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None


def _to_out(db: Session, u: User) -> dict:
    role = role_repo.get_by_id(db, u.role_id)
    return {"id": u.id, "username": u.username, "role_id": u.role_id,
            "role_code": role.code if role else None,
            "role_name": role.name if role else None,
            "employee_id": u.employee_id, "status": u.status,
            "last_login_at": u.last_login_at, "created_at": u.created_at}


def _check_role(db: Session, role_id: str) -> Role:
    role = role_repo.get_by_id(db, role_id)
    if role is None:
        raise biz(3002, "角色不存在")
    return role


def _check_employee(db: Session, employee_id: str, exclude_user_id: str | None = None) -> None:
    if employee_repo.get_active(db, employee_id) is None:
        raise biz(3002, "绑定的员工不存在")
    if user_repo.employee_bound_by(db, employee_id, exclude_user_id) is not None:
        raise biz(3005, "该员工已绑定其他账号")


def list_users(db: Session, user: CurrentUser, params: PageParams,
               status: int | None, role_code: str | None) -> dict:
    rows, total = user_repo.paginate(db, params=params, keyword=params.keyword,
                                     status=status, role_code=role_code)
    return paginate([_to_out(db, u) for u in rows], total, params)


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    return _to_out(db, u)


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if user_repo.get_active_by_username(db, data.username) is not None:
        raise biz(3005, "用户名已存在")
    _check_role(db, data.role_id)
    if data.employee_id:
        _check_employee(db, data.employee_id)
    u = user_repo.create(db, username=data.username,
                         password_hash=hash_password(data.password),
                         role_id=data.role_id, employee_id=data.employee_id or None,
                         status=data.status)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="create",
                              target_type="user", target_id=u.id,
                              detail={"username": u.username}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(db, u)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    fields = data.model_fields_set
    if "role_id" in fields and data.role_id:
        _check_role(db, data.role_id)
        u.role_id = data.role_id
    if "employee_id" in fields:
        if data.employee_id:
            _check_employee(db, data.employee_id, exclude_user_id=u.id)
        u.employee_id = data.employee_id or None
    if "status" in fields and data.status is not None:
        u.status = data.status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="update",
                              target_type="user", target_id=u.id,
                              detail={"username": u.username}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(db, u)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    if u.id == user.id:
        raise invalid_state("不能删除自己的账号")
    user_repo.soft_delete(db, u)
    operation_log_repo.create(db, user_id=user.id, module="user", action="delete",
                              target_type="user", target_id=u.id,
                              detail={"username": u.username}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def set_status(db: Session, user: CurrentUser, id_: str, status: int, req: Request) -> dict:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    if u.id == user.id and status == 0:
        raise invalid_state("不能禁用自己的账号")
    u.status = status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="status",
                              target_type="user", target_id=u.id,
                              detail={"status": status}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(db, u)


def reset_password(db: Session, user: CurrentUser, id_: str, new_password: str, req: Request) -> None:
    u = user_repo.get_active_by_id(db, id_)
    if u is None:
        raise not_found("账号不存在")
    user_repo.set_password(db, u, hash_password(new_password))
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="user", action="reset_password",
                              target_type="user", target_id=u.id, detail=None,
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
```

- [ ] **Step 6: Add router + mount**

Create `backend/app/routers/users.py`:

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.user import UserCreate, UserUpdate, UserStatusReq, ResetPasswordReq
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          status: int | None = None, role_code: str | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:user"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=user_service.list_users(db, user, params, status, role_code))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.get_one(db, user, id_))


@router.post("")
def create(body: UserCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: UserUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:user"))):
    user_service.delete(db, user, id_, request)
    return envelope(message="已删除")


@router.patch("/{id_}/status")
def set_status(id_: str, body: UserStatusReq, request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require_permission("system:user"))):
    return envelope(data=user_service.set_status(db, user, id_, body.status, request))


@router.post("/{id_}/reset-password")
def reset_password(id_: str, body: ResetPasswordReq, request: Request, db: Session = Depends(get_db),
                   user: CurrentUser = Depends(require_permission("system:user"))):
    user_service.reset_password(db, user, id_, body.new_password, request)
    return envelope(message="密码已重置")
```

Modify `backend/app/api/v1.py` — add import and include:

```python
from app.routers.users import router as users_router
# ...
api_router.include_router(users_router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_users.py -q`
Expected: PASS (7 tests). The revocation test uses the existing login-only `GET /api/v1/auth/me` (returns our `{code:...}` envelope, so a revoked token yields `code==1001`).

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/schemas/user.py app/repositories/user_repo.py app/services/user_service.py app/routers/users.py app/api/v1.py tests/test_users.py
git commit -m "feat(system): user management — CRUD, status, reset-password with binding guards"
```

---

### Task 2: Role & Permission Management

**Files:**
- Create: `backend/app/schemas/role.py`
- Modify: `backend/app/repositories/role_repo.py` (add list/create/update/delete/set_permissions/users_count/get_by_code)
- Create: `backend/app/services/role_service.py`
- Create: `backend/app/routers/roles.py` (roles + `GET /permissions`)
- Modify: `backend/app/api/v1.py` (mount roles + permissions routers)
- Test: `backend/tests/test_roles.py`

**Interfaces:**
- Consumes: `permission_repo.list_all` / `get_by_code` (existing), `role_repo.permission_codes_for_role` (existing), `require_permission`.
- Produces:
  - `role_repo.list_all(db) -> list[Role]`
  - `role_repo.get_by_code(db, code) -> Role | None`
  - `role_repo.create(db, **fields) -> Role`
  - `role_repo.delete(db, role) -> None`
  - `role_repo.users_count(db, role_id) -> int`
  - `role_repo.set_permissions(db, role_id, permission_ids: set[str]) -> None`
  - `role_service.{list_roles,get_one,create,update,delete,get_permissions,assign_permissions,all_permissions}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_roles.py`:

```python
import pytest

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


def _make_user(db, username, role_code):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_create_custom_role(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.post("/api/v1/roles", headers=_h(tok),
                    json={"code": "auditor", "name": "审计员", "data_scope": "all"})
    assert r.json()["code"] == 0 and r.json()["data"]["is_builtin"] == 0


def test_duplicate_role_code_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.post("/api/v1/roles", headers=_h(tok),
                    json={"code": "hr_admin", "name": "x", "data_scope": "all"})
    assert r.json()["code"] == 3005


def test_builtin_role_scope_immutable(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = _role_id(seeded, "hr_admin")
    r = client.put(f"/api/v1/roles/{rid}", headers=_h(tok), json={"data_scope": "self"})
    assert r.json()["code"] == 3007


def test_delete_builtin_role_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = _role_id(seeded, "employee")
    assert client.delete(f"/api/v1/roles/{rid}", headers=_h(tok)).json()["code"] == 3007


def test_delete_role_in_use_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = client.post("/api/v1/roles", headers=_h(tok),
                      json={"code": "temp", "name": "临时", "data_scope": "all"}).json()["data"]["id"]
    _make_user(seeded, "tempuser", "temp")
    assert client.delete(f"/api/v1/roles/{rid}", headers=_h(tok)).json()["code"] == 3002


def test_delete_unused_custom_role(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = client.post("/api/v1/roles", headers=_h(tok),
                      json={"code": "gone", "name": "g", "data_scope": "all"}).json()["data"]["id"]
    assert client.delete(f"/api/v1/roles/{rid}", headers=_h(tok)).json()["code"] == 0


def test_assign_and_read_permissions(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = client.post("/api/v1/roles", headers=_h(tok),
                      json={"code": "viewer", "name": "查看", "data_scope": "all"}).json()["data"]["id"]
    client.put(f"/api/v1/roles/{rid}/permissions", headers=_h(tok),
               json={"codes": ["department:view", "employee:view"]})
    got = client.get(f"/api/v1/roles/{rid}/permissions", headers=_h(tok)).json()["data"]["codes"]
    assert set(got) == {"department:view", "employee:view"}


def test_assign_unknown_permission_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = client.post("/api/v1/roles", headers=_h(tok),
                      json={"code": "v2", "name": "v", "data_scope": "all"}).json()["data"]["id"]
    r = client.put(f"/api/v1/roles/{rid}/permissions", headers=_h(tok),
                   json={"codes": ["nonexistent:perm"]})
    assert r.json()["code"] == 3002


def test_super_admin_permissions_immutable(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    rid = _role_id(seeded, "super_admin")
    r = client.put(f"/api/v1/roles/{rid}/permissions", headers=_h(tok),
                   json={"codes": ["department:view"]})
    assert r.json()["code"] == 3007


def test_all_permissions_grouped(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    data = client.get("/api/v1/permissions", headers=_h(tok)).json()["data"]["items"]
    modules = {g["module"] for g in data}
    assert {"department", "employee", "workstation", "device", "report", "system"} <= modules


def test_non_super_forbidden(client, seeded):
    _make_user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    assert client.get("/api/v1/roles", headers=_h(tok)).json()["code"] == 1003
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_roles.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add repository helpers**

Append to `backend/app/repositories/role_repo.py` (existing file imports `select`, `Session`, `Role, RolePermission, Permission`; add `delete as sa_delete`, `func` to imports):

```python
from sqlalchemy import select, func, delete as sa_delete
from app.models import User  # add alongside existing model imports


def list_all(db: Session) -> list[Role]:
    return list(db.execute(select(Role).order_by(Role.created_at)).scalars().all())


def get_by_code(db: Session, code: str) -> Role | None:
    return db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()


def create(db: Session, **fields) -> Role:
    role = Role(**fields)
    db.add(role)
    return role


def delete(db: Session, role: Role) -> None:
    db.execute(sa_delete(RolePermission).where(RolePermission.role_id == role.id))
    db.delete(role)


def users_count(db: Session, role_id: str) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role_id == role_id, User.deleted_at.is_(None))
    return db.execute(stmt).scalar_one()


def set_permissions(db: Session, role_id: str, permission_ids: set[str]) -> None:
    db.execute(sa_delete(RolePermission).where(RolePermission.role_id == role_id))
    for pid in permission_ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))
```

- [ ] **Step 4: Add schemas**

Create `backend/app/schemas/role.py`:

```python
from pydantic import BaseModel, Field, field_validator


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    data_scope: str = "all"
    status: int = 1

    @field_validator("data_scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v not in ("all", "dept", "self"):
            raise ValueError("data_scope must be all/dept/self")
        return v


class RoleUpdate(BaseModel):
    name: str | None = None
    data_scope: str | None = None
    status: int | None = None

    @field_validator("data_scope")
    @classmethod
    def _scope(cls, v):
        if v is not None and v not in ("all", "dept", "self"):
            raise ValueError("data_scope must be all/dept/self")
        return v


class PermissionAssignReq(BaseModel):
    codes: list[str]


class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    is_builtin: int
    data_scope: str
    status: int
```

- [ ] **Step 5: Add service**

Create `backend/app/services/role_service.py`:

```python
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found, invalid_state
from app.models import Role
from app.repositories import role_repo, permission_repo, operation_log_repo


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None


def _to_out(r: Role) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name,
            "is_builtin": r.is_builtin, "data_scope": r.data_scope, "status": r.status}


def list_roles(db: Session, user: CurrentUser) -> dict:
    return {"items": [_to_out(r) for r in role_repo.list_all(db)]}


def get_one(db: Session, user: CurrentUser, id_: str) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    return _to_out(role)


def create(db: Session, user: CurrentUser, data, req: Request) -> dict:
    if role_repo.get_by_code(db, data.code) is not None:
        raise biz(3005, "角色编码已存在")
    role = role_repo.create(db, code=data.code, name=data.name, is_builtin=0,
                            data_scope=data.data_scope, status=data.status)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="create",
                              target_type="role", target_id=role.id,
                              detail={"code": role.code}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(role)


def update(db: Session, user: CurrentUser, id_: str, data, req: Request) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    fields = data.model_fields_set
    if role.is_builtin == 1 and (fields - {"name"}):
        raise invalid_state("内置角色仅允许修改名称")
    if "name" in fields and data.name is not None:
        role.name = data.name
    if "data_scope" in fields and data.data_scope is not None:
        role.data_scope = data.data_scope
    if "status" in fields and data.status is not None:
        role.status = data.status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="update",
                              target_type="role", target_id=role.id,
                              detail={"code": role.code}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return _to_out(role)


def delete(db: Session, user: CurrentUser, id_: str, req: Request) -> None:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    if role.is_builtin == 1:
        raise invalid_state("内置角色不可删除")
    if role_repo.users_count(db, role.id) > 0:
        raise biz(3002, "角色下有账号，不能删除")
    role_repo.delete(db, role)
    operation_log_repo.create(db, user_id=user.id, module="role", action="delete",
                              target_type="role", target_id=id_,
                              detail={"code": role.code}, ip=_ip(req), user_agent=_ua(req))
    db.commit()


def get_permissions(db: Session, user: CurrentUser, id_: str) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    return {"codes": sorted(role_repo.permission_codes_for_role(db, role.id))}


def assign_permissions(db: Session, user: CurrentUser, id_: str, codes: list[str], req: Request) -> dict:
    role = role_repo.get_by_id(db, id_)
    if role is None:
        raise not_found("角色不存在")
    if role.code == "super_admin":
        raise invalid_state("超级管理员权限不可修改")
    ids: set[str] = set()
    for code in set(codes):
        perm = permission_repo.get_by_code(db, code)
        if perm is None:
            raise biz(3002, f"权限点不存在: {code}")
        ids.add(perm.id)
    role_repo.set_permissions(db, role.id, ids)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="role", action="assign_permissions",
                              target_type="role", target_id=role.id,
                              detail={"codes": sorted(set(codes))}, ip=_ip(req), user_agent=_ua(req))
    db.commit()
    return {"codes": sorted(set(codes))}


def all_permissions(db: Session, user: CurrentUser) -> dict:
    perms = permission_repo.list_all(db)
    grouped: dict[str, list] = {}
    for p in perms:
        grouped.setdefault(p.module, []).append({"code": p.code, "name": p.name})
    items = [{"module": m, "permissions": grouped[m]} for m in sorted(grouped)]
    return {"items": items}
```

- [ ] **Step 6: Add router(s) + mount**

Create `backend/app/routers/roles.py`:

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.role import RoleCreate, RoleUpdate, PermissionAssignReq
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["roles"])
permissions_router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("")
def list_(db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.list_roles(db, user))


@router.get("/{id_}")
def get_one(id_: str, db: Session = Depends(get_db),
            user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.get_one(db, user, id_))


@router.post("")
def create(body: RoleCreate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.create(db, user, body, request))


@router.put("/{id_}")
def update(id_: str, body: RoleUpdate, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.update(db, user, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           user: CurrentUser = Depends(require_permission("system:role"))):
    role_service.delete(db, user, id_, request)
    return envelope(message="已删除")


@router.get("/{id_}/permissions")
def get_permissions(id_: str, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.get_permissions(db, user, id_))


@router.put("/{id_}/permissions")
def assign_permissions(id_: str, body: PermissionAssignReq, request: Request,
                       db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.assign_permissions(db, user, id_, body.codes, request))


@permissions_router.get("")
def all_permissions(db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require_permission("system:role"))):
    return envelope(data=role_service.all_permissions(db, user))
```

Modify `backend/app/api/v1.py`:

```python
from app.routers.roles import router as roles_router, permissions_router
# ...
api_router.include_router(roles_router)
api_router.include_router(permissions_router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_roles.py -q`
Expected: PASS (11 tests).

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/schemas/role.py app/repositories/role_repo.py app/services/role_service.py app/routers/roles.py app/api/v1.py tests/test_roles.py
git commit -m "feat(system): role CRUD + permission assignment with builtin/super guards"
```

---

### Task 3: Data Dictionary + Redis Cache

**Files:**
- Create: `backend/app/schemas/dict.py`
- Create: `backend/app/repositories/data_dict_repo.py`
- Create: `backend/app/core/dict_cache.py`
- Create: `backend/app/services/dict_service.py`
- Create: `backend/app/routers/dicts.py`
- Modify: `backend/app/core/config.py` (add `dict_cache_ttl`)
- Modify: `backend/app/api/v1.py` (mount dicts router)
- Test: `backend/tests/test_dicts.py`

**Interfaces:**
- Consumes: `get_redis` (`app.core.redis`), `get_current_user`/`require_permission`, `settings.dict_cache_ttl`.
- Produces:
  - `data_dict_repo.{list_by_type,paginate,get,get_by_type_key,create,delete}`
  - `dict_cache.{get_cached,set_cached,invalidate}` keyed `dict:{dict_type}`
  - `dict_service.{list_by_type,list_dicts,create,update,delete}`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_dicts.py`:

```python
import pytest

from app.models import Role, User, DataDict
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


def test_read_by_type_enabled_sorted(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    items = client.get("/api/v1/dicts/gender", headers=_h(tok)).json()["data"]["items"]
    keys = [i["dict_key"] for i in items]
    assert keys == ["0", "1", "2"]  # seeded gender, sorted by sort_order


def test_read_caches_and_invalidates(client, seeded, redis_conn):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    client.get("/api/v1/dicts/gender", headers=_h(tok))
    assert redis_conn.get("dict:gender") is not None
    # a write to this type invalidates the cache key
    client.post("/api/v1/dicts", headers=_h(tok),
                json={"dict_type": "gender", "dict_key": "9", "dict_label": "其他", "sort_order": 9})
    assert redis_conn.get("dict:gender") is None


def test_duplicate_type_key_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.post("/api/v1/dicts", headers=_h(tok),
                    json={"dict_type": "gender", "dict_key": "1", "dict_label": "dup"})
    assert r.json()["code"] == 3005


def test_update_and_delete(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    did = client.post("/api/v1/dicts", headers=_h(tok),
                      json={"dict_type": "color", "dict_key": "r", "dict_label": "红"}).json()["data"]["id"]
    assert client.put(f"/api/v1/dicts/{did}", headers=_h(tok),
                      json={"dict_label": "大红"}).json()["data"]["dict_label"] == "大红"
    assert client.delete(f"/api/v1/dicts/{did}", headers=_h(tok)).json()["code"] == 0


def test_list_paginated_super_only(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    data = client.get("/api/v1/dicts?dict_type=gender", headers=_h(tok)).json()["data"]
    assert data["total"] >= 3 and "items" in data


def test_employee_can_read_type_but_not_manage(client, seeded):
    from app.models import Employee
    emp = Employee(employee_no="E1", name="a", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    assert client.get("/api/v1/dicts/gender", headers=_h(tok)).json()["code"] == 0
    assert client.get("/api/v1/dicts", headers=_h(tok)).json()["code"] == 1003
    assert client.post("/api/v1/dicts", headers=_h(tok),
                       json={"dict_type": "x", "dict_key": "y", "dict_label": "z"}).json()["code"] == 1003
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_dicts.py -q`
Expected: FAIL (routes missing).

- [ ] **Step 3: Add config setting**

Modify `backend/app/core/config.py` — add after `login_lock_minutes`:

```python
    dict_cache_ttl: int = 600
```

- [ ] **Step 4: Add repository**

Create `backend/app/repositories/data_dict_repo.py`:

```python
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.models import DataDict
from app.schemas.common import PageParams


def list_by_type(db: Session, dict_type: str) -> list[DataDict]:
    stmt = (select(DataDict)
            .where(DataDict.dict_type == dict_type, DataDict.status == 1)
            .order_by(DataDict.sort_order.asc()))
    return list(db.execute(stmt).scalars().all())


def paginate(db: Session, *, params: PageParams,
             dict_type: str | None = None) -> tuple[list[DataDict], int]:
    base = select(DataDict)
    if dict_type:
        base = base.where(DataDict.dict_type == dict_type)
    if params.keyword:
        kw = f"%{params.keyword}%"
        base = base.where(or_(DataDict.dict_key.like(kw), DataDict.dict_label.like(kw)))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    stmt = (base.order_by(DataDict.dict_type.asc(), DataDict.sort_order.asc())
            .offset((params.page - 1) * params.page_size).limit(params.page_size))
    return list(db.execute(stmt).scalars().all()), total


def get(db: Session, id_: str) -> DataDict | None:
    return db.get(DataDict, id_)


def get_by_type_key(db: Session, dict_type: str, dict_key: str) -> DataDict | None:
    stmt = select(DataDict).where(DataDict.dict_type == dict_type, DataDict.dict_key == dict_key)
    return db.execute(stmt).scalar_one_or_none()


def create(db: Session, **fields) -> DataDict:
    d = DataDict(**fields)
    db.add(d)
    return d


def delete(db: Session, d: DataDict) -> None:
    db.delete(d)
```

- [ ] **Step 5: Add cache helper**

Create `backend/app/core/dict_cache.py`:

```python
import json


def _key(dict_type: str) -> str:
    return f"dict:{dict_type}"


def get_cached(redis, dict_type: str) -> list[dict] | None:
    raw = redis.get(_key(dict_type))
    return json.loads(raw) if raw else None


def set_cached(redis, dict_type: str, items: list[dict], ttl: int) -> None:
    redis.set(_key(dict_type), json.dumps(items, ensure_ascii=False), ex=ttl)


def invalidate(redis, dict_type: str) -> None:
    redis.delete(_key(dict_type))
```

- [ ] **Step 6: Add schemas**

Create `backend/app/schemas/dict.py`:

```python
from pydantic import BaseModel, Field


class DictCreate(BaseModel):
    dict_type: str = Field(min_length=1, max_length=32)
    dict_key: str = Field(min_length=1, max_length=32)
    dict_label: str = Field(min_length=1, max_length=64)
    sort_order: int = 0
    status: int = 1


class DictUpdate(BaseModel):
    dict_label: str | None = None
    sort_order: int | None = None
    status: int | None = None


class DictOut(BaseModel):
    id: str
    dict_type: str
    dict_key: str
    dict_label: str
    sort_order: int
    status: int
```

- [ ] **Step 7: Add service**

Create `backend/app/services/dict_service.py`:

```python
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser
from app.core.exceptions import biz, not_found
from app.core import dict_cache
from app.models import DataDict
from app.repositories import data_dict_repo, operation_log_repo
from app.schemas.common import PageParams, paginate


def _ip(req: Request) -> str | None:
    return req.client.host if req and req.client else None


def _ua(req: Request) -> str | None:
    return req.headers.get("User-Agent") if req else None


def _to_out(d: DataDict) -> dict:
    return {"id": d.id, "dict_type": d.dict_type, "dict_key": d.dict_key,
            "dict_label": d.dict_label, "sort_order": d.sort_order, "status": d.status}


def list_by_type(db: Session, redis, dict_type: str) -> dict:
    cached = dict_cache.get_cached(redis, dict_type)
    if cached is not None:
        return {"items": cached}
    rows = data_dict_repo.list_by_type(db, dict_type)
    items = [{"dict_key": r.dict_key, "dict_label": r.dict_label, "sort_order": r.sort_order}
             for r in rows]
    dict_cache.set_cached(redis, dict_type, items, settings.dict_cache_ttl)
    return {"items": items}


def list_dicts(db: Session, user: CurrentUser, params: PageParams, dict_type: str | None) -> dict:
    rows, total = data_dict_repo.paginate(db, params=params, dict_type=dict_type)
    return paginate([_to_out(r) for r in rows], total, params)


def create(db: Session, user: CurrentUser, redis, data, req: Request) -> dict:
    if data_dict_repo.get_by_type_key(db, data.dict_type, data.dict_key) is not None:
        raise biz(3005, "该分类下的键已存在")
    d = data_dict_repo.create(db, dict_type=data.dict_type, dict_key=data.dict_key,
                              dict_label=data.dict_label, sort_order=data.sort_order,
                              status=data.status)
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="dict", action="create",
                              target_type="data_dict", target_id=d.id,
                              detail={"dict_type": d.dict_type, "dict_key": d.dict_key},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    dict_cache.invalidate(redis, d.dict_type)
    return _to_out(d)


def update(db: Session, user: CurrentUser, redis, id_: str, data, req: Request) -> dict:
    d = data_dict_repo.get(db, id_)
    if d is None:
        raise not_found("字典项不存在")
    fields = data.model_fields_set
    if "dict_label" in fields and data.dict_label is not None:
        d.dict_label = data.dict_label
    if "sort_order" in fields and data.sort_order is not None:
        d.sort_order = data.sort_order
    if "status" in fields and data.status is not None:
        d.status = data.status
    db.flush()
    operation_log_repo.create(db, user_id=user.id, module="dict", action="update",
                              target_type="data_dict", target_id=d.id,
                              detail={"dict_type": d.dict_type, "dict_key": d.dict_key},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    dict_cache.invalidate(redis, d.dict_type)
    return _to_out(d)


def delete(db: Session, user: CurrentUser, redis, id_: str, req: Request) -> None:
    d = data_dict_repo.get(db, id_)
    if d is None:
        raise not_found("字典项不存在")
    dict_type = d.dict_type
    data_dict_repo.delete(db, d)
    operation_log_repo.create(db, user_id=user.id, module="dict", action="delete",
                              target_type="data_dict", target_id=id_,
                              detail={"dict_type": dict_type, "dict_key": d.dict_key},
                              ip=_ip(req), user_agent=_ua(req))
    db.commit()
    dict_cache.invalidate(redis, dict_type)
```

- [ ] **Step 8: Add router + mount**

Create `backend/app/routers/dicts.py`:

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_permission
from app.core.redis import get_redis
from app.core.response import envelope
from app.schemas.common import PageParams
from app.schemas.dict import DictCreate, DictUpdate
from app.services import dict_service

router = APIRouter(prefix="/dicts", tags=["dicts"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, keyword: str | None = None,
          dict_type: str | None = None, db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:dict"))):
    params = PageParams(page=page, page_size=page_size, keyword=keyword)
    return envelope(data=dict_service.list_dicts(db, user, params, dict_type))


@router.get("/{dict_type}")
def by_type(dict_type: str, db: Session = Depends(get_db),
            redis=Depends(get_redis), user: CurrentUser = Depends(get_current_user)):
    return envelope(data=dict_service.list_by_type(db, redis, dict_type))


@router.post("")
def create(body: DictCreate, request: Request, db: Session = Depends(get_db),
           redis=Depends(get_redis),
           user: CurrentUser = Depends(require_permission("system:dict"))):
    return envelope(data=dict_service.create(db, user, redis, body, request))


@router.put("/{id_}")
def update(id_: str, body: DictUpdate, request: Request, db: Session = Depends(get_db),
           redis=Depends(get_redis),
           user: CurrentUser = Depends(require_permission("system:dict"))):
    return envelope(data=dict_service.update(db, user, redis, id_, body, request))


@router.delete("/{id_}")
def delete(id_: str, request: Request, db: Session = Depends(get_db),
           redis=Depends(get_redis),
           user: CurrentUser = Depends(require_permission("system:dict"))):
    dict_service.delete(db, user, redis, id_, request)
    return envelope(message="已删除")
```

**Routing note:** `GET /dicts` (path `""`, `system:dict`) and `GET /dicts/{dict_type}` (login-only) coexist — FastAPI matches the empty path exactly for the list and the parameterized path for by-type. `PUT/DELETE /dicts/{id_}` use the same `{id_}` param shape; there is no GET-by-id endpoint, so no clash with `GET /dicts/{dict_type}`.

Modify `backend/app/api/v1.py`:

```python
from app.routers.dicts import router as dicts_router
# ...
api_router.include_router(dicts_router)
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_dicts.py -q`
Expected: PASS (6 tests).

- [ ] **Step 10: Commit**

```bash
cd backend && git add app/schemas/dict.py app/repositories/data_dict_repo.py app/core/dict_cache.py app/services/dict_service.py app/routers/dicts.py app/core/config.py app/api/v1.py tests/test_dicts.py
git commit -m "feat(system): data dictionary CRUD with Redis cache read+invalidate"
```

---

### Task 4: Operation Log Query (read-only)

**Files:**
- Create: `backend/app/schemas/operation_log.py`
- Modify: `backend/app/repositories/operation_log_repo.py` (add `paginate`)
- Create: `backend/app/services/log_service.py`
- Create: `backend/app/routers/operation_logs.py`
- Modify: `backend/app/api/v1.py` (mount operation_logs router)
- Test: `backend/tests/test_operation_logs.py`

**Interfaces:**
- Consumes: `require_permission("system:log")`, existing `operation_log_repo.create`.
- Produces:
  - `operation_log_repo.paginate(db, *, params, user_id=None, module=None, action=None, start=None, end=None) -> tuple[list[tuple[OperationLog, str]], int]`
  - `log_service.list_logs(db, user, params, filters...) -> dict`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_operation_logs.py`:

```python
import pytest

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


def _make_user(db, username, role_code):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_logs_recorded_and_queryable(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    # produce a couple of write ops (role create logs module=role)
    client.post("/api/v1/roles", headers=_h(tok),
                json={"code": "r1", "name": "r1", "data_scope": "all"})
    data = client.get("/api/v1/operation-logs", headers=_h(tok)).json()["data"]
    assert data["total"] >= 1
    assert all("username" in it for it in data["items"])


def test_filter_by_module(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    client.post("/api/v1/roles", headers=_h(tok),
                json={"code": "r2", "name": "r2", "data_scope": "all"})
    data = client.get("/api/v1/operation-logs?module=role&action=create", headers=_h(tok)).json()["data"]
    assert data["total"] >= 1
    assert all(it["module"] == "role" and it["action"] == "create" for it in data["items"])


def test_filter_by_module_empty(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    data = client.get("/api/v1/operation-logs?module=nonesuch", headers=_h(tok)).json()["data"]
    assert data["total"] == 0 and data["items"] == []


def test_non_super_forbidden(client, seeded):
    _make_user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    assert client.get("/api/v1/operation-logs", headers=_h(tok)).json()["code"] == 1003
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_operation_logs.py -q`
Expected: FAIL (route missing).

- [ ] **Step 3: Add repository paginate**

Append to `backend/app/repositories/operation_log_repo.py` (add imports `from datetime import datetime, timedelta`, `from sqlalchemy import select, func`, `from app.models import OperationLog, User`, `from app.schemas.common import PageParams`):

```python
def _parse_bound(value: str, *, end: bool) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:  # date only 'YYYY-MM-DD'
            d = datetime.fromisoformat(value)
            return d + timedelta(days=1) if end else d
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def paginate(db, *, params: PageParams, user_id: str | None = None, module: str | None = None,
             action: str | None = None, start: str | None = None,
             end: str | None = None) -> tuple[list[tuple[OperationLog, str]], int]:
    base = (select(OperationLog, User.username)
            .join(User, User.id == OperationLog.user_id))
    if user_id:
        base = base.where(OperationLog.user_id == user_id)
    if module:
        base = base.where(OperationLog.module == module)
    if action:
        base = base.where(OperationLog.action == action)
    start_dt = _parse_bound(start, end=False) if start else None
    end_dt = _parse_bound(end, end=True) if end else None
    if start_dt is not None:
        base = base.where(OperationLog.created_at >= start_dt)
    if end_dt is not None:
        op = OperationLog.created_at < end_dt if (end and len(end) == 10) else OperationLog.created_at <= end_dt
        base = base.where(op)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()
    stmt = (base.order_by(OperationLog.created_at.desc())
            .offset((params.page - 1) * params.page_size).limit(params.page_size))
    rows = db.execute(stmt).all()
    return [(r[0], r[1]) for r in rows], total
```

- [ ] **Step 4: Add schema**

Create `backend/app/schemas/operation_log.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class OperationLogOut(BaseModel):
    id: str
    user_id: str
    username: str | None = None
    module: str
    action: str
    target_type: str | None = None
    target_id: str | None = None
    detail: dict | None = None
    ip: str | None = None
    created_at: datetime | None = None
```

- [ ] **Step 5: Add service**

Create `backend/app/services/log_service.py`:

```python
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models import OperationLog
from app.repositories import operation_log_repo
from app.schemas.common import PageParams, paginate


def _to_out(log: OperationLog, username: str | None) -> dict:
    return {"id": log.id, "user_id": log.user_id, "username": username,
            "module": log.module, "action": log.action,
            "target_type": log.target_type, "target_id": log.target_id,
            "detail": log.detail, "ip": log.ip, "created_at": log.created_at}


def list_logs(db: Session, user: CurrentUser, params: PageParams, *,
              user_id: str | None, module: str | None, action: str | None,
              start: str | None, end: str | None) -> dict:
    rows, total = operation_log_repo.paginate(
        db, params=params, user_id=user_id, module=module, action=action, start=start, end=end)
    return paginate([_to_out(log, name) for log, name in rows], total, params)
```

- [ ] **Step 6: Add router + mount**

Create `backend/app/routers/operation_logs.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.core.response import envelope
from app.schemas.common import PageParams
from app.services import log_service

router = APIRouter(prefix="/operation-logs", tags=["operation-logs"])


@router.get("")
def list_(page: int = 1, page_size: int = 20, user_id: str | None = None,
          module: str | None = None, action: str | None = None,
          start: str | None = None, end: str | None = None,
          db: Session = Depends(get_db),
          user: CurrentUser = Depends(require_permission("system:log"))):
    params = PageParams(page=page, page_size=page_size)
    return envelope(data=log_service.list_logs(db, user, params, user_id=user_id,
                                               module=module, action=action, start=start, end=end))
```

Modify `backend/app/api/v1.py`:

```python
from app.routers.operation_logs import router as operation_logs_router
# ...
api_router.include_router(operation_logs_router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_operation_logs.py -q`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/schemas/operation_log.py app/repositories/operation_log_repo.py app/services/log_service.py app/routers/operation_logs.py app/api/v1.py tests/test_operation_logs.py
git commit -m "feat(system): read-only operation-log query with filters"
```

---

### Task 5: Integration, Full Suite, Ruff Sweep

**Files:**
- Modify: `backend/app/api/v1.py` (verify all four routers mounted)
- Possibly Modify: any files flagged by ruff
- Test: whole suite

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: green whole-suite + clean ruff; no new public interfaces.

- [ ] **Step 1: Verify router mounts**

Run: `cd backend && grep -n "include_router" app/api/v1.py`
Expected: auth, departments, employees, workstations, devices, **users, roles, permissions, dicts, operation_logs** all present.

- [ ] **Step 2: Run the whole test suite**

Run: `cd backend && python -m pytest -q`
Expected: ALL green (prior 96 + new ~28 = ~124). Fix any regressions before proceeding (do not edit unrelated slice-1/2/3 tests).

- [ ] **Step 3: Ruff sweep**

Run: `cd backend && python -m ruff check app tests`
If issues: `python -m ruff check --fix app tests` for import/format-only fixes, then re-run. Manually resolve anything `--fix` won't (e.g., unused imports introduced while extending repos). Target: **0 warnings**.

- [ ] **Step 4: Re-run suite after ruff fixes**

Run: `cd backend && python -m pytest -q && python -m ruff check app tests`
Expected: tests green AND ruff clean.

- [ ] **Step 5: Add missing edge coverage (only if a gap surfaced in review)**

If review flags an untested branch, add a focused test in the relevant `tests/test_*.py`. Candidates to double-check now:
- `PUT /users/{id}` role change happy-path returns updated `role_code`.
- `GET /dicts/{dict_type}` second call is served from cache (assert DB not queried is hard; instead assert two calls return identical items and the cache key exists after the first).
- `DELETE /roles/{id}` on a custom role also removed its `role_permissions` (query `role_permissions` count == 0 after delete).

- [ ] **Step 6: Commit**

```bash
cd backend && git add -A
git commit -m "chore(system): mount routers, ruff clean, full suite green for slice 4"
```

---

## Self-Review Notes (author)

- **Spec coverage:** §8.6 Users (7) → Task 1; Roles/Permissions (8) → Task 2; operation-logs (1) → Task 4; dicts (5) → Task 3. §3.2 super-only gating → `require_permission("system:*")` on every route + `test_non_super_forbidden` in each test file. §5.11 cache → Task 3 `dict_cache` + invalidation test. §6 security (self-lock, builtin/super guards, reset-revoke) → Task 1/2 tests.
- **Type consistency:** `paginate(items, total, params)` from `schemas.common` reused everywhere; `model_fields_set` used for partial updates in users/roles/dicts; `_ip`/`_ua` helper pair duplicated per-service (matches existing department/employee services — intentional, not DRY-violating within this codebase's established style).
- **Known reuse:** `role_repo.get_by_id`, `permission_repo.list_all/get_by_code`, `user_repo.get_active_by_username/get_active_by_id/set_password` already exist — do not redefine.
- **Deferred:** `employees/import|export` + `/tasks/{id}` (slice 5); history endpoint name enrichment (slice 6).
