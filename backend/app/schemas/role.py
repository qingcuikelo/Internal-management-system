from pydantic import BaseModel, Field, field_validator


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    data_scope: str = "all"
    status: int = 1

    @field_validator("data_scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v not in ("all", "dept", "self"):
            raise ValueError("data_scope must be all/dept/self")
        return v


class RoleUpdate(BaseModel):
    name: str | None = None
    data_scope: str | None = None
    status: int | None = None

    @field_validator("data_scope")
    @classmethod
    def _scope(cls, v):
        if v is not None and v not in ("all", "dept", "self"):
            raise ValueError("data_scope must be all/dept/self")
        return v


class PermissionAssignReq(BaseModel):
    codes: list[str]


class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    is_builtin: int
    data_scope: str
    status: int
