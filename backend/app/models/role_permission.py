from sqlalchemy import CHAR, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("permissions.id"), primary_key=True
    )
