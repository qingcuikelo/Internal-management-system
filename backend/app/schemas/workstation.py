from datetime import date

from pydantic import BaseModel, Field


class WorkstationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    location: str | None = Field(default=None, max_length=128)
    type: str = Field(min_length=1, max_length=16)
    notes: str | None = Field(default=None, max_length=255)


class WorkstationUpdate(BaseModel):
    location: str | None = Field(default=None, max_length=128)
    type: str | None = Field(default=None, max_length=16)
    notes: str | None = Field(default=None, max_length=255)


class WorkstationAssignReq(BaseModel):
    employee_id: str
    assign_date: date | None = None
    version: int | None = None


class WorkstationStatusReq(BaseModel):
    status: int  # 1=idle,3=reserved,4=disabled (validated in service)


class BatchReleaseReq(BaseModel):
    workstation_ids: list[str] = Field(min_length=1)
