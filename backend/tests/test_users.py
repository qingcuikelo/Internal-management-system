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
