import pytest
from datetime import date, timedelta

from app.models import Role, Employee, User, Department, Workstation, Device
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


def test_employee_assets_as_super(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    emp = Employee(employee_no="E1", name="x", gender=1, department_id=dept.id, status=1)
    seeded.add(emp)
    seeded.flush()
    ws = Workstation(code="W1", type="fixed", status=2, current_employee_id=emp.id)
    d1 = Device(asset_code="D1", type="laptop", status=2, current_employee_id=emp.id, warranty_expire=date.today() + timedelta(days=60))
    seeded.add_all([ws, d1])
    seeded.flush()
    r = client.get(f"/api/v1/reports/employee-assets?employee_id={emp.id}", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["workstation"] is not None
    assert len(r["data"]["devices"]) >= 1


def test_employee_assets_out_of_scope_for_dept_manager(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    _login(client, "boss")
    dept_a = Department(name="A", status=1)
    dept_b = Department(name="B", status=1)
    seeded.add_all([dept_a, dept_b])
    seeded.flush()
    emp_a = Employee(employee_no="E1", name="a", gender=1, department_id=dept_a.id, status=1)
    emp_b = Employee(employee_no="E2", name="b", gender=1, department_id=dept_b.id, status=1)
    seeded.add_all([emp_a, emp_b])
    seeded.flush()
    _make_user(seeded, "mgr", "dept_manager", employee_id=emp_a.id)
    tok = _login(client, "mgr")
    # dept_manager in dept A queries employee in dept B -> 3404
    r = client.get(f"/api/v1/reports/employee-assets?employee_id={emp_b.id}", headers=_h(tok)).json()
    assert r["code"] == 3404


def test_idle_assets_as_global(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    seeded.add_all([
        Workstation(code="W1", type="fixed", status=1),
        Device(asset_code="D1", type="laptop", status=1, warranty_expire=date.today() + timedelta(days=30)),
    ])
    seeded.flush()
    r = client.get("/api/v1/reports/idle-assets", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["idle_workstations"] >= 1
    assert r["data"]["idle_devices"] >= 1


def test_idle_assets_dept_manager_gets_null(client, seeded):
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    emp = Employee(employee_no="E1", name="x", gender=1, department_id=dept.id, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "mgr", "dept_manager", employee_id=emp.id)
    tok = _login(client, "mgr")
    seeded.add_all([
        Workstation(code="W1", type="fixed", status=1),
        Device(asset_code="D1", type="laptop", status=1, warranty_expire=date.today() + timedelta(days=30)),
    ])
    seeded.flush()
    r = client.get("/api/v1/reports/idle-assets", headers=_h(tok)).json()
    assert r["code"] == 0
    assert r["data"]["idle_workstations"] is None


def test_device_by_department(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    emp = Employee(employee_no="E1", name="x", gender=1, department_id=dept.id, status=1)
    seeded.add(emp)
    seeded.flush()
    d = Device(asset_code="D1", type="laptop", status=2, current_employee_id=emp.id, warranty_expire=date.today() + timedelta(days=30))
    seeded.add(d)
    seeded.flush()
    r = client.get("/api/v1/reports/device-by-department", headers=_h(tok)).json()
    assert r["code"] == 0
    assert any(item["department_id"] == dept.id and item["count"] >= 1 for item in r["data"]["items"])


def test_warranty_expiring(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    d = Device(asset_code="D1", type="laptop", status=2, warranty_expire=date.today() + timedelta(days=10))
    seeded.add(d)
    seeded.flush()
    r = client.get("/api/v1/reports/warranty-expiring?days=30", headers=_h(tok)).json()
    assert r["code"] == 0
    assert len(r["data"]["items"]) >= 1


def test_non_holder_forbidden(client, seeded):
    emp = Employee(employee_no="E1", name="x", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    # employee role has no report:view
    r = client.get("/api/v1/reports/idle-assets", headers=_h(tok)).json()
    assert r["code"] == 1003


def test_warranty_expiring_dept_manager_scope(client, seeded):
    dept_a = Department(name="A", status=1)
    dept_b = Department(name="B", status=1)
    seeded.add_all([dept_a, dept_b])
    seeded.flush()
    emp_a = Employee(employee_no="EA", name="a", gender=1, department_id=dept_a.id, status=1)
    emp_b = Employee(employee_no="EB", name="b", gender=1, department_id=dept_b.id, status=1)
    seeded.add_all([emp_a, emp_b])
    seeded.flush()
    d1 = Device(asset_code="WD1", type="laptop", status=2, current_employee_id=emp_a.id, warranty_expire=date.today() + timedelta(days=10))
    d2 = Device(asset_code="WD2", type="desktop", status=2, current_employee_id=emp_b.id, warranty_expire=date.today() + timedelta(days=15))
    seeded.add_all([d1, d2])
    seeded.flush()
    _make_user(seeded, "mgr", "dept_manager", employee_id=emp_a.id)
    tok = _login(client, "mgr")
    r = client.get("/api/v1/reports/warranty-expiring?days=30", headers=_h(tok)).json()
    assert r["code"] == 0
    codes = [item["asset_code"] for item in r["data"]["items"]]
    assert "WD1" in codes
    assert "WD2" not in codes
