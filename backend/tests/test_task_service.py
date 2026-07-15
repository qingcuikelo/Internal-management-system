import json
import os

import pytest

from app.core.security import hash_password
from app.models import Role, User
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
