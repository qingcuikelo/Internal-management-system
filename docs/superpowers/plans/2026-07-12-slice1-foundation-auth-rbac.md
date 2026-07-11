# 切片1（地基 + 认证/RBAC）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a runnable FastAPI backend with full JWT auth + RBAC groundwork and all 11 tables' schema, verifiable end-to-end and green under pytest on a dedicated MySQL test DB.

**Architecture:** Four-layer FastAPI (`api → routers → services → repositories → models`) with a `core` layer for cross-cutting infra (config, DB, Redis, security, deps, exceptions, response, logging). SQLAlchemy 2.0 declarative models + Alembic baseline migration (all 11 tables, two-step circular FK). Auth uses PyJWT dual-token (access/refresh) with a Redis jti blacklist and login-fail lockout; RBAC resolves permission-point sets per role and produces a data-scope descriptor (applied in later slices).

**Tech Stack:** Python 3.11, FastAPI, uvicorn, SQLAlchemy 2.0, Alembic, PyMySQL, redis-py, Pydantic v2, pydantic-settings, PyJWT, passlib[bcrypt], uuid-utils, pytest, httpx, ruff.

## Global Constraints

- Python **3.11**; project-specific venv at `backend/.venv` (venv + pip). Never use global Python or the shared `ai_projects/.venv`.
- Package is installable: `pyproject.toml` with **hatchling** build backend; `pip install -e .[dev]`.
- All source under `backend/`. Working dir for all commands below is `backend/` unless stated.
- DB is **MySQL 8** (LAN), driver **PyMySQL**, charset utf8mb4. App DB `ims`, test DB `ims_test`. No SQLite anywhere.
- Redis 7 (LAN). Tests use a dedicated `REDIS_DB` index and flush it in fixtures.
- Primary keys: **UUIDv7** stored as `CHAR(36)` (via `uuid-utils`).
- Times stored **UTC**, columns `DATETIME(3)`.
- Soft delete via `deleted_at`; unique business keys use a generated `active_flag` column + composite unique index (uniqueness only among non-deleted rows).
- Unified response envelope `{code, message, data, trace_id}`; `code=0` success; error code ranges 1xxx/2xxx/3xxx/5xxx.
- API prefix `/api/v1`; `/health` is public and un-prefixed.
- Passwords: bcrypt hashed (passlib); policy ≥8 chars incl. upper+lower+digit. Never store plaintext/MD5.
- JWT: HS256, access 15min, refresh 7d, each token carries a `jti` and `iat`.
- TDD: write failing test → run → implement → run → commit. Small, frequent commits.
- All commits append: `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`.

---

### Task 1: Backend scaffold, packaging, and settings

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `app.core.config.Settings` (pydantic-settings `BaseSettings`); `app.core.config.get_settings() -> Settings` (lru_cached); `settings` module-level instance. Fields: `app_env, api_prefix, db_host, db_port, db_user, db_password, db_name, db_name_test, redis_host, redis_port, redis_db, redis_password, jwt_secret, jwt_alg, access_token_minutes, refresh_token_days, login_max_fail, login_lock_minutes, seed_admin_username, seed_admin_password, cors_origins (list[str])`. Properties: `sqlalchemy_url -> str`, `sqlalchemy_test_url -> str`, `redis_url -> str`.

- [ ] **Step 1: Create the venv and project files**

Create `backend/pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ims-backend"
version = "0.1.0"
description = "Enterprise internal management system - backend"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pymysql>=1.1",
    "redis>=5.0",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "pyjwt>=2.8",
    "passlib[bcrypt]>=1.7.4",
    "bcrypt>=4.0,<5.0",
    "uuid-utils>=0.7",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27", "ruff>=0.4"]

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
```

Create `backend/.gitignore`:
```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
```

Create `backend/.env.example`:
```
APP_ENV=dev
API_PREFIX=/api/v1
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=ims
DB_NAME_TEST=ims_test
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
JWT_SECRET=change-me-in-.env
JWT_ALG=HS256
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
LOGIN_MAX_FAIL=5
LOGIN_LOCK_MINUTES=15
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_PASSWORD=Admin@12345
CORS_ORIGINS=http://localhost:5173
```

Create empty `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/tests/__init__.py`.

Then bootstrap the environment:
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_config.py`:
```python
import importlib


def test_settings_builds_urls(monkeypatch):
    monkeypatch.setenv("DB_HOST", "10.0.0.5")
    monkeypatch.setenv("DB_PORT", "3306")
    monkeypatch.setenv("DB_USER", "ims")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setenv("DB_NAME", "ims")
    monkeypatch.setenv("DB_NAME_TEST", "ims_test")
    monkeypatch.setenv("REDIS_HOST", "10.0.0.6")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "1")
    monkeypatch.setenv("REDIS_PASSWORD", "")
    monkeypatch.setenv("JWT_SECRET", "x")

    from app.core import config
    importlib.reload(config)
    s = config.get_settings()

    assert s.sqlalchemy_url == "mysql+pymysql://ims:secret@10.0.0.5:3306/ims?charset=utf8mb4"
    assert s.sqlalchemy_test_url.endswith("/ims_test?charset=utf8mb4")
    assert s.redis_url == "redis://10.0.0.6:6379/1"
    assert s.access_token_minutes == 15
    assert s.cors_origins == ["http://localhost:5173"]


