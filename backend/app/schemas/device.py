from datetime import date

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    asset_code: str = Field(min_length=1, max_length=32)
    type: str = Field(min_length=1, max_length=16)
    brand: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=64)
    specs: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    warranty_expire: date | None = None
    notes: str | None = Field(default=None, max_length=255)


class DeviceUpdate(BaseModel):
    type: str | None = Field(default=None, max_length=16)
    brand: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=64)
    serial_number: str | None = Field(default=None, max_length=64)
    specs: str | None = Field(default=None, max_length=255)
    purchase_date: date | None = None
    warranty_expire: date | None = None
    notes: str | None = Field(default=None, max_length=255)


class DeviceCheckoutReq(BaseModel):
    employee_id: str
    assign_date: date | None = None
    version: int | None = None
