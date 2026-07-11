from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, PKMixin


class DataDict(Base, PKMixin):
    __tablename__ = "data_dict"
    __table_args__ = (UniqueConstraint("dict_type", "dict_key", name="uk_dict_type_key"),)

    dict_type: Mapped[str] = mapped_column(String(32), nullable=False)
    dict_key: Mapped[str] = mapped_column(String(32), nullable=False)
    dict_label: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
