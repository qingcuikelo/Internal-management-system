import subprocess
import os

from sqlalchemy import create_engine, inspect

from app.core.config import settings

EXPECTED = {
    "users", "roles", "permissions", "role_permissions", "departments",
    "employees", "workstations", "devices", "workstation_assignments",
    "device_assignments", "operation_logs", "data_dict", "alembic_version",
}


def _alembic(*args):
    env = {**os.environ, "ALEMBIC_TARGET": "test"}
    return subprocess.run(
        ["alembic", *args], cwd=".", env=env, capture_output=True, text=True
    )


def test_upgrade_creates_all_tables():
    _alembic("downgrade", "base")
    up = _alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr

    engine = create_engine(settings.sqlalchemy_test_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert EXPECTED.issubset(tables)


def test_circular_fk_present():
    _alembic("upgrade", "head")
    engine = create_engine(settings.sqlalchemy_test_url)
    insp = inspect(engine)
    dep_fks = {fk["referred_table"] for fk in insp.get_foreign_keys("departments")}
    emp_fks = {fk["referred_table"] for fk in insp.get_foreign_keys("employees")}
    engine.dispose()
    assert "employees" in dep_fks       # departments.manager_id -> employees
    assert "departments" in emp_fks     # employees.department_id -> departments
