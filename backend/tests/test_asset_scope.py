from app.core.deps import CurrentUser
from app.core.exceptions import conflict, invalid_state, BizError
from app.core.constants import WorkstationStatus, DeviceStatus
from app.models import Department, Employee
from app.repositories import employee_repo
from app.services import scope_service


def test_error_helpers():
    assert isinstance(conflict(), BizError) and conflict().code == 3001 and conflict().http_status == 409
    assert invalid_state().code == 3007 and invalid_state().http_status == 409


def test_status_constants():
    assert WorkstationStatus.IDLE == 1 and WorkstationStatus.OCCUPIED == 2
    assert DeviceStatus.IN_STOCK == 1 and DeviceStatus.IN_USE == 2


def _u(scope, dept=None, emp=None):
    return CurrentUser(id="u", username="x", role_code="r", data_scope=scope,
                       permissions=set(), employee_id=emp, department_id=dept)


def test_ids_in_departments(db):
    a = Department(name="A", sort_order=0, status=1)
    db.add(a)
    db.flush()
    e1 = Employee(employee_no="E1", name="a", gender=1, department_id=a.id, status=1)
    e2 = Employee(employee_no="E2", name="b", gender=1, department_id=a.id, status=1)
    e3 = Employee(employee_no="E3", name="c", gender=1, status=1)  # no dept
    db.add_all([e1, e2, e3])
    db.flush()
    ids = employee_repo.ids_in_departments(db, {a.id})
    assert ids == {e1.id, e2.id}
    assert employee_repo.ids_in_departments(db, set()) == set()


def test_asset_scope_modes(db):
    a = Department(name="A", sort_order=0, status=1)
    db.add(a)
    db.flush()
    e1 = Employee(employee_no="E1", name="a", gender=1, department_id=a.id, status=1)
    db.add(e1)
    db.flush()
    assert scope_service.asset_scope(db, _u("all")) == {"mode": "all"}
    assert scope_service.asset_scope(db, _u("self", emp="x")) == {"mode": "self", "employee_id": "x"}
    dept = scope_service.asset_scope(db, _u("dept", dept=a.id))
    assert dept["mode"] == "employees" and e1.id in dept["employee_ids"]
    none_dept = scope_service.asset_scope(db, _u("dept", dept=None))
    assert none_dept == {"mode": "employees", "employee_ids": set()}
