from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base, PKMixin, TimestampMixin, SoftDeleteMixin, active_flag_column,
)


class User(Base, PKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", "active_flag", name="uk_username_active"),)

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("roles.id"), nullable=False)
    employee_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_login_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    pwd_updated_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
    active_flag: Mapped[int | None] = active_flag_column()
