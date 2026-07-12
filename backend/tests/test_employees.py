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


def _login(client, username):
    return client.post("/api/v1/auth/login",
                       json={"username": username, "password": "Passw0rd"}).json()["data"]["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _dept(db, name, parent=None):
    d = Department(name=name, parent_id=parent, sort_order=0, status=1)
    db.add(d)
    db.flush()
    return d


def test_create_list_filter(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    d = _dept(seeded, "研发")
    r = client.post("/api/v1/employees", headers=_h(tok),
                    json={"employee_no": "E100", "name": "张三", "gender": 1, "department_id": d.id})
    assert r.json()["code"] == 0
    data = client.get("/api/v1/employees?keyword=张", headers=_h(tok)).json()["data"]
    assert data["total"] == 1 and data["items"][0]["name"] == "张三"


def test_duplicate_employee_no_rejected(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    body = {"employee_no": "E1", "name": "a", "gender": 1}
    assert client.post("/api/v1/employees", headers=_h(tok), json=body).json()["code"] == 0
    assert client.post("/api/v1/employees", headers=_h(tok), json=body).json()["code"] == 3005


def test_supervisor_cycle_rejected(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    a = client.post("/api/v1/employees", headers=_h(tok),
                    json={"employee_no": "A", "name": "a", "gender": 1}).json()["data"]["id"]
    b = client.post("/api/v1/employees", headers=_h(tok),
                    json={"employee_no": "B", "name": "b", "gender": 1, "direct_supervisor_id": a}).json()["data"]["id"]
    # set a's supervisor = b (b already reports to a) -> cycle
    r = client.put(f"/api/v1/employees/{a}", headers=_h(tok), json={"direct_supervisor_id": b})
    assert r.json()["code"] == 3004


def test_batch_department(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    d = _dept(seeded, "新部门")
    ids = [client.post("/api/v1/employees", headers=_h(tok),
                       json={"employee_no": f"N{i}", "name": f"n{i}", "gender": 1}).json()["data"]["id"]
           for i in range(2)]
    r = client.patch("/api/v1/employees/batch-department", headers=_h(tok),
                     json={"employee_ids": ids, "department_id": d.id})
    assert r.json()["code"] == 0 and r.json()["data"]["updated"] == 2


def test_dept_manager_scope_and_out_of_scope_404(client, seeded):
    _user(seeded, "hr", "hr_admin")
    hr = _login(client, "hr")
    a = _dept(seeded, "A")
    b = _dept(seeded, "B", parent=a.id)
    other = _dept(seeded, "Other")
    mgr = Employee(employee_no="M", name="m", gender=1, department_id=a.id, status=1)
    seeded.add(mgr)
    seeded.flush()
    in_b = client.post("/api/v1/employees", headers=_h(hr),
                       json={"employee_no": "IB", "name": "inb", "gender": 1, "department_id": b.id}).json()["data"]["id"]
    out = client.post("/api/v1/employees", headers=_h(hr),
                      json={"employee_no": "OUT", "name": "o", "gender": 1, "department_id": other.id}).json()["data"]["id"]
    _user(seeded, "mgr", "dept_manager", employee_id=mgr.id)
    tok = _login(client, "mgr")
    data = client.get("/api/v1/employees", headers=_h(tok)).json()["data"]
    nos = {i["employee_no"] for i in data["items"]}
    assert "IB" in nos and "M" in nos and "OUT" not in nos
    assert client.get(f"/api/v1/employees/{out}", headers=_h(tok)).json()["code"] == 3404
    assert client.get(f"/api/v1/employees/{in_b}", headers=_h(tok)).json()["code"] == 0


def test_employee_self_scope(client, seeded):
    _user(seeded, "hr", "hr_admin")
    me = Employee(employee_no="SELF", name="me", gender=1, status=1)
    other = Employee(employee_no="OTH", name="oth", gender=1, status=1)
    seeded.add_all([me, other])
    seeded.flush()
    _user(seeded, "self1", "employee", employee_id=me.id)
    tok = _login(client, "self1")
    data = client.get("/api/v1/employees", headers=_h(tok)).json()["data"]
    assert data["total"] == 1 and data["items"][0]["employee_no"] == "SELF"
    assert client.get(f"/api/v1/employees/{other.id}", headers=_h(tok)).json()["code"] == 3404


def test_update_fields(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    eid = client.post("/api/v1/employees", headers=_h(tok),
                      json={"employee_no": "U1", "name": "old", "gender": 1}).json()["data"]["id"]
    r = client.put(f"/api/v1/employees/{eid}", headers=_h(tok),
                   json={"name": "new", "position": "工程师"})
    assert r.json()["code"] == 0
    assert client.get(f"/api/v1/employees/{eid}", headers=_h(tok)).json()["data"]["name"] == "new"


def test_delete_soft(client, seeded):
    _user(seeded, "hr", "hr_admin")
    tok = _login(client, "hr")
    eid = client.post("/api/v1/employees", headers=_h(tok),
                      json={"employee_no": "D1", "name": "d", "gender": 1}).json()["data"]["id"]
    assert client.delete(f"/api/v1/employees/{eid}", headers=_h(tok)).json()["code"] == 0
    assert client.get(f"/api/v1/employees/{eid}", headers=_h(tok)).json()["code"] == 3404


def test_out_of_scope_update_delete_404(seeded):
    # Scope check lives in the service layer (out-of-scope target -> not_found 3404).
    # Use a dept-scoped CurrentUser that HAS employee:update/delete (a hypothetical custom
    # role) so we exercise the scope gate itself, not the permission gate. The built-in
    # dept_manager is read-only for employees (see test below) and can never reach here.
    from app.core.deps import CurrentUser
    from app.core.exceptions import BizError
    from app.models import Department, Employee
    from app.schemas.employee import EmployeeUpdate
    from app.services import employee_service
    a = Department(name="A", sort_order=0, status=1)
    other = Department(name="Other", sort_order=0, status=1)
    seeded.add_all([a, other])
    seeded.flush()
    out_emp = Employee(employee_no="OO", name="o", gender=1, department_id=other.id, status=1)
    seeded.add(out_emp)
    seeded.flush()
    real_user = _user(seeded, "cust_mgr", "dept_manager")
    user = CurrentUser(id=real_user.id, username="cust_mgr", role_code="custom_dept",
                       data_scope="dept", permissions={"employee:update", "employee:delete"},
                       employee_id=None, department_id=a.id)

    class _Req:
        client = None
        headers = {}

    with pytest.raises(BizError) as ei:
        employee_service.update(seeded, user, out_emp.id, EmployeeUpdate(name="x"), _Req())
    assert ei.value.code == 3404
    with pytest.raises(BizError) as ei2:
        employee_service.delete(seeded, user, out_emp.id, _Req())
    assert ei2.value.code == 3404


def test_dept_manager_cannot_write_employees(client, seeded):
    # §3.2: dept_manager is READ-ONLY for employees. Guards against re-granting write perms.
    _user(seeded, "hr", "hr_admin")
    hr = _login(client, "hr")
    eid = client.post("/api/v1/employees", headers=_h(hr),
                      json={"employee_no": "RO", "name": "ro", "gender": 1}).json()["data"]["id"]
    mgr = Employee(employee_no="M3", name="m3", gender=1, status=1)
    seeded.add(mgr)
    seeded.flush()
    _user(seeded, "mgr3", "dept_manager", employee_id=mgr.id)
    tok = _login(client, "mgr3")
    assert client.post("/api/v1/employees", headers=_h(tok),
                       json={"employee_no": "Z", "name": "z", "gender": 1}).json()["code"] == 1003
    assert client.put(f"/api/v1/employees/{eid}", headers=_h(tok),
                      json={"name": "x"}).json()["code"] == 1003
    assert client.delete(f"/api/v1/employees/{eid}", headers=_h(tok)).json()["code"] == 1003


def test_batch_department_respects_dept_scope(seeded):
    from app.core.deps import CurrentUser
    from app.models import Department, Employee
    from app.schemas.employee import BatchDepartmentReq
    from app.services import employee_service
    a = Department(name="A", sort_order=0, status=1)
    other = Department(name="Other", sort_order=0, status=1)
    dest = Department(name="Dest", sort_order=0, status=1)
    seeded.add_all([a, other, dest])
    seeded.flush()
    in_scope = Employee(employee_no="IN", name="i", gender=1, department_id=a.id, status=1)
    out_scope = Employee(employee_no="OUT", name="o", gender=1, department_id=other.id, status=1)
    seeded.add_all([in_scope, out_scope])
    seeded.flush()
    real_user = _user(seeded, "scope_u", "dept_manager")
    user = CurrentUser(id=real_user.id, username="scope_u", role_code="dept_manager",
                       data_scope="dept", permissions={"employee:update"},
                       employee_id=None, department_id=a.id)
    req = BatchDepartmentReq(employee_ids=[in_scope.id, out_scope.id], department_id=dest.id)

    class _Req:
        client = None
        headers = {}
    result = employee_service.batch_department(seeded, user, req, _Req())
    assert result["updated"] == 1  # only the in-scope employee moved
    seeded.refresh(in_scope)
    seeded.refresh(out_scope)
    assert in_scope.department_id == dest.id
    assert out_scope.department_id == other.id  # unchanged
