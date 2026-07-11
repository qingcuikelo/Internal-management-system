from typing import Any

from pydantic import BaseModel, Field, field_validator


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    sort: str | None = None
    order: str = "desc"
    keyword: str | None = None

    @field_validator("page_size")
    @classmethod
    def _cap(cls, v: int) -> int:
        return min(v, 100)

    @field_validator("order")
    @classmethod
    def _order(cls, v: str) -> str:
        return v.lower() if v.lower() in ("asc", "desc") else "desc"


class PageResult(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


def paginate(items: list, total: int, params: PageParams) -> dict:
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size}
