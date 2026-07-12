import pytest

from app.core.security import hash_password
from app.models import User, Role, Permission, RolePermission


@pytest.fixture()
def admin_user(db):
    role = Role(code="super_admin", name="超管", is_builtin=1, data_scope="all", status=1)
    perm = Permission(code="employee:view", name="查看员工", module="employee")
    db.add_all([role, perm])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    u = User(username="admin", password_hash=hash_password("Admin@123"),
             role_id=role.id, status=1)
    db.add(u)
    db.flush()
    return u


def _login(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_login_success_returns_tokens(client, admin_user):
    resp = _login(client, "admin", "Admin@123")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"] and data["refresh_token"]
    assert data["user"]["username"] == "admin"
    assert "employee:view" in data["user"]["permissions"]


def test_login_wrong_password_fails(client, admin_user):
    resp = _login(client, "admin", "nope")
    assert resp.json()["code"] == 1001


def test_login_lockout_after_5_failures(client, admin_user):
    for _ in range(5):
        _login(client, "admin", "nope")
    resp = _login(client, "admin", "Admin@123")
    assert resp.json()["code"] == 1002  # locked despite correct password


def test_me_returns_permissions(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "super_admin"


def test_refresh_issues_new_access(client, admin_user):
    refresh = _login(client, "admin", "Admin@123").json()["data"]["refresh_token"]
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


def test_logout_blacklists_token(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).json()["code"] == 1001


def test_change_password_invalidates_old_token(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    resp = client.put("/api/v1/auth/password", headers=h,
                      json={"old_password": "Admin@123", "new_password": "NewPass@123"})
    assert resp.status_code == 200
    # old token no longer valid (iat < pwd_updated_at)
    assert client.get("/api/v1/auth/me", headers=h).json()["code"] == 1001
    # new password works
    assert _login(client, "admin", "NewPass@123").status_code == 200


def test_refresh_rejected_after_password_change(client, admin_user):
    tokens = _login(client, "admin", "Admin@123").json()["data"]
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    client.put("/api/v1/auth/password", headers={"Authorization": f"Bearer {access}"},
               json={"old_password": "Admin@123", "new_password": "NewPass@123"})
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.json()["code"] == 1001


def test_weak_password_rejected(client, admin_user):
    token = _login(client, "admin", "Admin@123").json()["data"]["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    resp = client.put("/api/v1/auth/password", headers=h,
                      json={"old_password": "Admin@123", "new_password": "weak"})
    assert resp.json()["code"] == 2001
