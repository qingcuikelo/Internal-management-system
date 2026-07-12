from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, data_scope_descriptor
from app.repositories import department_repo, employee_repo
from app.utils.tree import descendant_ids


def accessible_department_ids(db: Session, user: CurrentUser) -> set[str] | None:
    desc = data_scope_descriptor(user)
    if desc["scope"] == "all":
        return None
    if desc["scope"] == "dept":
        dept_id = desc.get("department_id")
        if not dept_id:
            return set()
        rows = department_repo.all_id_parent_rows(db)
        return descendant_ids(rows, dept_id)
    # self scope has no department visibility
    return set()


def employee_scope(db: Session, user: CurrentUser) -> dict:
    desc = data_scope_descriptor(user)
    if desc["scope"] == "all":
        return {"mode": "all"}
    if desc["scope"] == "self":
        return {"mode": "self", "employee_id": desc.get("employee_id")}
    ids = accessible_department_ids(db, user) or set()
    return {"mode": "dept", "dept_ids": ids}


def asset_scope(db: Session, user: CurrentUser) -> dict:
    desc = data_scope_descriptor(user)
    if desc["scope"] == "all":
        return {"mode": "all"}
    if desc["scope"] == "self":
        return {"mode": "self", "employee_id": desc.get("employee_id")}
    dept_ids = accessible_department_ids(db, user) or set()
    return {"mode": "employees", "employee_ids": employee_repo.ids_in_departments(db, dept_ids)}
