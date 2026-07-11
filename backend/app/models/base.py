from datetime import datetime, timezone

from sqlalchemy import CHAR, Computed, Integer, String, event
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.uuidv7 import uuid7


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _auto_set_pk(target, args, kwargs) -> None:
    """Auto-generate a UUID7 primary key when `id` is not provided."""
    if "id" not in kwargs and hasattr(target, "id") and target.id is None:
        target.id = uuid7()


class Base(DeclarativeBase):
    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Register an init-event listener on each mapped subclass to auto-set its PK."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "id"):
            event.listen(cls, "init", _auto_set_pk)


class PKMixin:
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), default=now_utc, onupdate=now_utc, nullable=False
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)


class AuditMixin:
    created_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)


class VersionMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def active_flag_column() -> Mapped[int | None]:
    # Generated column: 1 when not deleted, NULL when deleted.
    # Used with a composite UNIQUE index (business_key, active_flag) so
    # uniqueness only applies among non-deleted rows.
    return mapped_column(
        Integer,
        Computed("IF(deleted_at IS NULL, 1, NULL)", persisted=True),
        nullable=True,
    )
