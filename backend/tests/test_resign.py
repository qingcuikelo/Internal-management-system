from datetime import date

import pytest

from app.models import Role, Employee, User, Workstation, Device
from app.core.constants import WorkstationStatus, DeviceStatus
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


def test_resign_cascade(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    # employee with an occupied workstation, 2 checked-out devices, and a bound account
    emp = Employee(employee_no="R1", name="r", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    ws = Workstation(code="W-1", type="fixed", status=WorkstationStatus.OCCUPIED,
                     current_employee_id=emp.id, assign_date=date.today())
    d1 = Device(asset_code="D-1", type="laptop", status=DeviceStatus.IN_USE, current_employee_id=emp.id)
    d2 = Device(asset_code="D-2", type="laptop", status=DeviceStatus.IN_USE, current_employee_id=emp.id)
    seeded.add_all([ws, d1, d2])
    seeded.flush()
    bound = _user(seeded, "empacct", "employee", employee_id=emp.id)

    r = client.post(f"/api/v1/employees/{emp.id}/resign", headers=_h(tok),
                    json={"resign_date": date.today().isoformat()})
    data = r.json()["data"]
    assert r.json()["code"] == 0
    assert data["released_workstations"] == 1
    assert data["returned_devices"] == 2
    assert data["account_disabled"] is True

    seeded.refresh(emp)
    seeded.refresh(ws)
    seeded.refresh(d1)
    seeded.refresh(d2)
    seeded.refresh(bound)
    assert emp.status == 0 and emp.resign_date is not None
    assert ws.status == WorkstationStatus.IDLE and ws.current_employee_id is None
    assert d1.status == DeviceStatus.IN_STOCK and d1.current_employee_id is None
    assert d2.status == DeviceStatus.IN_STOCK and d2.current_employee_id is None
    assert bound.status == 0


def test_resign_requires_permission(client, seeded):
    emp = Employee(employee_no="R2", name="r", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _user(seeded, "itx", "it_admin")  # it_admin has NO employee:resign
    tok = _login(client, "itx")
    assert client.post(f"/api/v1/employees/{emp.id}/resign", headers=_h(tok),
                       json={"resign_date": date.today().isoformat()}).json()["code"] == 1003


def test_resign_already_resigned_rejected(client, seeded):
    from app.models import Employee
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    emp = Employee(employee_no="RR", name="rr", gender=1, status=0)  # already resigned
    seeded.add(emp)
    seeded.flush()
    r = client.post(f"/api/v1/employees/{emp.id}/resign", headers=_h(tok),
                    json={"resign_date": date.today().isoformat()})
    assert r.json()["code"] == 2001
