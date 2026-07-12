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
    db.add(u); db.flush()
    return u


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_department_crud_and_tree_as_admin(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    # create root + child
    r = client.post("/api/v1/departments", headers=_h(tok), json={"name": "总部"})
    assert r.json()["code"] == 0
    root_id = r.json()["data"]["id"]
    c = client.post("/api/v1/departments", headers=_h(tok),
                    json={"name": "研发部", "parent_id": root_id})
    assert c.json()["code"] == 0
    tree = client.get("/api/v1/departments/tree", headers=_h(tok)).json()["data"]
    assert tree[0]["name"] == "总部" and tree[0]["children"][0]["name"] == "研发部"


def test_delete_blocked_by_children(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    root_id = client.post("/api/v1/departments", headers=_h(tok), json={"name": "A"}).json()["data"]["id"]
    client.post("/api/v1/departments", headers=_h(tok), json={"name": "B", "parent_id": root_id})
    r = client.delete(f"/api/v1/departments/{root_id}", headers=_h(tok))
    assert r.json()["code"] == 3002


def test_delete_blocked_by_employees(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    did = client.post("/api/v1/departments", headers=_h(tok), json={"name": "A"}).json()["data"]["id"]
    seeded.add(Employee(employee_no="E9", name="y", gender=1, department_id=did, status=1)); seeded.flush()
    r = client.delete(f"/api/v1/departments/{did}", headers=_h(tok))
    assert r.json()["code"] == 3002


def test_update_parent_cycle_rejected(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    a = client.post("/api/v1/departments", headers=_h(tok), json={"name": "A"}).json()["data"]["id"]
    b = client.post("/api/v1/departments", headers=_h(tok), json={"name": "B", "parent_id": a}).json()["data"]["id"]
    # make A's parent = B (B is A's descendant) -> cycle
    r = client.put(f"/api/v1/departments/{a}", headers=_h(tok), json={"parent_id": b})
    assert r.json()["code"] == 3003


def test_dept_manager_sees_only_subtree(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    boss = _login(client, "boss")
    a = client.post("/api/v1/departments", headers=_h(boss), json={"name": "A"}).json()["data"]["id"]
    b = client.post("/api/v1/departments", headers=_h(boss), json={"name": "B", "parent_id": a}).json()["data"]["id"]
    other = client.post("/api/v1/departments", headers=_h(boss), json={"name": "Other"}).json()["data"]["id"]
    # a manager employee in dept A
    mgr_emp = Employee(employee_no="M1", name="mgr", gender=1, department_id=a, status=1)
    seeded.add(mgr_emp); seeded.flush()
    _make_user(seeded, "mgr", "dept_manager", employee_id=mgr_emp.id)
    tok = _login(client, "mgr")
    listing = client.get("/api/v1/departments", headers=_h(tok)).json()["data"]["items"]
    names = {d["name"] for d in listing}
    assert names == {"A", "B"}  # not "Other"
    # out-of-scope detail -> 404 (3404)
    assert client.get(f"/api/v1/departments/{other}", headers=_h(tok)).json()["code"] == 3404


def test_employee_role_has_no_department_access(client, seeded):
    emp = Employee(employee_no="P1", name="p", gender=1, status=1)
    seeded.add(emp); seeded.flush()
    _make_user(seeded, "self1", "employee", employee_id=emp.id)
    tok = _login(client, "self1")
    assert client.get("/api/v1/departments", headers=_h(tok)).json()["code"] == 1003
