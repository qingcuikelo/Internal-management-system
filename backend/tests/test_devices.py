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
