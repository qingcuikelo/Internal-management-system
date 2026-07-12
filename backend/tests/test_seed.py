from sqlalchemy import select

from app.models import Role, Permission, RolePermission, User, DataDict
from app.services import seed_service


def test_run_seed_is_idempotent(db, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "Admin@12345")
    # reload settings so seed_admin reads env
    from app.core import config
    config.get_settings.cache_clear()

    seed_service.run_seed(db)
    db.flush()
    seed_service.run_seed(db)  # second run must not duplicate
    db.flush()

    roles = db.execute(select(Role)).scalars().all()
    perms = db.execute(select(Permission)).scalars().all()
    admins = db.execute(select(User).where(User.username == "admin")).scalars().all()
    assert len(roles) == 5
    assert len(perms) == 20
    assert len(admins) == 1


def test_super_admin_has_all_permissions(db):
    seed_service.run_seed(db)
    db.flush()
    super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
    from app.repositories import role_repo
    codes = role_repo.permission_codes_for_role(db, super_role.id)
    assert len(codes) == 20


def test_hr_admin_has_no_device_permission(db):
    seed_service.run_seed(db)
    db.flush()
    hr = db.execute(select(Role).where(Role.code == "hr_admin")).scalar_one()
    from app.repositories import role_repo
    codes = role_repo.permission_codes_for_role(db, hr.id)
    assert not any(c.startswith("device:") for c in codes)
    assert "employee:create" in codes


def test_dicts_seeded(db):
    seed_service.run_seed(db)
    db.flush()
    genders = db.execute(select(DataDict).where(DataDict.dict_type == "gender")).scalars().all()
    assert len(genders) >= 2
