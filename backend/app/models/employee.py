from datetime import date

from sqlalchemy import CHAR, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, active_flag_column,
)


class Employee(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("employee_no", "active_flag", name="uk_employee_no_active"),)

    employee_no: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    department_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    direct_supervisor_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active_flag: Mapped[int | None] = active_flag_column()
