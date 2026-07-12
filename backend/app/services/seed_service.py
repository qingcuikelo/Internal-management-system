from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import ALL_PERMISSIONS
from app.core.security import hash_password
from app.models import Role, Permission, RolePermission, User, DataDict

# §3.1 roles with data scope
ROLES = [
    {"code": "super_admin", "name": "超级管理员", "data_scope": "all"},
    {"code": "hr_admin", "name": "HR管理员", "data_scope": "all"},
    {"code": "it_admin", "name": "IT管理员", "data_scope": "all"},
    {"code": "dept_manager", "name": "部门主管", "data_scope": "dept"},
    {"code": "employee", "name": "普通员工", "data_scope": "self"},
]

ALL_CODES = {p["code"] for p in ALL_PERMISSIONS}

# §3.2 permission matrix (write ops for ws/device collapse to *:manage)
ROLE_MATRIX: dict[str, set[str]] = {
    "super_admin": set(ALL_CODES),
    "hr_admin": {
        "department:view", "department:create", "department:update", "department:delete",
        "employee:view", "employee:create", "employee:update", "employee:delete",
        "employee:resign", "employee:import", "employee:export",
        "workstation:view", "workstation:manage", "report:view",
    },
    "it_admin": {
        "department:view", "employee:view",
        "workstation:view", "workstation:manage",
        "device:view", "device:manage", "report:view",
    },
    "dept_manager": {
        "department:view", "employee:view", "workstation:view", "device:view", "report:view",
    },
    "employee": {
        "employee:view", "workstation:view", "device:view",
    },
}

DICTS = [
    ("gender", "0", "未知", 0), ("gender", "1", "男", 1), ("gender", "2", "女", 2),
    ("workstation_type", "fixed", "固定", 0),
    ("workstation_type", "shared", "共享", 1),
    ("workstation_type", "temp", "临时", 2),
    ("device_type", "desktop", "台式机", 0),
    ("device_type", "laptop", "笔记本", 1),
    ("device_type", "workstation", "工作站", 2),
]


def seed_permissions(db: Session) -> None:
    existing = {p.code for p in db.execute(select(Permission)).scalars().all()}
    for p in ALL_PERMISSIONS:
        if p["code"] not in existing:
            db.add(Permission(code=p["code"], name=p["name"], module=p["module"]))
    db.flush()


def seed_roles(db: Session) -> None:
    existing = {r.code for r in db.execute(select(Role)).scalars().all()}
    for r in ROLES:
        if r["code"] not in existing:
            db.add(Role(code=r["code"], name=r["name"], is_builtin=1,
                        data_scope=r["data_scope"], status=1))
    db.flush()


def seed_role_permissions(db: Session) -> None:
    roles = {r.code: r for r in db.execute(select(Role)).scalars().all()}
    perms = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
    for role_code, codes in ROLE_MATRIX.items():
        role = roles[role_code]
        have = {
            rp.permission_id
            for rp in db.execute(
                select(RolePermission).where(RolePermission.role_id == role.id)
            ).scalars().all()
        }
        for code in codes:
            pid = perms[code].id
            if pid not in have:
                db.add(RolePermission(role_id=role.id, permission_id=pid))
    db.flush()


def seed_dicts(db: Session) -> None:
    existing = {
        (d.dict_type, d.dict_key)
        for d in db.execute(select(DataDict)).scalars().all()
    }
    for dict_type, key, label, order in DICTS:
        if (dict_type, key) not in existing:
            db.add(DataDict(dict_type=dict_type, dict_key=key, dict_label=label,
                            sort_order=order, status=1))
    db.flush()


def seed_admin(db: Session) -> None:
    settings = get_settings()
    username = settings.seed_admin_username
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        return
    if not settings.seed_admin_password:
        raise RuntimeError("SEED_ADMIN_PASSWORD is not set")
    super_role = db.execute(select(Role).where(Role.code == "super_admin")).scalar_one()
    db.add(User(username=username, password_hash=hash_password(settings.seed_admin_password),
                role_id=super_role.id, status=1))
    db.flush()


def run_seed(db: Session) -> None:
    seed_permissions(db)
    seed_roles(db)
    seed_role_permissions(db)
    seed_dicts(db)
    seed_admin(db)
