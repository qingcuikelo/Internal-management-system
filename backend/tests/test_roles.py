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
