from app.core.deps import CurrentUser
from app.repositories import department_repo
from app.services import scope_service


def _u(scope, dept=None, emp=None):
    return CurrentUser(id="u", username="x", role_code="r", data_scope=scope,
                       permissions=set(), employee_id=emp, department_id=dept)


def test_all_scope_unrestricted(db):
    assert scope_service.accessible_department_ids(db, _u("all")) is None
    assert scope_service.employee_scope(db, _u("all")) == {"mode": "all"}


def test_dept_scope_subtree(db):
    a = department_repo.create(db, name="A", sort_order=0, status=1)
    db.flush()
    b = department_repo.create(db, name="B", parent_id=a.id, sort_order=0, status=1)
    db.flush()
    c = department_repo.create(db, name="C", sort_order=0, status=1)
    db.flush()
    ids = scope_service.accessible_department_ids(db, _u("dept", dept=a.id))
    assert ids == {a.id, b.id}
    assert c.id not in ids
    es = scope_service.employee_scope(db, _u("dept", dept=a.id))
    assert es["mode"] == "dept" and es["dept_ids"] == {a.id, b.id}


def test_dept_scope_none_department_is_empty(db):
    assert scope_service.accessible_department_ids(db, _u("dept", dept=None)) == set()
    assert scope_service.employee_scope(db, _u("dept", dept=None))["dept_ids"] == set()


def test_self_scope(db):
    es = scope_service.employee_scope(db, _u("self", emp="e-1"))
    assert es == {"mode": "self", "employee_id": "e-1"}
