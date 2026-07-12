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