def test_cors_origins_parses_csv(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
    from app.core import config
    importlib.reload(config)
    s = config.get_settings()
    assert s.cors_origins == ["http://a.com", "http://b.com"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError` / `get_settings` not defined.

- [ ] **Step 4: Implement config**

Create `backend/app/core/config.py`:
```python
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "ims"
    db_name_test: str = "ims_test"

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    jwt_secret: str
    jwt_alg: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    login_max_fail: int = 5
    login_lock_minutes: int = 15

    seed_admin_username: str = "admin"
    seed_admin_password: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    def _url(self, name: str) -> str:
        pwd = f":{self.db_password}" if self.db_password else ""
        return f"mysql+pymysql://{self.db_user}{pwd}@{self.db_host}:{self.db_port}/{name}?charset=utf8mb4"

    @property
    def sqlalchemy_url(self) -> str:
        return self._url(self.db_name)

    @property
    def sqlalchemy_test_url(self) -> str:
        return self._url(self.db_name_test)

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/.env.example backend/.gitignore backend/app backend/tests
git commit -m "$(cat <<'EOF'
feat(backend): scaffold project, packaging, and settings

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Unified response, pagination schemas, exceptions & error codes

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/core/context.py`
- Create: `backend/app/core/response.py`
- Create: `backend/app/core/exceptions.py`
- Create: `backend/tests/test_response.py`

**Interfaces:**
- Produces:
  - `app.core.context.trace_id_ctx: ContextVar[str]`; `get_trace_id() -> str`; `set_trace_id(v: str)`.
  - `app.core.response.envelope(data=None, message="ok", code=0) -> dict` (includes `trace_id`).
  - `app.schemas.common.PageParams` (fields `page:int=1, page_size:int=20, sort:str|None, order:str="desc", keyword:str|None`); `PageResult` generic model with `items, total, page, page_size`; helper `paginate(items, total, params) -> dict`.
  - `app.core.exceptions.BizError(code:int, message:str, http_status:int=400)` and named factories: `unauthorized()`(1001,401), `forbidden()`(1003,403), `account_locked(msg)`(1002,423), `biz(code,msg)`(3xxx,409), `validation(msg)`(2001,422). `register_exception_handlers(app)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_response.py`:
```python
from app.core.context import set_trace_id
from app.core.response import envelope
from app.core.exceptions import BizError, unauthorized, forbidden
from app.schemas.common import PageParams, paginate


def test_envelope_shape():
    set_trace_id("t-123")
    e = envelope(data={"x": 1})
    assert e["code"] == 0
    assert e["message"] == "ok"
    assert e["data"] == {"x": 1}
    assert e["trace_id"] == "t-123"


def test_biz_error_factories():
    assert isinstance(unauthorized(), BizError)
    assert unauthorized().code == 1001
    assert unauthorized().http_status == 401
    assert forbidden().code == 1003
    assert forbidden().http_status == 403


def test_paginate():
    params = PageParams(page=2, page_size=10)
    out = paginate(items=[1, 2, 3], total=23, params=params)
    assert out == {"items": [1, 2, 3], "total": 23, "page": 2, "page_size": 10}


def test_page_params_caps_page_size():
    params = PageParams(page_size=999)
    assert params.page_size == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_response.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement context, response, common schema, exceptions**

Create `backend/app/core/context.py`:
```python
from contextvars import ContextVar

trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return trace_id_ctx.get()


def set_trace_id(value: str) -> None:
    trace_id_ctx.set(value)
```

Create `backend/app/core/response.py`:
```python
from typing import Any

from app.core.context import get_trace_id


def envelope(data: Any = None, message: str = "ok", code: int = 0) -> dict:
    return {"code": code, "message": message, "data": data, "trace_id": get_trace_id()}
```

Create `backend/app/schemas/common.py`:
```python
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    sort: str | None = None
    order: str = "desc"
    keyword: str | None = None

    @field_validator("page_size")
    @classmethod
    def _cap(cls, v: int) -> int:
        return min(v, 100)

    @field_validator("order")
    @classmethod
    def _order(cls, v: str) -> str:
        return v.lower() if v.lower() in ("asc", "desc") else "desc"


class PageResult(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


def paginate(items: list, total: int, params: PageParams) -> dict:
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size}
```

Create `backend/app/schemas/__init__.py` (empty).

Create `backend/app/core/exceptions.py`:
```python
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import envelope


class BizError(Exception):
    def __init__(self, code: int, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def unauthorized(message: str = "未登录或登录已失效") -> BizError:
    return BizError(1001, message, 401)


def account_locked(message: str = "账号已锁定，请稍后再试") -> BizError:
    return BizError(1002, message, 423)


def forbidden(message: str = "无权访问该资源") -> BizError:
    return BizError(1003, message, 403)


def validation(message: str = "参数校验失败") -> BizError:
    return BizError(2001, message, 422)


def biz(code: int, message: str, http_status: int = 409) -> BizError:
    return BizError(code, message, http_status)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz(_: Request, exc: BizError):
        return JSONResponse(
            status_code=exc.http_status,
            content=envelope(data=None, message=exc.message, code=exc.code),
        )

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        msg = "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors())
        return JSONResponse(status_code=422, content=envelope(data=None, message=msg, code=2001))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=envelope(data=None, message="服务器内部错误", code=5000),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_response.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/context.py backend/app/core/response.py backend/app/core/exceptions.py backend/app/schemas backend/tests/test_response.py
git commit -m "$(cat <<'EOF'
feat(core): unified response envelope, pagination, exceptions and error codes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: UUIDv7 and tree utilities

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/uuidv7.py`
- Create: `backend/app/utils/tree.py`
- Create: `backend/tests/test_utils.py`

**Interfaces:**
- Produces: `app.utils.uuidv7.uuid7() -> str` (36-char UUID string, time-ordered). `app.utils.tree.descendant_ids(rows: list[tuple[str, str | None]], root_id: str) -> set[str]` (returns root_id plus all transitive children; `rows` are `(id, parent_id)`).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_utils.py`:
```python
from app.utils.uuidv7 import uuid7
from app.utils.tree import descendant_ids


def test_uuid7_format_and_ordering():
    a = uuid7()
    b = uuid7()
    assert len(a) == 36 and a.count("-") == 4
    assert a != b
    assert a < b  # UUIDv7 is time-ordered


def test_descendant_ids():
    rows = [("1", None), ("2", "1"), ("3", "1"), ("4", "2"), ("5", None)]
    assert descendant_ids(rows, "1") == {"1", "2", "3", "4"}
    assert descendant_ids(rows, "2") == {"2", "4"}
    assert descendant_ids(rows, "5") == {"5"}


def test_descendant_ids_missing_root():
    assert descendant_ids([("1", None)], "x") == {"x"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_utils.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement utilities**

Create `backend/app/utils/__init__.py` (empty).

Create `backend/app/utils/uuidv7.py`:
```python
import uuid_utils


def uuid7() -> str:
    return str(uuid_utils.uuid7())
```

Create `backend/app/utils/tree.py`:
```python
from collections import defaultdict


def descendant_ids(rows: list[tuple[str, str | None]], root_id: str) -> set[str]:
    children: dict[str | None, list[str]] = defaultdict(list)
    for node_id, parent_id in rows:
        children[parent_id].append(node_id)

    result: set[str] = {root_id}
    stack = [root_id]
    while stack:
        current = stack.pop()
        for child in children.get(current, []):
            if child not in result:
                result.add(child)
                stack.append(child)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_utils.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/utils backend/tests/test_utils.py
git commit -m "$(cat <<'EOF'
feat(utils): UUIDv7 generator and department subtree id collector

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: ORM base, mixins, and all 11 models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/role.py`
- Create: `backend/app/models/permission.py`
- Create: `backend/app/models/role_permission.py`
- Create: `backend/app/models/department.py`
- Create: `backend/app/models/employee.py`
- Create: `backend/app/models/workstation.py`
- Create: `backend/app/models/device.py`
- Create: `backend/app/models/assignment.py`
- Create: `backend/app/models/operation_log.py`
- Create: `backend/app/models/data_dict.py`
- Create: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.base.Base` (DeclarativeBase), mixins `PKMixin`, `TimestampMixin`, `SoftDeleteMixin`, `AuditMixin`, `VersionMixin`, helper `now_utc()`, and generated-column helper `active_flag_column()`. ORM classes: `User, Role, Permission, RolePermission, Department, Employee, Workstation, Device, WorkstationAssignment, DeviceAssignment, OperationLog, DataDict`. `app.models.__init__` imports all so `Base.metadata` sees every table. Table names: `users, roles, permissions, role_permissions, departments, employees, workstations, devices, workstation_assignments, device_assignments, operation_logs, data_dict`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_models.py`:
```python
from app.models import Base, User


EXPECTED_TABLES = {
    "users", "roles", "permissions", "role_permissions",
    "departments", "employees", "workstations", "devices",
    "workstation_assignments", "device_assignments",
    "operation_logs", "data_dict",
}


def test_all_tables_registered():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_user_columns():
    cols = Base.metadata.tables["users"].columns
    for name in ("id", "username", "password_hash", "role_id", "employee_id",
                 "status", "last_login_at", "pwd_updated_at",
                 "created_at", "updated_at", "deleted_at"):
        assert name in cols


def test_new_instance_gets_uuid():
    u = User(username="a", password_hash="x", role_id="r", status=1)
    assert u.id is not None and len(u.id) == 36


def test_version_column_on_workstation_and_device():
    assert "version" in Base.metadata.tables["workstations"].columns
    assert "version" in Base.metadata.tables["devices"].columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `app.models` not found.

- [ ] **Step 3: Implement base + mixins**

Create `backend/app/models/base.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import CHAR, Computed, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.uuidv7 import uuid7


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PKMixin:
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(fsp=3), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(fsp=3), default=now_utc, onupdate=now_utc, nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(fsp=3), nullable=True)


class AuditMixin:
    created_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def active_flag_column() -> Mapped[int | None]:
    # Generated column: 1 when not deleted, NULL when deleted.
    # Used with a composite UNIQUE index (business_key, active_flag) so
    # uniqueness only applies among non-deleted rows.
    return mapped_column(
        Integer,
        Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True),
        nullable=True,
    )
```

- [ ] **Step 4: Implement the 11 model files**

Create `backend/app/models/role.py`:
```python
from sqlalchemy import CHAR, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class Role(Base, PKMixin, TimestampMixin):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_builtin: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_scope: Mapped[str] = mapped_column(String(16), nullable=False)  # all/dept/self
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```

Create `backend/app/models/permission.py`:
```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin


class Permission(Base, PKMixin):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
```

Create `backend/app/models/role_permission.py`:
```python
from sqlalchemy import CHAR, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("permissions.id"), primary_key=True
    )
```

Create `backend/app/models/user.py`:
```python
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, active_flag_column,
)


