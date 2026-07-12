from pydantic import BaseModel, Field


class DictCreate(BaseModel):
    dict_type: str = Field(min_length=1, max_length=32)
    dict_key: str = Field(min_length=1, max_length=32)
    dict_label: str = Field(min_length=1, max_length=64)
    sort_order: int = 0
    status: int = 1


class DictUpdate(BaseModel):
    dict_label: str | None = None
    sort_order: int | None = None
    status: int | None = None


class DictOut(BaseModel):
    id: str
    dict_type: str
    dict_key: str
    dict_label: str
    sort_order: int
    status: int
