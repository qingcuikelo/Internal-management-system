from app.schemas.common import PageParams
from app.repositories import employee_repo, department_repo


def _emp(db, no, name, dept=None, sup=None, status=1):
    e = employee_repo.create(db, employee_no=no, name=name, gender=1,
                             department_id=dept, direct_supervisor_id=sup, status=status)
    db.flush()
    return e


def _dept(db, id_):
    d = department_repo.create(db, id=id_, name=id_, sort_order=0, status=1)
    db.flush()
    return d


def test_paginate_keyword_and_filter_all_scope(db):
    d1 = _dept(db, "d1")
    d2 = _dept(db, "d2")
    _emp(db, "E1", "张三", dept=d1.id)
    _emp(db, "E2", "李四", dept=d2.id)
    items, total = employee_repo.paginate(
        db, params=PageParams(keyword="张"), scope={"mode": "all"})
    assert total == 1 and items[0].name == "张三"
    items, total = employee_repo.paginate(
        db, params=PageParams(), department_id=d2.id, scope={"mode": "all"})
    assert total == 1 and items[0].employee_no == "E2"


def test_paginate_dept_scope(db):
    d1 = _dept(db, "d1")
    d2 = _dept(db, "d2")
    _emp(db, "E1", "a", dept=d1.id)
    _emp(db, "E2", "b", dept=d2.id)
    items, total = employee_repo.paginate(
        db, params=PageParams(), scope={"mode": "dept", "dept_ids": {d1.id}})
    assert total == 1 and items[0].department_id == d1.id
    # empty dept set -> no rows
    _, total0 = employee_repo.paginate(db, params=PageParams(), scope={"mode": "dept", "dept_ids": set()})
    assert total0 == 0


def test_paginate_self_scope(db):
    e = _emp(db, "E1", "a")
    _emp(db, "E2", "b")
    items, total = employee_repo.paginate(
        db, params=PageParams(), scope={"mode": "self", "employee_id": e.id})
    assert total == 1 and items[0].id == e.id
    _, total0 = employee_repo.paginate(db, params=PageParams(), scope={"mode": "self", "employee_id": None})
    assert total0 == 0


def test_dup_check_and_batch_and_chain(db):
    d = _dept(db, "dX")
    a = _emp(db, "E1", "a")
    b = _emp(db, "E2", "b", sup=a.id)
    assert employee_repo.get_by_employee_no(db, "E1").id == a.id
    n = employee_repo.batch_set_department(db, [a.id, b.id], d.id)
    assert n == 2
    # chain: starting from b, walking up hits a
    assert employee_repo.supervisor_chain_has(db, b.id, a.id) is True
    assert employee_repo.supervisor_chain_has(db, a.id, b.id) is False
