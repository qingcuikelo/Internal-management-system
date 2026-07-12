from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role_id: str
    employee_id: str | None = None
    status: int = 1


class UserUpdate(BaseModel):
    role_id: str | None = None
    employee_id: str | None = None
    status: int | None = None


class UserStatusReq(BaseModel):
    status: int = Field(ge=0, le=1)


class ResetPasswordReq(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    role_id: str
    role_code: str | None = None
    role_name: str | None = None
    employee_id: str | None = None
    status: int
    last_login_at: datetime | None = None
    created_at: datetime | None = None
