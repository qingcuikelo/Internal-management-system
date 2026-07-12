"""baseline: all 11 tables + circular FKs

Revision ID: 0001
Revises:
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DT = mysql.DATETIME(fsp=3)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("is_builtin", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_scope", sa.String(16), nullable=False),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.UniqueConstraint("code", name="uk_role_code"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.UniqueConstraint("code", name="uk_perm_code"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.CHAR(36), nullable=False),
        sa.Column("permission_id", sa.CHAR(36), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", sa.CHAR(36), nullable=False),
        sa.Column("employee_id", sa.CHAR(36), nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_login_at", DT, nullable=True),
        sa.Column("pwd_updated_at", DT, nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.UniqueConstraint("username", "active_flag", name="uk_username_active"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_users_employee_id", "users", ["employee_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("parent_id", sa.CHAR(36), nullable=True),
        sa.Column("manager_id", sa.CHAR(36), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_dept_parent_id", "departments", ["parent_id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("employee_no", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("gender", sa.Integer, nullable=False),
        sa.Column("email", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("department_id", sa.CHAR(36), nullable=True),
        sa.Column("direct_supervisor_id", sa.CHAR(36), nullable=True),
        sa.Column("position", sa.String(64), nullable=True),
        sa.Column("hire_date", sa.Date, nullable=True),
        sa.Column("resign_date", sa.Date, nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.UniqueConstraint("employee_no", "active_flag", name="uk_employee_no_active"),
        sa.UniqueConstraint("email", name="uk_employee_email"),
        sa.UniqueConstraint("phone", name="uk_employee_phone"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_emp_department_id", "employees", ["department_id"])
    op.create_index("idx_emp_supervisor_id", "employees", ["direct_supervisor_id"])

    op.create_table(
        "workstations",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("location", sa.String(128), nullable=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("current_employee_id", sa.CHAR(36), nullable=True),
        sa.Column("assign_date", sa.Date, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["current_employee_id"], ["employees.id"]),
        sa.UniqueConstraint("code", "active_flag", name="uk_ws_code_active"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_ws_current_emp", "workstations", ["current_employee_id"])
    op.create_index("idx_ws_status", "workstations", ["status"])

    op.create_table(
        "devices",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("asset_code", sa.String(32), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("brand", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("serial_number", sa.String(64), nullable=True),
        sa.Column("specs", sa.String(255), nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("warranty_expire", sa.Date, nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("current_employee_id", sa.CHAR(36), nullable=True),
        sa.Column("assign_date", sa.Date, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_by", sa.CHAR(36), nullable=True),
        sa.Column("updated_by", sa.CHAR(36), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("deleted_at", DT, nullable=True),
        sa.Column("active_flag", sa.Integer,
                  sa.Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True), nullable=True),
        sa.ForeignKeyConstraint(["current_employee_id"], ["employees.id"]),
        sa.UniqueConstraint("asset_code", "active_flag", name="uk_dev_asset_active"),
        sa.UniqueConstraint("serial_number", "active_flag", name="uk_dev_serial_active"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_dev_status", "devices", ["status"])
    op.create_index("idx_dev_current_emp", "devices", ["current_employee_id"])
    op.create_index("idx_dev_warranty", "devices", ["warranty_expire"])

    op.create_table(
        "workstation_assignments",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("workstation_id", sa.CHAR(36), nullable=False),
        sa.Column("employee_id", sa.CHAR(36), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("operator_id", sa.CHAR(36), nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.ForeignKeyConstraint(["workstation_id"], ["workstations.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_wsa_ws", "workstation_assignments", ["workstation_id"])
    op.create_index("idx_wsa_emp", "workstation_assignments", ["employee_id"])

    op.create_table(
        "device_assignments",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("device_id", sa.CHAR(36), nullable=False),
        sa.Column("employee_id", sa.CHAR(36), nullable=False),
        sa.Column("checkout_date", sa.Date, nullable=False),
        sa.Column("return_date", sa.Date, nullable=True),
        sa.Column("operator_id", sa.CHAR(36), nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_da_dev", "device_assignments", ["device_id"])
    op.create_index("idx_da_emp", "device_assignments", ["employee_id"])

    op.create_table(
        "operation_logs",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("user_id", sa.CHAR(36), nullable=False),
        sa.Column("module", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.CHAR(36), nullable=True),
        sa.Column("detail", mysql.JSON, nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", DT, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )
    op.create_index("idx_oplog_user", "operation_logs", ["user_id"])
    op.create_index("idx_oplog_created", "operation_logs", ["created_at"])
    op.create_index("idx_oplog_target", "operation_logs", ["target_type", "target_id"])

    op.create_table(
        "data_dict",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("dict_type", sa.String(32), nullable=False),
        sa.Column("dict_key", sa.String(32), nullable=False),
        sa.Column("dict_label", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("dict_type", "dict_key", name="uk_dict_type_key"),
        mysql_engine="InnoDB", mysql_charset="utf8mb4",
    )

    # --- step 2: circular / late FKs ---
    op.create_foreign_key("fk_users_employee", "users", "employees", ["employee_id"], ["id"])
    op.create_foreign_key("fk_dept_parent", "departments", "departments", ["parent_id"], ["id"])
    op.create_foreign_key("fk_dept_manager", "departments", "employees", ["manager_id"], ["id"])
    op.create_foreign_key("fk_emp_dept", "employees", "departments", ["department_id"], ["id"])
    op.create_foreign_key("fk_emp_supervisor", "employees", "employees", ["direct_supervisor_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_emp_supervisor", "employees", type_="foreignkey")
    op.drop_constraint("fk_emp_dept", "employees", type_="foreignkey")
    op.drop_constraint("fk_dept_manager", "departments", type_="foreignkey")
    op.drop_constraint("fk_dept_parent", "departments", type_="foreignkey")
    op.drop_constraint("fk_users_employee", "users", type_="foreignkey")
    for t in ("data_dict", "operation_logs", "device_assignments", "workstation_assignments",
              "devices", "workstations", "employees", "departments", "users",
              "role_permissions", "permissions", "roles"):
        op.drop_table(t)
