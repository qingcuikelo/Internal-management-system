from app.models import Department, Employee
from app.repositories import department_repo
from app.core.exceptions import not_found, BizError


def test_not_found_helper():
    e = not_found()
    assert isinstance(e, BizError) and e.code == 3404 and e.http_status == 404


def _dept(db, name, parent_id=None):
    d = department_repo.create(db, name=name, parent_id=parent_id, sort_order=0, status=1)
    db.flush()
    return d


def test_list_and_rows(db):
    a = _dept(db, "A")
    b = _dept(db, "B", parent_id=a.id)
    rows = department_repo.all_id_parent_rows(db)
    assert (a.id, None) in rows and (b.id, a.id) in rows


def test_has_active_children(db):
    a = _dept(db, "A")
    assert department_repo.has_active_children(db, a.id) is False
    _dept(db, "B", parent_id=a.id)
    assert department_repo.has_active_children(db, a.id) is True


def test_has_active_employees(db):
    a = _dept(db, "A")
    assert department_repo.has_active_employees(db, a.id) is False
    db.add(Employee(employee_no="E1", name="x", gender=1, department_id=a.id, status=1))
    db.flush()
    assert department_repo.has_active_employees(db, a.id) is True


def test_soft_delete(db):
    a = _dept(db, "A")
    department_repo.soft_delete(db, a)
    db.flush()
    assert department_repo.get_active(db, a.id) is None
