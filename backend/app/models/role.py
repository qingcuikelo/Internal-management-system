from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin, TimestampMixin


class Role(Base, PKMixin, TimestampMixin):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_builtin: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_scope: Mapped[str] = mapped_column(String(16), nullable=False)  # all/dept/self
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
