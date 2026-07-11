from sqlalchemy import CHAR, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin


class Department(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    manager_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
