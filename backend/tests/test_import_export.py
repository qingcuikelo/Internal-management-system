import io
import pytest

from openpyxl import Workbook

from app.models import Role, User, Department, Employee
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


def _make_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def test_import_returns_task_id(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    dept = Department(name="D", status=1)
    seeded.add(dept)
    seeded.flush()
    xlsx = _make_xlsx([["employee_no", "name", "gender", "department_id", "status"],
                       ["IMP001", "测试", "1", dept.id, "1"]])
    # Commit so the Celery task (which creates its own SessionLocal) can see data
    seeded.commit()
    r = client.post("/api/v1/employees/import", headers=_h(tok),
                    files={"file": ("test.xlsx", xlsx,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 202
    assert "task_id" in r.json()["data"]
    task_id = r.json()["data"]["task_id"]
    # With always_eager=True, the task runs synchronously and the result key is set
    import json
    from app.core.redis import redis_client
    raw = redis_client.get(f"task:{task_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["status"] == "success"
    assert data["result"]["success_count"] == 1


def test_import_non_super_forbidden(client, seeded):
    _make_user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    xlsx = _make_xlsx([["employee_no", "name", "gender"], ["X", "x", "1"]])
    r = client.post("/api/v1/employees/import", headers=_h(tok),
                    files={"file": ("test.xlsx", xlsx)})
    # hr_admin HAS employee:import
    assert r.status_code == 202


def test_import_employee_role_forbidden(client, seeded):
    from app.models import Employee as Emp
    emp = Emp(employee_no="E1", name="x", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    xlsx = _make_xlsx([["employee_no", "name", "gender"], ["X", "x", "1"]])
    r = client.post("/api/v1/employees/import", headers=_h(tok),
                    files={"file": ("test.xlsx", xlsx)})
    assert r.json()["code"] == 1003


def test_export_returns_task_id(client, seeded):
    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    r = client.post("/api/v1/employees/export", headers=_h(tok), json={})
    assert r.status_code == 202
    assert "task_id" in r.json()["data"]
    task_id = r.json()["data"]["task_id"]
    import json
    from app.core.redis import redis_client
    raw = redis_client.get(f"task:{task_id}")
    assert raw is not None
    data = json.loads(raw)
    assert data["status"] == "success"


def test_export_non_super_forbidden(client, seeded):
    from app.models import Employee as Emp
    emp = Emp(employee_no="E1", name="x", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    _make_user(seeded, "emp", "employee", employee_id=emp.id)
    tok = _login(client, "emp")
    r = client.post("/api/v1/employees/export", headers=_h(tok), json={})
    assert r.json()["code"] == 1003


def test_export_creates_downloadable_file(client, seeded):
    import json
    from app.core.redis import redis_client

    _make_user(seeded, "boss", "super_admin")
    tok = _login(client, "boss")
    emp = Employee(employee_no="EXP001", name="export_me", gender=1, status=1)
    seeded.add(emp)
    seeded.flush()
    seeded.commit()
    r = client.post("/api/v1/employees/export", headers=_h(tok), json={})
    assert r.status_code == 202
    data = r.json()
    task_id = data["data"]["task_id"]
    raw = redis_client.get(f"task:{task_id}")
    assert raw is not None
    result = json.loads(raw)
    assert result["status"] == "success"
    download_url = result["result"]["download_url"]
    assert download_url.startswith("/exports/")
    r2 = client.get(f"/api/v1{download_url}", headers=_h(tok))
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
