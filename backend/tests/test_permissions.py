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
