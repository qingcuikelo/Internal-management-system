from datetime import date

from sqlalchemy import CHAR, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin, active_flag_column,
)


class Workstation(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin):
    __tablename__ = "workstations"
    __table_args__ = (UniqueConstraint("code", "active_flag", name="uk_ws_code_active"),)

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_employee_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    assign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_flag: Mapped[int | None] = active_flag_column()
