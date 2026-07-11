from app.models import Base, User


EXPECTED_TABLES = {
    "users", "roles", "permissions", "role_permissions",
    "departments", "employees", "workstations", "devices",
    "workstation_assignments", "device_assignments",
    "operation_logs", "data_dict",
}


def test_all_tables_registered():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_user_columns():
    cols = Base.metadata.tables["users"].columns
    for name in ("id", "username", "password_hash", "role_id", "employee_id",
                 "status", "last_login_at", "pwd_updated_at",
                 "created_at", "updated_at", "deleted_at"):
        assert name in cols


def test_new_instance_gets_uuid():
    u = User(username="a", password_hash="x", role_id="r", status=1)
    assert u.id is not None and len(u.id) == 36


def test_version_column_on_workstation_and_device():
    assert "version" in Base.metadata.tables["workstations"].columns
    assert "version" in Base.metadata.tables["devices"].columns
