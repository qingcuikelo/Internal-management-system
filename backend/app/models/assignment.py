from datetime import date, datetime

from sqlalchemy import CHAR, Date, ForeignKey
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, now_utc


class WorkstationAssignment(Base, PKMixin):
    __tablename__ = "workstation_assignments"

    workstation_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("workstations.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("employees.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    operator_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), default=now_utc, nullable=False)


class DeviceAssignment(Base, PKMixin):
    __tablename__ = "device_assignments"

    device_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("devices.id"), nullable=False)
    employee_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("employees.id"), nullable=False)
    checkout_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    operator_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), default=now_utc, nullable=False)
