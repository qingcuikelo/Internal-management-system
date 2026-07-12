"""extend operation_logs.action to String(32) for assign_permissions

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("operation_logs", "action",
                    type_=sa.String(32),
                    existing_type=sa.String(16),
                    nullable=False)


def downgrade() -> None:
    op.alter_column("operation_logs", "action",
                    type_=sa.String(16),
                    existing_type=sa.String(32),
                    nullable=False)
