from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    parent_id: str | None = None
    manager_id: str | None = None
    sort_order: int = 0
    status: int = 1


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    parent_id: str | None = None
    manager_id: str | None = None
    sort_order: int | None = None
    status: int | None = None


class DepartmentOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    manager_id: str | None
    sort_order: int
    status: int
