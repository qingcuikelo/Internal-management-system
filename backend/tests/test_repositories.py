
from app.models import User, Role, Permission, RolePermission
from app.repositories import user_repo, role_repo, operation_log_repo
from app.core.security import hash_password


def _seed_role_with_perm(db):
    role = Role(code="t_admin", name="T", is_builtin=0, data_scope="all", status=1)
    perm = Permission(code="employee:view", name="查看员工", module="employee")
    db.add_all([role, perm])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.flush()
    return role, perm


def test_get_active_by_username(db):
    role, _ = _seed_role_with_perm(db)
    u = User(username="alice", password_hash=hash_password("Abc12345"),
             role_id=role.id, status=1)
    db.add(u)
    db.flush()
    found = user_repo.get_active_by_username(db, "alice")
    assert found is not None and found.id == u.id
    assert user_repo.get_active_by_username(db, "nobody") is None


def test_permission_codes_for_role(db):
    role, _ = _seed_role_with_perm(db)
    codes = role_repo.permission_codes_for_role(db, role.id)
    assert codes == {"employee:view"}


def test_set_password_updates_timestamp(db):
    role, _ = _seed_role_with_perm(db)
    u = User(username="bob", password_hash=hash_password("Abc12345"),
             role_id=role.id, status=1)
    db.add(u)
    db.flush()
    user_repo.set_password(db, u, hash_password("New12345"))
    db.flush()
    assert u.pwd_updated_at is not None


def test_operation_log_create(db):
    role, _ = _seed_role_with_perm(db)
    u = User(username="carol", password_hash="x", role_id=role.id, status=1)
    db.add(u)
    db.flush()
    log = operation_log_repo.create(db, user_id=u.id, module="auth", action="login")
    db.flush()
    assert log.id is not None and log.module == "auth"
