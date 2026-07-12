from datetime import date

from app.core.constants import DeviceStatus
from app.models import Employee
from app.repositories import device_repo
from app.schemas.common import PageParams


def _dev(db, code, status=DeviceStatus.IN_STOCK):
    d = device_repo.create(db, asset_code=code, type="laptop", status=status)
    db.flush(); return d


def _emp(db, no):
    e = Employee(employee_no=no, name=no, gender=1, status=1); db.add(e); db.flush(); return e


def test_checkout_optimistic(db):
    d = _dev(db, "AST-1"); e = _emp(db, "E1")
    v = d.version
    assert device_repo.checkout_if_available(db, d.id, e.id, date.today(), v, "op") == 1
    db.flush()
    assert device_repo.checkout_if_available(db, d.id, e.id, date.today(), v, "op") == 0  # stale


def test_return_and_repair_scrap(db):
    d = _dev(db, "AST-2"); e = _emp(db, "E2")
    device_repo.checkout_if_available(db, d.id, e.id, date.today(), d.version, "op"); db.flush()
    assert device_repo.return_if_in_use(db, d.id, "op") == 1; db.flush()
    assert device_repo.to_repair(db, d.id, "op") == 1; db.flush()  # in-stock -> repair
    db.refresh(d); assert d.status == DeviceStatus.REPAIR
    assert device_repo.to_scrap(db, d.id, "op") == 1  # repair -> scrap


def test_repair_blocked_when_in_use(db):
    d = _dev(db, "AST-3"); e = _emp(db, "E3")
    device_repo.checkout_if_available(db, d.id, e.id, date.today(), d.version, "op"); db.flush()
    assert device_repo.to_repair(db, d.id, "op") == 0  # in-use cannot go to repair directly


def test_paginate_scope(db):
    d = _dev(db, "AST-4"); e = _emp(db, "E4")
    device_repo.checkout_if_available(db, d.id, e.id, date.today(), d.version, "op"); db.flush()
    _dev(db, "AST-5")  # in-stock, no holder
    items, total = device_repo.paginate(db, params=PageParams(), scope={"mode": "employees", "employee_ids": {e.id}})
    codes = {x.asset_code for x in items}
    assert "AST-4" in codes and "AST-5" not in codes
