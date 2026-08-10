from datetime import datetime

from pydantic import BaseModel, Field, field_validator

HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class ClassRecord(BaseModel):
    id: int
    name: str
    color: str
    created_at: datetime
    usage_count: int = 0


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=HEX_COLOR_PATTERN)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Class name is required")
        return trimmed


class ClassUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=HEX_COLOR_PATTERN)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Class name is required")
        return trimmed


class DeleteClassResponse(BaseModel):
    deleted_id: int

