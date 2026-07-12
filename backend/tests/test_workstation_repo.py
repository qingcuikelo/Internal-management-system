from datetime import date

from app.core.constants import WorkstationStatus
from app.models import Employee, Role, User
from app.repositories import workstation_repo, assignment_repo
from app.schemas.common import PageParams


def _ws(db, code, status=WorkstationStatus.IDLE):
    w = workstation_repo.create(db, code=code, type="fixed", status=status)
    db.flush()
    return w


def _emp(db, no):
    e = Employee(employee_no=no, name=no, gender=1, status=1)
    db.add(e)
    db.flush()
    return e


def _op_user(db):
    role = Role(code="op_role", name="op_role", data_scope="all", status=1)
    db.add(role)
    db.flush()
    u = User(id="op", username="operator", password_hash="x", role_id=role.id, status=1)
    db.add(u)
    db.flush()
    return u


def test_assign_if_free_optimistic(db):
    w = _ws(db, "A-1")
    e = _emp(db, "E1")
    v = w.version
    n1 = workstation_repo.assign_if_free(db, w.id, e.id, date.today(), v, "op")
    assert n1 == 1
    db.flush()
    # second attempt with the STALE version must fail (row now has version+1, status occupied)
    n2 = workstation_repo.assign_if_free(db, w.id, e.id, date.today(), v, "op")
    assert n2 == 0


def test_release_if_occupied(db):
    w = _ws(db, "A-2")
    e = _emp(db, "E2")
    workstation_repo.assign_if_free(db, w.id, e.id, date.today(), w.version, "op")
    db.flush()
    n = workstation_repo.release_if_occupied(db, w.id, "op")
    assert n == 1
    db.flush()
    db.refresh(w)
    assert w.status == WorkstationStatus.IDLE and w.current_employee_id is None


def test_set_status_blocked_when_occupied(db):
    w = _ws(db, "A-3")
    e = _emp(db, "E3")
    workstation_repo.assign_if_free(db, w.id, e.id, date.today(), w.version, "op")
    db.flush()
    assert workstation_repo.set_status(db, w.id, WorkstationStatus.DISABLED, "op") == 0  # occupied -> blocked


def test_history_open_and_close(db):
    w = _ws(db, "A-4")
    e = _emp(db, "E4")
    u = _op_user(db)
    assignment_repo.create_ws(db, w.id, e.id, date.today(), u.id)
    db.flush()
    assert len(assignment_repo.list_ws(db, w.id)) == 1
    n = assignment_repo.close_ws_open(db, w.id, date.today())
    assert n == 1


def test_paginate_scope(db):
    a = _ws(db, "A-5")
    e = _emp(db, "E5")
    workstation_repo.assign_if_free(db, a.id, e.id, date.today(), a.version, "op")
    db.flush()
    _ws(db, "A-6")  # idle, no occupant — intentionally discarded
    # dept scope with employee e -> sees occupied one, not the idle one
    items, total = workstation_repo.paginate(
        db, params=PageParams(), scope={"mode": "employees", "employee_ids": {e.id}})
    codes = {w.code for w in items}
    assert "A-5" in codes and "A-6" not in codes
    # empty employees -> nothing
    _, t0 = workstation_repo.paginate(db, params=PageParams(), scope={"mode": "employees", "employee_ids": set()})
    assert t0 == 0
