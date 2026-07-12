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
