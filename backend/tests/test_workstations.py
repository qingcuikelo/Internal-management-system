import pytest

from app.models import Role, Employee, User, Department
from app.core.security import hash_password
from app.services import seed_service


@pytest.fixture()
def seeded(db):
    seed_service.run_seed(db)
    db.flush()
    return db


def _role_id(db, code):
    return db.query(Role).filter(Role.code == code).one().id


def _user(db, username, role_code, employee_id=None):
    u = User(username=username, password_hash=hash_password("Passw0rd"),
             role_id=_role_id(db, role_code), employee_id=employee_id, status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, u):
    return client.post("/api/v1/auth/login", json={"username": u, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _emp(db, no, dept=None):
    e = Employee(employee_no=no, name=no, gender=1, department_id=dept, status=1)
    db.add(e)
    db.flush()
    return e


def test_create_assign_release_history(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E1")
    wid = client.post("/api/v1/workstations", headers=_h(tok),
                      json={"code": "A-1", "type": "fixed"}).json()["data"]["id"]
    r = client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok),
                    json={"employee_id": e.id})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == 2
    # double assign -> conflict 3001
    r2 = client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok),
                     json={"employee_id": e.id})
    assert r2.json()["code"] == 3001
    assert client.post(f"/api/v1/workstations/{wid}/release", headers=_h(tok)).json()["code"] == 0
    hist = client.get(f"/api/v1/workstations/{wid}/history", headers=_h(tok)).json()["data"]
    assert len(hist) == 1 and hist[0]["end_date"] is not None


def test_stale_version_conflict(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E2")
    wid = client.post("/api/v1/workstations", headers=_h(tok),
                      json={"code": "A-2", "type": "fixed"}).json()["data"]["id"]
    # assign with explicit stale version 999 -> conflict
    r = client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok),
                    json={"employee_id": e.id, "version": 999})
    assert r.json()["code"] == 3001


def test_batch_release(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    e = _emp(seeded, "E3")
    ids = []
    for c in ("B-1", "B-2"):
        wid = client.post("/api/v1/workstations", headers=_h(tok), json={"code": c, "type": "fixed"}).json()["data"]["id"]
        client.post(f"/api/v1/workstations/{wid}/assign", headers=_h(tok), json={"employee_id": e.id})
        ids.append(wid)
    r = client.post("/api/v1/workstations/batch-release", headers=_h(tok), json={"workstation_ids": ids})
    assert r.json()["data"]["released"] == 2


def test_status_reserve(client, seeded):
    _user(seeded, "it", "it_admin")
    tok = _login(client, "it")
    wid = client.post("/api/v1/workstations", headers=_h(tok), json={"code": "C-1", "type": "fixed"}).json()["data"]["id"]
    r = client.patch(f"/api/v1/workstations/{wid}/status", headers=_h(tok), json={"status": 3})
    assert r.json()["code"] == 0 and r.json()["data"]["status"] == 3


def test_data_scope_and_idle_invisible(client, seeded):
    _user(seeded, "it", "it_admin")
    it = _login(client, "it")
    a = Department(name="A", sort_order=0, status=1)
    seeded.add(a)
    seeded.flush()
    mgr = _emp(seeded, "M", dept=a.id)
    occupied = client.post("/api/v1/workstations", headers=_h(it), json={"code": "D-1", "type": "fixed"}).json()["data"]["id"]
    client.post(f"/api/v1/workstations/{occupied}/assign", headers=_h(it), json={"employee_id": mgr.id})
    client.post("/api/v1/workstations", headers=_h(it), json={"code": "D-2", "type": "fixed"})  # idle
    _user(seeded, "mgr", "dept_manager", employee_id=mgr.id)
    tok = _login(client, "mgr")
    data = client.get("/api/v1/workstations", headers=_h(tok)).json()["data"]
    codes = {w["code"] for w in data["items"]}
    assert codes == {"D-1"}  # occupied by in-scope employee; idle D-2 invisible


def test_hr_can_manage_workstations_but_not_devices_perm(client, seeded):
    # workstation:manage includes hr_admin
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    r = client.post("/api/v1/workstations", headers=_h(tok), json={"code": "H-1", "type": "fixed"})
    assert r.json()["code"] == 0
