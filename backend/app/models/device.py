from datetime import date

from sqlalchemy import CHAR, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin, active_flag_column,
)


class Device(Base, PKMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, VersionMixin):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("asset_code", "active_flag", name="uk_dev_asset_active"),
        UniqueConstraint("serial_number", "active_flag", name="uk_dev_serial_active"),
    )

    asset_code: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    specs: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_expire: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_employee_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    assign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_flag: Mapped[int | None] = active_flag_column()