class User(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", "active_flag", name="uk_username_active"),)

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("roles.id"), nullable=False)
    employee_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(fsp=3), nullable=True)
    pwd_updated_at: Mapped[datetime | None] = mapped_column(DateTime(fsp=3), nullable=True)
    active_flag: Mapped[int | None] = active_flag_column()
```
> Note: `users.employee_id` FK to `employees.id` is added in the Alembic migration (Task 5), not on the model, to keep model import order simple. The column exists here; the constraint is DB-level.

Create `backend/app/models/department.py`:
```python
from sqlalchemy import CHAR, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin


class Department(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```
> `parent_id`, `manager_id` FKs added in migration (circular dependency handled two-step).

Create `backend/app/models/employee.py`:
```python
from datetime import date

from sqlalchemy import CHAR, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, active_flag_column,
)


class Employee(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("employee_no", "active_flag", name="uk_employee_no_active"),)

    employee_no: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    department_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    direct_supervisor_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active_flag: Mapped[int | None] = active_flag_column()
```

Create `backend/app/models/workstation.py`:
```python
from datetime import date

from sqlalchemy import CHAR, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin, active_flag_column,
)


class Workstation(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin):
    __tablename__ = "workstations"
    __table_args__ = (UniqueConstraint("code", "active_flag", name="uk_ws_code_active"),)

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_employee_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    assign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Create `backend/app/models/device.py`:
```python
from datetime import date

from sqlalchemy import CHAR, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin, active_flag_column,
)


class Device(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("asset_code", "active_flag", name="uk_dev_asset_active"),
        UniqueConstraint("serial_number", "active_flag", name="uk_dev_serial_active"),
    )

    asset_code: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specs: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_expire: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_employee_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    assign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

Create `backend/app/models/assignment.py`:
```python
from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, now_utc


class WorkstationAssignment(Base, PKMixin):
    __tablename__ = "workstation_assignments"

    workstation_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("workstations.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("employees.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    operator_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(fsp=3), default=now_utc, nullable=False)


class DeviceAssignment(Base, PKMixin):
    __tablename__ = "device_assignments"

    device_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("devices.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("employees.id"), nullable=False)
    checkout_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    operator_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(fsp=3), default=now_utc, nullable=False)
```

Create `backend/app/models/operation_log.py`:
```python
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, now_utc


class OperationLog(Base, PKMixin):
    __tablename__ = "operation_logs"

    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), nullable=False)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(fsp=3), default=now_utc, nullable=False)
```

Create `backend/app/models/data_dict.py`:
```python
from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin


class DataDict(Base, PKMixin):
    __tablename__ = "data_dict"
    __table_args__ = (UniqueConstraint("dict_type", "dict_key", name="uk_dict_type_key"),)

    dict_type: Mapped[str] = mapped_column(String(32), nullable=False)
    dict_key: Mapped[str] = mapped_column(String(32), nullable=False)
    dict_label: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
```

Create `backend/app/models/__init__.py`:
```python
from app.models.base import Base
from app.models.role import Role
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.workstation import Workstation
from app.models.device import Device
from app.models.assignment import WorkstationAssignment, DeviceAssignment
from app.models.operation_log import OperationLog
from app.models.data_dict import DataDict

