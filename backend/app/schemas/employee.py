from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmployeeCreate(BaseModel):
    employee_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    gender: int
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    department_id: str | None = None
    direct_supervisor_id: str | None = None
    position: str | None = Field(default=None, max_length=64)
    hire_date: date | None = None

    @field_validator("gender")
    @classmethod
    def _g(cls, v: int) -> int:
        if v not in (0, 1, 2):
            raise ValueError("gender must be 0/1/2")
        return v


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    gender: int | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    department_id: str | None = None
    direct_supervisor_id: str | None = None
    position: str | None = Field(default=None, max_length=64)
    hire_date: date | None = None
    status: int | None = None

    @field_validator("gender")
    @classmethod
    def _g(cls, v):
        if v is not None and v not in (0, 1, 2):
            raise ValueError("gender must be 0/1/2")
        return v


class BatchDepartmentReq(BaseModel):
    employee_ids: list[str] = Field(min_length=1)
    department_id: str | None = None