__all__ = [
    "Base", "Role", "Permission", "RolePermission", "User", "Department",
    "Employee", "Workstation", "Device", "WorkstationAssignment",
    "DeviceAssignment", "OperationLog", "DataDict",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models backend/tests/test_models.py
git commit -m "$(cat <<'EOF'
feat(models): SQLAlchemy base, mixins, and all 11 tables

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Alembic setup and baseline migration (all tables + two-step circular FK)

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_baseline.py`
- Create: `backend/tests/test_migration.py`

**Interfaces:**
- Consumes: `app.models.Base.metadata`, `app.core.config.settings.sqlalchemy_test_url`.
- Produces: a baseline migration with `revision = "0001"` creating all 11 tables and adding FKs (incl. circular `departments.parent_id/manager_id`, `employees.department_id/direct_supervisor_id`, `users.employee_id`) in a second step. Running `alembic upgrade head` builds the full schema; `downgrade base` drops it.

**Precondition:** `.env` is configured to reach the LAN MySQL, and databases `ims` and `ims_test` exist:
```sql
CREATE DATABASE IF NOT EXISTS ims CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
CREATE DATABASE IF NOT EXISTS ims_test CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
```

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_migration.py`:
```python
import subprocess
import os

from sqlalchemy import create_engine, inspect

from app.core.config import settings

EXPECTED = {
    "users", "roles", "permissions", "role_permissions", "departments",
    "employees", "workstations", "devices", "workstation_assignments",
    "device_assignments", "operation_logs", "data_dict", "alembic_version",
}


def _alembic(*args):
    env = {**os.environ, "ALEMBIC_TARGET": "test"}
    return subprocess.run(["alembic", *args], cwd="backend", env=env, capture_output=True, text=True)


def test_upgrade_creates_all_tables():
    down = _alembic("downgrade", "base")
    up = _alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr

    engine = create_engine(settings.sqlalchemy_test_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert EXPECTED.issubset(tables)


def test_circular_fk_present():
    _alembic("upgrade", "head")
    engine = create_engine(settings.sqlalchemy_test_url)
    insp = inspect(engine)
    dep_fks = {fk["referred_table"] for fk in insp.get_foreign_keys("departments")}
    emp_fks = {fk["referred_table"] for fk in insp.get_foreign_keys("employees")}
    engine.dispose()
    assert "employees" in dep_fks       # departments.manager_id -> employees
    assert "departments" in emp_fks     # employees.department_id -> departments
```
> Note: run this test from repo root (`pytest backend/tests/test_migration.py`) so `cwd="backend"` resolves. Other tests run from `backend/`. Task 6 conftest handles both by using absolute paths; for this task run `pytest tests/test_migration.py` from `backend/` and adjust `cwd="."`. **Set `cwd="."` in `_alembic` when running from `backend/`.** Use `cwd="."`.

Adjust the helper to `cwd="."` (running from `backend/`):
```python
    return subprocess.run(["alembic", *args], cwd=".", env=env, capture_output=True, text=True)
```

- [ ] **Step 2: Initialize Alembic config files**

Create `backend/alembic.ini`:
```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/alembic/script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `backend/alembic/env.py`:
```python
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    if os.getenv("ALEMBIC_TARGET") == "test":
        return settings.sqlalchemy_test_url
    return settings.sqlalchemy_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_migration.py -v`
Expected: FAIL — no revision / `alembic upgrade` errors (no versions yet).

- [ ] **Step 4: Write the baseline migration**

Create `backend/alembic/versions/0001_baseline.py`. This creates every table without the circular FKs, then adds them via `ALTER TABLE`. Uses generated `active_flag` columns for soft-delete-aware uniqueness.

```python
"""baseline: all 11 tables + circular FKs

Revision ID: 0001
Revises:
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DT = mysql.DATETIME(fsp=3)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("is_builtin", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_scope", sa.String(16), nullable=False),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.UniqueConstraint("code", name="uk_role_code"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.UniqueConstraint("code", name="uk_perm_code"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.CHAR(36), nullable=False),
        sa.Column("permission_id", sa.CHAR(36), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", sa.CHAR(36), nullable=False),
        sa.Column("employee_id", sa.CHAR(36), nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_login_at", DT, nullable=True),
        sa.Column("pwd_updated_at", DT, nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.UniqueConstraint("username", "active_flag", name="uk_username_active"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_users_employee_id", "users", ["employee_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("parent_id", sa.CHAR(36), nullable=True),
        sa.Column("manager_id", sa.CHAR(36), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_dept_parent_id", "departments", ["parent_id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("employee_no", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("gender", sa.Integer, nullable=False),
        sa.Column("email", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("department_id", sa.CHAR(36), nullable=True),
        sa.Column("direct_supervisor_id", sa.CHAR(36), nullable=True),
        sa.Column("position", sa.String(64), nullable=True),
        sa.Column("hire_date", sa.Date, nullable=True),
        sa.Column("resign_date", sa.Date, nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.UniqueConstraint("employee_no", "active_flag", name="uk_employee_no_active"),
        sa.UniqueConstraint("email", name="uk_employee_email"),
        sa.UniqueConstraint("phone", name="uk_employee_phone"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_emp_department_id", "employees", ["department_id"])
    op.create_index("idx_emp_supervisor_id", "employees", ["direct_supervisor_id"])

    op.create_table(
        "workstations",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("current_employee_id", sa.CHAR(36), nullable=True),
        sa.Column("assign_date", sa.Date, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["current_employee_id"], ["employees.id"]),
        sa.UniqueConstraint("code", "active_flag", name="uk_ws_code_active"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_ws_current_emp", "workstations", ["current_employee_id"])
    op.create_index("idx_ws_status", "workstations", ["status"])

    op.create_table(
        "devices",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("asset_code", sa.String(32), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("brand", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("serial_number", sa.String(64), nullable=True),
        sa.Column("specs", sa.String(255), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("warranty_expire", sa.Date, nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("current_employee_id", sa.CHAR(36), nullable=True),
        sa.Column("assign_date", sa.Date, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["current_employee_id"], ["employees.id"]),
        sa.UniqueConstraint("asset_code", "active_flag", name="uk_dev_asset_active"),
        sa.UniqueConstraint("serial_number", "active_flag", name="uk_dev_serial_active"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_dev_status", "devices", ["status"])
    op.create_index("idx_dev_current_emp", "devices", ["current_employee_id"])
    op.create_index("idx_dev_warranty", "devices", ["warranty_expire"])

    op.create_table(
        "workstation_assignments",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("workstation_id", sa.CHAR(36), nullable=False),
        sa.Column("employee_id", sa.CHAR(36), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("operator_id", sa.CHAR(36), nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.ForeignKeyConstraint(["workstation_id"], ["workstations.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_wsa_ws", "workstation_assignments", ["workstation_id"])
    op.create_index("idx_wsa_emp", "workstation_assignments", ["employee_id"])

    op.create_table(
        "device_assignments",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("device_id", sa.CHAR(36), nullable=False),
        sa.Column("employee_id", sa.CHAR(36), nullable=False),
        sa.Column("checkout_date", sa.Date, nullable=False),
        sa.Column("return_date", sa.Date, nullable=True),
        sa.Column("operator_id", sa.CHAR(36), nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_da_dev", "device_assignments", ["device_id"])
    op.create_index("idx_da_emp", "device_assignments", ["employee_id"])

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("user_id", sa.CHAR(36), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.CHAR(36), nullable=True),
        sa.Column("detail", mysql.JSON, nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_oplog_user", "operation_logs", ["user_id"])
    op.create_index("idx_oplog_created", "operation_logs", ["created_at"])
    op.create_index("idx_oplog_target", "operation_logs", ["target_type", "target_id"])

    op.create_table(
        "data_dict",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("dict_type", sa.String(32), nullable=False),
        sa.Column("dict_key", sa.String(32), nullable=False),
        sa.Column("dict_label", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("dict_type", "dict_key", name="uk_dict_type_key"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    # --- step 2: circular / late FKs ---
    op.create_foreign_key("fk_users_employee", "users", "employees", ["employee_id"], ["id"])
    op.create_foreign_key("fk_dept_parent", "departments", "departments", ["parent_id"], ["id"])
    op.create_foreign_key("fk_dept_manager", "departments", "employees", ["manager_id"], ["id"])
    op.create_foreign_key("fk_emp_dept", "employees", "departments", ["department_id"], ["id"])
    op.create_foreign_key("fk_emp_supervisor", "employees", "employees", ["direct_supervisor_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_emp_supervisor", "employees", type_="foreignkey")
    op.drop_constraint("fk_emp_dept", "employees", type_="foreignkey")
    op.drop_constraint("fk_dept_manager", "departments", type_="foreignkey")
    op.drop_constraint("fk_dept_parent", "departments", type_="foreignkey")
    op.drop_constraint("fk_users_employee", "users", type_="foreignkey")
    for t in ("data_dict", "operation_logs", "device_assignments", "workstation_assignments",
              "devices", "workstations", "employees", "departments", "users",
              "role_permissions", "permissions", "roles"):
        op.drop_table(t)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_migration.py -v`
Expected: PASS (2 passed). Also manually confirm: `ALEMBIC_TARGET= alembic upgrade head` builds `ims`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic backend/tests/test_migration.py
git commit -m "$(cat <<'EOF'
feat(db): alembic baseline migration for all 11 tables with two-step circular FKs

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Database/Redis core, app assembly, health check, and test harness

**Files:**
- Create: `backend/app/core/database.py`
- Create: `backend/app/core/redis.py`
- Create: `backend/app/core/logging.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: `settings`, exception handlers, `envelope`, `set_trace_id`.
- Produces:
  - `app.core.database.engine`, `SessionLocal`, `get_db() -> Iterator[Session]`.
  - `app.core.redis.get_redis() -> redis.Redis`, `redis_client`.
  - `app.core.logging.TraceIdMiddleware`.
  - `app.api.v1.api_router` (APIRouter with prefix from settings; auth router included in Task 9).
  - `app.main.app` (FastAPI). `/health` endpoint.
  - conftest fixtures: `db` (Session bound to `ims_test`, rolled back per test), `client` (httpx test client with `get_db`/`get_redis` overridden), `redis_conn` (flushes test Redis DB).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_health.py`:
```python
def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["db"] == "ok"
    assert body["data"]["redis"] == "ok"
    assert "trace_id" in body


def test_health_has_trace_id_header_roundtrip(client):
    resp = client.get("/health")
    assert resp.json()["trace_id"] != "-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL — no conftest fixtures / no app.

- [ ] **Step 3: Implement database, redis, logging, api router, main**

Create `backend/app/core/database.py`:
```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Create `backend/app/core/redis.py`:
```python
import redis

from app.core.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis_client
```

Create `backend/app/core/logging.py`:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import set_trace_id
from app.utils.uuidv7 import uuid7


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid7()
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
```

Create `backend/app/api/__init__.py` (empty).

Create `backend/app/api/v1.py`:
```python
from fastapi import APIRouter

from app.core.config import settings

api_router = APIRouter(prefix=settings.api_prefix)

# Business routers are included here as slices land.
# Task 9 adds: from app.routers.auth import router as auth_router; api_router.include_router(auth_router)
```

Create `backend/app/main.py`:
```python
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
```

Create `backend/tests/conftest.py`:
```python
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

os.environ.setdefault("ALEMBIC_TARGET", "test")

from app.core.config import settings  # noqa: E402
from app.core import database, redis as app_redis  # noqa: E402
from app.models import Base  # noqa: E402

test_engine = create_engine(settings.sqlalchemy_test_url, pool_pre_ping=True, future=True)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


@pytest.fixture()
def db():
    conn = test_engine.connect()
    trans = conn.begin()
    session = TestSession(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture()
def redis_conn():
    client = app_redis.get_redis()
    client.flushdb()
    yield client
    client.flushdb()


@pytest.fixture()
def client(db, redis_conn):
    from app.main import app

    app.dependency_overrides[database.get_db] = lambda: db
    app.dependency_overrides[app_redis.get_redis] = lambda: redis_conn
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```
> Note: conftest uses `Base.metadata.create_all` for speed. `test_migration.py` (Task 5) separately verifies the real Alembic migration builds an equivalent schema. The generated `active_flag` columns are created by `create_all` too (Computed is emitted).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS (2 passed). Requires LAN MySQL/Redis reachable and `ims_test` DB present.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/database.py backend/app/core/redis.py backend/app/core/logging.py backend/app/api backend/app/main.py backend/tests/conftest.py backend/tests/test_health.py
git commit -m "$(cat <<'EOF'
feat(core): DB/Redis engines, app assembly, trace-id middleware, health check, test harness

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Security primitives — password hashing and JWT

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(raw: str) -> str`; `verify_password(raw: str, hashed: str) -> bool`.
  - `new_jti() -> str`.
  - `create_access_token(sub: str) -> tuple[str, str, int]` returns `(token, jti, expires_in_seconds)`.
  - `create_refresh_token(sub: str) -> tuple[str, str]` returns `(token, jti)`.
  - `decode_token(token: str) -> dict` (raises `BizError` unauthorized on invalid/expired). Payload keys: `sub, jti, type, iat, exp`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_security.py`:
```python
import time

import pytest

from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token, decode_token,
)
from app.core.exceptions import BizError


def test_password_hash_roundtrip():
    h = hash_password("Abc12345")
    assert h != "Abc12345"
    assert verify_password("Abc12345", h)
    assert not verify_password("wrong", h)


def test_access_token_encodes_claims():
    token, jti, expires_in = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert payload["jti"] == jti
    assert expires_in > 0
    assert "iat" in payload


def test_refresh_token_type():
    token, jti = create_refresh_token("user-1")
    assert decode_token(token)["type"] == "refresh"


def test_decode_invalid_raises():
    with pytest.raises(BizError):
        decode_token("not.a.jwt")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement security**

Create `backend/app/core/security.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import unauthorized
from app.utils.uuidv7 import uuid7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def new_jti() -> str:
    return uuid7()


def _encode(sub: str, token_type: str, expires_delta: timedelta) -> tuple[str, str, int]:
    now = datetime.now(timezone.utc)
    jti = new_jti()
    payload = {
        "sub": sub,
        "jti": jti,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, jti, int(expires_delta.total_seconds())


def create_access_token(sub: str) -> tuple[str, str, int]:
    return _encode(sub, "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(sub: str) -> tuple[str, str]:
    token, jti, _ = _encode(sub, "refresh", timedelta(days=settings.refresh_token_days))
    return token, jti


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        raise unauthorized()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "$(cat <<'EOF'
feat(core): bcrypt password hashing and PyJWT dual-token helpers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Repositories (base, user, role, permission, operation_log)

**Files:**
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/repositories/base.py`
- Create: `backend/app/repositories/user_repo.py`
- Create: `backend/app/repositories/role_repo.py`
- Create: `backend/app/repositories/permission_repo.py`
- Create: `backend/app/repositories/operation_log_repo.py`
- Create: `backend/tests/test_repositories.py`

**Interfaces:**
- Consumes: models, `Session`.
- Produces:
  - `base.get_by_id(db, model, id_)`, `base.get_active(db, model, id_)` (filters `deleted_at IS NULL` when present).
  - `user_repo.get_active_by_username(db, username) -> User | None`; `get_active_by_id(db, id_)`; `update_last_login(db, user)`; `set_password(db, user, password_hash)` (also sets `pwd_updated_at`).
  - `role_repo.get_by_id(db, id_) -> Role | None`; `permission_codes_for_role(db, role_id) -> set[str]`.
  - `permission_repo.get_by_code(db, code) -> Permission | None`; `list_all(db) -> list[Permission]`.
  - `operation_log_repo.create(db, *, user_id, module, action, target_type=None, target_id=None, detail=None, ip=None, user_agent=None) -> OperationLog`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_repositories.py`:
```python
from datetime import datetime, timezone

from app.models import User, Role, Permission, RolePermission
from app.repositories import user_repo, role_repo, permission_repo, operation_log_repo
from app.core.security import hash_password


def _seed_role_with_perm(db):
    role = Role(code="t_admin", name="T", is_builtin=0, data_scope="all", status=1)
    perm = Permission(code="employee:view", name="查看员工", module="employee")
    db.add_all([role, perm])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.flush()
    return role, perm


def test_get_active_by_username(db):
    role, _ = _seed_role_with_perm(db)
    u = User(username="alice", password_hash=hash_password("Abc12345"),
             role_id=role.id, status=1)
    db.add(u)
    db.flush()
    found = user_repo.get_active_by_username(db, "alice")
    assert found is not None and found.id == u.id
    assert user_repo.get_active_by_username(db, "nobody") is None


def test_permission_codes_for_role(db):
    role, _ = _seed_role_with_perm(db)
    codes = role_repo.permission_codes_for_role(db, role.id)
    assert codes == {"employee:view"}


def test_set_password_updates_timestamp(db):
    role, _ = _seed_role_with_perm(db)
    u = User(username="bob", password_hash=hash_password("Abc12345"),
             role_id=role.id, status=1)
    db.add(u)
    db.flush()
    user_repo.set_password(db, u, hash_password("New12345"))
    db.flush()
    assert u.pwd_updated_at is not None


def test_operation_log_create(db):
    role, _ = _seed_role_with_perm(db)
    u = User(username="carol", password_hash="x", role_id=role.id, status=1)
    db.add(u)
    db.flush()
    log = operation_log_repo.create(db, user_id=u.id, module="auth", action="login")
    db.flush()
    assert log.id is not None and log.module == "auth"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repositories.py -v`
Expected: FAIL — repositories not found.

- [ ] **Step 3: Implement repositories**

Create `backend/app/repositories/__init__.py` (empty).

Create `backend/app/repositories/base.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_by_id(db: Session, model, id_: str):
    return db.get(model, id_)


def get_active(db: Session, model, id_: str):
    obj = db.get(model, id_)
    if obj is None:
        return None
    if hasattr(obj, "deleted_at") and obj.deleted_at is not None:
        return None
    return obj
```

Create `backend/app/repositories/user_repo.py`:
```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_active_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username, User.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def get_active_by_id(db: Session, id_: str) -> User | None:
    stmt = select(User).where(User.id == id_, User.deleted_at.is_(None))
    return db.execute(stmt).scalar_one_or_none()


def update_last_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)


def set_password(db: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    user.pwd_updated_at = datetime.now(timezone.utc)
```

Create `backend/app/repositories/role_repo.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, RolePermission, Permission


def get_by_id(db: Session, id_: str) -> Role | None:
    return db.get(Role, id_)


def permission_codes_for_role(db: Session, role_id: str) -> set[str]:
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    return set(db.execute(stmt).scalars().all())
```

Create `backend/app/repositories/permission_repo.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Permission


def get_by_code(db: Session, code: str) -> Permission | None:
    return db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()


def list_all(db: Session) -> list[Permission]:
    return list(db.execute(select(Permission)).scalars().all())
```

Create `backend/app/repositories/operation_log_repo.py`:
```python
from sqlalchemy.orm import Session

from app.models import OperationLog


def create(db: Session, *, user_id: str, module: str, action: str,
           target_type: str | None = None, target_id: str | None = None,
           detail: dict | None = None, ip: str | None = None,
           user_agent: str | None = None) -> OperationLog:
    log = OperationLog(
        user_id=user_id, module=module, action=action,
        target_type=target_type, target_id=target_id, detail=detail,
        ip=ip, user_agent=user_agent,
    )
    db.add(log)
    return log
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repositories.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories backend/tests/test_repositories.py
git commit -m "$(cat <<'EOF'
feat(repositories): base, user, role, permission, operation_log data access

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Auth service, dependencies, permission constants, and auth router

**Files:**
- Create: `backend/app/core/permissions.py`
- Create: `backend/app/core/deps.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/auth.py`
- Modify: `backend/app/api/v1.py` (include auth router)
- Create: `backend/tests/test_auth.py`
- Create: `backend/tests/test_permissions.py`

**Interfaces:**
- Consumes: security, repos, redis, exceptions, response.
- Produces:
  - `app.core.permissions` — `ALL_PERMISSIONS: list[dict]` (`{code, name, module}`) covering §3.4; module-level code constants (e.g. `EMPLOYEE_VIEW = "employee:view"`).
  - `app.core.deps.CurrentUser` (dataclass: `id, username, role_code, data_scope, permissions:set[str], employee_id, department_id`); `get_current_user(...)`; `require_permission(code) -> dependency`; `data_scope_descriptor(user) -> dict`.
  - `app.services.auth_service.login/refresh/logout/change_password`.
  - Redis keys: `blacklist:{jti}`, `login_fail:{username}`, `login_lock:{username}`.
  - Auth endpoints under `/api/v1/auth`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth.py`:
```python
import pytest

from app.core.security import hash_password
from app.models import User, Role, Permission, RolePermission


@pytest.fixture()
def admin_user(db):
    role = Role(code="super_admin", name="超管", is_builtin=1, data_scope="all", status=1)
    perm = Permission(code="employee:view", name="查看员工", module="employee")
    db.add_all([role, perm])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    u = User(username="admin", password_hash=hash_password("Admin@123"),
             role_id=role.id, status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_success_returns_tokens(client, admin_user):
    resp = _login(client, "admin", "Admin@123")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["username"] == "admin"
    assert "employee:view" in data["user"]["permissions"]


def test_login_wrong_password_fails(client, admin_user):
    resp = _login(client, "admin", "nope")
    assert resp.json()["code"] == 1001


def test_login_lockout_after_5_failures(client, admin_user):
    for _ in range(5):
        _login(client, "admin", "nope")
    resp = _login(client, "admin", "Admin@123")
    assert resp.json()["code"] == 1002  # locked despite correct password


def test_me_returns_permissions(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "super_admin"


def test_refresh_issues_new_access(client, admin_user):
    refresh = _login(client, "admin", "Admin@123").json()["data"]["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


def test_logout_blacklists_token(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).json()["code"] == 1001


def test_change_password_invalidates_old_token(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    resp = client.put("/api/v1/auth/password", headers=h,
                      json={"old_password": "Admin@123", "new_password": "NewPass@123"})
    assert resp.status_code == 200
    # old token no longer valid (iat < pwd_updated_at)
    assert client.get("/api/v1/auth/me", headers=h).json()["code"] == 1001
    # new password works
    assert _login(client, "admin", "NewPass@123").status_code == 200


def test_weak_password_rejected(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    resp = client.put("/api/v1/auth/password", headers=h,
                      json={"old_password": "Admin@123", "new_password": "weak"})
    assert resp.json()["code"] == 2001
```

Create `backend/tests/test_permissions.py`:
```python
import pytest
from fastapi import Depends, FastAPI
from starlette.testclient import TestClient

from app.core.deps import require_permission, CurrentUser, get_current_user


def test_require_permission_blocks_without_code():
    app = FastAPI()

    def fake_user():
        return CurrentUser(id="u1", username="x", role_code="employee",
                           data_scope="self", permissions={"employee:view"},
                           employee_id=None, department_id=None)

    @app.get("/need", dependencies=[Depends(require_permission("device:manage"))])
    def need():
        return {"ok": True}

    app.dependency_overrides[get_current_user] = fake_user
    from app.core.exceptions import register_exception_handlers
    register_exception_handlers(app)
    client = TestClient(app)
    assert client.get("/need").json()["code"] == 1003


def test_require_permission_allows_with_code():
    app = FastAPI()

    def fake_user():
        return CurrentUser(id="u1", username="x", role_code="it_admin",
                           data_scope="all", permissions={"device:manage"},
                           employee_id=None, department_id=None)

    @app.get("/need", dependencies=[Depends(require_permission("device:manage"))])
    def need():
        return {"ok": True}

    app.dependency_overrides[get_current_user] = fake_user
    client = TestClient(app)
    assert client.get("/need").json() == {"ok": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py tests/test_permissions.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement permission constants**

Create `backend/app/core/permissions.py`:
```python
DEPARTMENT_VIEW = "department:view"
DEPARTMENT_CREATE = "department:create"
DEPARTMENT_UPDATE = "department:update"
DEPARTMENT_DELETE = "department:delete"
EMPLOYEE_VIEW = "employee:view"
EMPLOYEE_CREATE = "employee:create"
EMPLOYEE_UPDATE = "employee:update"
EMPLOYEE_DELETE = "employee:delete"
EMPLOYEE_RESIGN = "employee:resign"
EMPLOYEE_IMPORT = "employee:import"
EMPLOYEE_EXPORT = "employee:export"
WORKSTATION_VIEW = "workstation:view"
WORKSTATION_MANAGE = "workstation:manage"
DEVICE_VIEW = "device:view"
DEVICE_MANAGE = "device:manage"
REPORT_VIEW = "report:view"
SYSTEM_USER = "system:user"
SYSTEM_ROLE = "system:role"
SYSTEM_LOG = "system:log"
SYSTEM_DICT = "system:dict"

ALL_PERMISSIONS: list[dict] = [
    {"code": DEPARTMENT_VIEW, "name": "查看部门", "module": "department"},
    {"code": DEPARTMENT_CREATE, "name": "新增部门", "module": "department"},
    {"code": DEPARTMENT_UPDATE, "name": "编辑部门", "module": "department"},
    {"code": DEPARTMENT_DELETE, "name": "删除部门", "module": "department"},
    {"code": EMPLOYEE_VIEW, "name": "查看员工", "module": "employee"},
    {"code": EMPLOYEE_CREATE, "name": "新增员工", "module": "employee"},
    {"code": EMPLOYEE_UPDATE, "name": "编辑员工", "module": "employee"},
    {"code": EMPLOYEE_DELETE, "name": "删除员工", "module": "employee"},
    {"code": EMPLOYEE_RESIGN, "name": "离职处理", "module": "employee"},
    {"code": EMPLOYEE_IMPORT, "name": "导入员工", "module": "employee"},
    {"code": EMPLOYEE_EXPORT, "name": "导出员工", "module": "employee"},
    {"code": WORKSTATION_VIEW, "name": "查看工位", "module": "workstation"},
    {"code": WORKSTATION_MANAGE, "name": "工位管理", "module": "workstation"},
    {"code": DEVICE_VIEW, "name": "查看设备", "module": "device"},
    {"code": DEVICE_MANAGE, "name": "设备管理", "module": "device"},
    {"code": REPORT_VIEW, "name": "查看报表", "module": "report"},
    {"code": SYSTEM_USER, "name": "账号管理", "module": "system"},
    {"code": SYSTEM_ROLE, "name": "角色权限", "module": "system"},
    {"code": SYSTEM_LOG, "name": "操作日志", "module": "system"},
    {"code": SYSTEM_DICT, "name": "数据字典", "module": "system"},
]
```

- [ ] **Step 4: Implement deps (current user + permission + data scope)**

Create `backend/app/core/deps.py`:
```python
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import unauthorized, forbidden
from app.core.redis import get_redis
from app.core.security import decode_token
from app.repositories import user_repo, role_repo


@dataclass
class CurrentUser:
    id: str
    username: str
    role_code: str
    data_scope: str
    permissions: set[str]
    employee_id: str | None
    department_id: str | None


def _extract_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise unauthorized()
    return header[len("Bearer "):]


def get_current_user(request: Request, db: Session = Depends(get_db),
                     redis=Depends(get_redis)) -> CurrentUser:
    token = _extract_token(request)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise unauthorized()
    if redis.get(f"blacklist:{payload['jti']}"):
        raise unauthorized()

    user = user_repo.get_active_by_id(db, payload["sub"])
    if user is None or user.status != 1:
        raise unauthorized()
    if user.pwd_updated_at is not None and payload["iat"] < int(user.pwd_updated_at.timestamp()):
        raise unauthorized()

    role = role_repo.get_by_id(db, user.role_id)
    if role is None:
        raise unauthorized()
    perms = role_repo.permission_codes_for_role(db, role.id)

    department_id = None
    if user.employee_id:
        from app.models import Employee
        emp = db.get(Employee, user.employee_id)
        department_id = emp.department_id if emp else None

    return CurrentUser(
        id=user.id, username=user.username, role_code=role.code,
        data_scope=role.data_scope, permissions=perms,
        employee_id=user.employee_id, department_id=department_id,
    )


def require_permission(code: str):
    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in user.permissions:
            raise forbidden()
        return user
    return _dep


def data_scope_descriptor(user: CurrentUser) -> dict:
    if user.data_scope == "all":
        return {"scope": "all"}
    if user.data_scope == "self":
        return {"scope": "self", "employee_id": user.employee_id}
    return {"scope": "dept", "department_id": user.department_id}
```
> Data-scope descriptor is produced here; actual query filtering is wired in slice 2/3.

- [ ] **Step 5: Implement auth schemas**

Create `backend/app/schemas/auth.py`:
```python
import re

from pydantic import BaseModel, field_validator

PWD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _policy(cls, v: str) -> str:
        if not PWD_RE.match(v):
            raise ValueError("密码需≥8位且包含大小写字母与数字")
        return v
```
> The `ValueError` in the validator surfaces as a 422 `RequestValidationError`, mapped to code 2001 by the handler.

- [ ] **Step 6: Implement auth service**

Create `backend/app/services/__init__.py` (empty).

Create `backend/app/services/auth_service.py`:
```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import unauthorized, account_locked, forbidden
from app.core.security import (
    verify_password, hash_password, create_access_token, create_refresh_token, decode_token,
)
from app.repositories import user_repo, role_repo, operation_log_repo


def _fail_key(username: str) -> str:
    return f"login_fail:{username}"


def _lock_key(username: str) -> str:
    return f"login_lock:{username}"


def _user_payload(db: Session, user) -> dict:
    role = role_repo.get_by_id(db, user.role_id)
    perms = sorted(role_repo.permission_codes_for_role(db, user.role_id))
    return {
        "id": user.id, "username": user.username,
        "role": role.code if role else None,
        "employee_id": user.employee_id, "permissions": perms,
    }


def login(db: Session, redis, username: str, password: str,
          ip: str | None = None, user_agent: str | None = None) -> dict:
    if redis.get(_lock_key(username)):
        raise account_locked()

    user = user_repo.get_active_by_username(db, username)
    if user is None or user.status != 1 or not verify_password(password, user.password_hash):
        fails = redis.incr(_fail_key(username))
        redis.expire(_fail_key(username), settings.login_lock_minutes * 60)
        if fails >= settings.login_max_fail:
            redis.setex(_lock_key(username), settings.login_lock_minutes * 60, "1")
        raise unauthorized("账号或密码错误")

    redis.delete(_fail_key(username))
    user_repo.update_last_login(db, user)
    operation_log_repo.create(db, user_id=user.id, module="auth", action="login",
                              ip=ip, user_agent=user_agent)
    db.commit()

    access, _, expires_in = create_access_token(user.id)
    refresh, _ = create_refresh_token(user.id)
    return {
        "access_token": access, "refresh_token": refresh, "token_type": "Bearer",
        "expires_in": expires_in, "user": _user_payload(db, user),
    }


def refresh(db: Session, redis, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise unauthorized()
    if redis.get(f"blacklist:{payload['jti']}"):
        raise unauthorized()
    user = user_repo.get_active_by_id(db, payload["sub"])
    if user is None or user.status != 1:
        raise unauthorized()
    access, _, expires_in = create_access_token(user.id)
    return {"access_token": access, "token_type": "Bearer", "expires_in": expires_in}


def logout(redis, access_payload: dict) -> None:
    ttl = access_payload["exp"] - int(datetime.now(timezone.utc).timestamp())
    if ttl > 0:
        redis.setex(f"blacklist:{access_payload['jti']}", ttl, "1")


def change_password(db: Session, user_id: str, old_password: str, new_password: str) -> None:
    user = user_repo.get_active_by_id(db, user_id)
    if user is None or not verify_password(old_password, user.password_hash):
        raise unauthorized("旧密码不正确")
    user_repo.set_password(db, user, hash_password(new_password))
    operation_log_repo.create(db, user_id=user.id, module="auth", action="change_password")
    db.commit()
```

- [ ] **Step 7: Implement auth router and wire it**

Create `backend/app/routers/__init__.py` (empty).

Create `backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.core.redis import get_redis
from app.core.response import envelope
from app.core.security import decode_token
from app.schemas.auth import LoginRequest, RefreshRequest, ChangePasswordRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db), redis=Depends(get_redis)):
    data = auth_service.login(
        db, redis, body.username, body.password,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return envelope(data=data)


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db), redis=Depends(get_redis)):
    return envelope(data=auth_service.refresh(db, redis, body.refresh_token))


@router.post("/logout")
def logout(request: Request, redis=Depends(get_redis), user: CurrentUser = Depends(get_current_user)):
    token = request.headers["Authorization"][len("Bearer "):]
    auth_service.logout(redis, decode_token(token))
    return envelope(message="已登出")


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return envelope(data={
        "id": user.id, "username": user.username, "role": user.role_code,
        "employee_id": user.employee_id, "permissions": sorted(user.permissions),
    })


@router.put("/password")
def change_password(body: ChangePasswordRequest, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    auth_service.change_password(db, user.id, body.old_password, body.new_password)
    return envelope(message="密码修改成功")
```

Modify `backend/app/api/v1.py` — replace the comment block with the include:
```python
from fastapi import APIRouter

from app.core.config import settings
from app.routers.auth import router as auth_router

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(auth_router)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_auth.py tests/test_permissions.py -v`
Expected: PASS (all auth + permission tests green).
> The `db` fixture rolls back per test, but `auth_service.login/change_password` call `db.commit()` on the test session. Since the session is bound to a connection with an outer transaction, `commit()` commits the savepoint/inner work but conftest's outer `trans.rollback()` still discards it after the test. If nested-transaction issues arise, the conftest `db` fixture uses `conn.begin()` + session bound to `conn`; SQLAlchemy's "commit as you go" on the session won't close the outer connection transaction. This is the standard pattern and tests remain isolated.

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/permissions.py backend/app/core/deps.py backend/app/schemas/auth.py backend/app/services backend/app/routers backend/app/api/v1.py backend/tests/test_auth.py backend/tests/test_permissions.py
git commit -m "$(cat <<'EOF'
feat(auth): JWT login/refresh/logout/me/password, RBAC deps, data-scope groundwork

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Seed script (roles, permissions, matrix, dict, super admin)

**Files:**
- Create: `backend/app/services/seed_service.py`
- Create: `backend/scripts/seed.py`
- Create: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: models, repos, `ALL_PERMISSIONS`, permission code constants, `hash_password`, `settings`.
- Produces:
  - `seed_service.seed_permissions(db)`, `seed_roles(db)`, `seed_role_permissions(db)`, `seed_dicts(db)`, `seed_admin(db)`, and `run_seed(db)` orchestrating all (idempotent).
  - `ROLE_MATRIX: dict[str, set[str]]` mapping role code → permission codes (§3.2).
  - `scripts/seed.py` CLI entry: opens a `SessionLocal`, calls `run_seed`, commits.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_seed.py`:
```python
from sqlalchemy import select

from app.models import Role, Permission, RolePermission, User, DataDict
from app.services import seed_service


def test_run_seed_is_idempotent(db, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "Admin@12345")
    # reload settings so seed_admin reads env
    from app.core import config
    config.get_settings.cache_clear()

    seed_service.run_seed(db)
    db.flush()
    seed_service.run_seed(db)  # second run must not duplicate
    db.flush()

    roles = db.execute(select(Role)).scalars().all()
    perms = db.execute(select(Permission)).scalars().all()
    admins = db.execute(select(User).where(User.username == "admin")).scalars().all()
    assert len(roles) == 5
    assert len(perms) == 20
    assert len(admins) == 1


def test_super_admin_has_all_permissions(db):
    seed_service.run_seed(db)
    db.flush()
    super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
    from app.repositories import role_repo
    codes = role_repo.permission_codes_for_role(db, super_role.id)
    assert len(codes) == 20


def test_hr_admin_has_no_device_permission(db):
    seed_service.run_seed(db)
    db.flush()
    hr = db.execute(select(Role).where(Role.code == "hr_admin")).scalar_one()
    from app.repositories import role_repo
    codes = role_repo.permission_codes_for_role(db, hr.id)
    assert not any(c.startswith("device:") for c in codes)
    assert "employee:create" in codes


def test_dicts_seeded(db):
    seed_service.run_seed(db)
    db.flush()
    genders = db.execute(select(DataDict).where(DataDict.dict_type == "gender")).scalars().all()
    assert len(genders) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed.py -v`
Expected: FAIL — seed_service not found.

- [ ] **Step 3: Implement seed service**

Create `backend/app/services/seed_service.py`:
```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import ALL_PERMISSIONS
from app.core.security import hash_password
from app.models import Role, Permission, RolePermission, User, DataDict

# §3.1 roles with data scope
ROLES = [
    {"code": "super_admin", "name": "超级管理员", "data_scope": "all"},
    {"code": "hr_admin", "name": "HR管理员", "data_scope": "all"},
    {"code": "it_admin", "name": "IT管理员", "data_scope": "all"},
    {"code": "dept_manager", "name": "部门主管", "data_scope": "dept"},
    {"code": "employee", "name": "普通员工", "data_scope": "self"},
]

ALL_CODES = {p["code"] for p in ALL_PERMISSIONS}

# §3.2 permission matrix (write ops for ws/device collapse to *:manage)
ROLE_MATRIX: dict[str, set[str]] = {
    "super_admin": set(ALL_CODES),
    "hr_admin": {
        "department:view", "department:create", "department:update", "department:delete",
        "employee:view", "employee:create", "employee:update", "employee:delete",
        "employee:resign", "employee:import", "employee:export",
        "workstation:view", "workstation:manage", "report:view",
    },
    "it_admin": {
        "department:view", "employee:view",
        "workstation:view", "workstation:manage",
        "device:view", "device:manage", "report:view",
    },
    "dept_manager": {
        "department:view", "employee:view", "workstation:view", "device:view", "report:view",
    },
    "employee": {
        "employee:view", "workstation:view", "device:view",
    },
}

DICTS = [
    ("gender", "0", "未知", 0), ("gender", "1", "男", 1), ("gender", "2", "女", 2),
    ("workstation_type", "fixed", "固定", 0),
    ("workstation_type", "shared", "共享", 1),
    ("workstation_type", "temp", "临时", 2),
    ("device_type", "desktop", "台式机", 0),
    ("device_type", "laptop", "笔记本", 1),
    ("device_type", "workstation", "工作站", 2),
]


def seed_permissions(db: Session) -> None:
    existing = {p.code for p in db.execute(select(Permission)).scalars().all()}
    for p in ALL_PERMISSIONS:
        if p["code"] not in existing:
            db.add(Permission(code=p["code"], name=p["name"], module=p["module"]))
    db.flush()


def seed_roles(db: Session) -> None:
    existing = {r.code for r in db.execute(select(Role)).scalars().all()}
    for r in ROLES:
        if r["code"] not in existing:
            db.add(Role(code=r["code"], name=r["name"], is_builtin=1,
                        data_scope=r["data_scope"], status=1))
    db.flush()


def seed_role_permissions(db: Session) -> None:
    roles = {r.code: r for r in db.execute(select(Role)).scalars().all()}
    perms = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
    for role_code, codes in ROLE_MATRIX.items():
        role = roles[role_code]
        have = {
            rp.permission_id
            for rp in db.execute(
                select(RolePermission).where(RolePermission.role_id == role.id)
            ).scalars().all()
        }
        for code in codes:
            pid = perms[code].id
            if pid not in have:
                db.add(RolePermission(role_id=role.id, permission_id=pid))
    db.flush()


def seed_dicts(db: Session) -> None:
    existing = {
        (d.dict_type, d.dict_key)
        for d in db.execute(select(DataDict)).scalars().all()
    }
    for dict_type, key, label, order in DICTS:
        if (dict_type, key) not in existing:
            db.add(DataDict(dict_type=dict_type, dict_key=key, dict_label=label,
                            sort_order=order, status=1))
    db.flush()


def seed_admin(db: Session) -> None:
    settings = get_settings()
    username = settings.seed_admin_username
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        return
    if not settings.seed_admin_password:
        raise RuntimeError("SEED_ADMIN_PASSWORD is not set")
    super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
    db.add(User(username=username, password_hash=hash_password(settings.seed_admin_password),
                role_id=super_role.id, status=1))
    db.flush()


def run_seed(db: Session) -> None:
    seed_permissions(db)
    seed_roles(db)
    seed_role_permissions(db)
    seed_dicts(db)
    seed_admin(db)
```

Create `backend/scripts/seed.py`:
```python
from app.core.database import SessionLocal
from app.services.seed_service import run_seed


def main() -> None:
    db = SessionLocal()
    try:
        run_seed(db)
        db.commit()
        print("Seed completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/seed_service.py backend/scripts/seed.py backend/tests/test_seed.py
git commit -m "$(cat <<'EOF'
feat(seed): idempotent seeding of roles, permission matrix, dicts, and super admin

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Full suite green, ruff clean, and run-book README

**Files:**
- Create: `backend/README.md`
- Modify: any files flagged by ruff.

- [ ] **Step 1: Run the full test suite**

From `backend/`:
Run: `pytest -v`
Expected: ALL tests pass (config, response, utils, models, migration, health, security, repositories, auth, permissions, seed).
> `test_migration.py` runs alembic against `ims_test`; ensure it runs (from `backend/`, `cwd="."`). If it conflicts with the `_schema` fixture's `create_all`, run it in isolation: `pytest tests/test_migration.py` then `pytest --ignore=tests/test_migration.py`.

- [ ] **Step 2: Lint**

Run: `ruff check .`
Expected: no errors (fix any reported issues, re-run).

- [ ] **Step 3: Manual smoke (real server)**

```bash
alembic upgrade head          # against ims
python -m scripts.seed        # or: python scripts/seed.py
uvicorn app.main:app --reload
```
Verify at `http://127.0.0.1:8000/docs`:
- `POST /api/v1/auth/login` with seeded admin → 200 + tokens + permissions (20 codes).
- `GET /api/v1/auth/me` with Bearer token → role `super_admin`.
- `POST /api/v1/auth/refresh` → new access token.
- `POST /api/v1/auth/logout` → then `/auth/me` returns code 1001.
- `GET /health` → `{healthy:true, db:ok, redis:ok}`.

- [ ] **Step 4: Write the run-book**

Create `backend/README.md`:
```markdown
# IMS Backend — Slice 1 (Foundation + Auth/RBAC)

## Prerequisites
- Python 3.11
- LAN MySQL 8 and Redis 7 reachable
- Databases created:
  ```sql
  CREATE DATABASE IF NOT EXISTS ims CHARACTER SET utf8mb4;
  CREATE DATABASE IF NOT EXISTS ims_test CHARACTER SET utf8mb4;
  ```

## Setup
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
pip install -e ".[dev]"
cp .env.example .env                # fill DB/Redis creds, JWT_SECRET, SEED_ADMIN_PASSWORD
```

## Database & seed
```bash
alembic upgrade head
python scripts/seed.py
```

## Run
```bash
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

## Test
```bash
pytest                             # runs against ims_test
ruff check .
```

## Auth quickstart
1. `POST /api/v1/auth/login` `{ "username": "admin", "password": "<SEED_ADMIN_PASSWORD>" }`
2. Use `Authorization: Bearer <access_token>` for protected endpoints.
3. `GET /api/v1/auth/me` returns role + permission codes.
```

- [ ] **Step 5: Commit**

```bash
git add backend/README.md
git commit -m "$(cat <<'EOF'
docs(backend): slice-1 run-book; full suite green and ruff clean

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review (performed against the spec)

**Spec coverage:**
- §2 目标与验收 → Tasks 1–11 (each DoD item mapped: venv/deps→T1, migration all tables→T5, seed→T10, auth closure→T9, health→T6, pytest green→T11).
- §3 目录结构 → created across T1–T10 exactly as specced.
- §4 数据模型 (11 tables, mixins, active_flag, two-step FK) → T4 (models) + T5 (migration).
- §5 认证/RBAC (JWT dual-token, blacklist, lockout, password policy, deps, data-scope, permission constants, 5 endpoints) → T7 (security) + T9 (service/deps/router/permissions).
- §6 横切基建 (response/pagination, error codes, trace_id, op-log write, health) → T2 + T6 + T8 (op-log repo) + T9 (op-log writes on login/change_password).
- §7 seed → T10.
- §8 config/.env → T1.
- §9 tests → every task is TDD; suite consolidated in T11.
- §10 run-book → T11 README.

**Placeholder scan:** No TBD/TODO; all steps contain real code and exact commands.

**Type consistency:** `CurrentUser` fields consistent across T9 producer and T9/T11 consumers; `create_access_token` returns `(token, jti, expires_in)` and callers unpack accordingly; `permission_codes_for_role` returns `set[str]` used consistently; envelope shape `{code,message,data,trace_id}` consistent everywhere.

**Known risk noted in-plan:** test transaction isolation with `db.commit()` in services (T9 Step 8 note) and migration-vs-create_all coexistence (T11 Step 1 note) — mitigations documented.
