from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProjectStats(BaseModel):
    images: int = 0
    annotations: int = 0
    classes: int = 0


class ProjectRecord(BaseModel):
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    stats: ProjectStats = Field(default_factory=ProjectStats)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        return value


class ProjectUpdate(ProjectCreate):
    pass


class ProjectListResponse(BaseModel):
    current_project_id: str
    projects: list[ProjectRecord]


class ProjectDeleteResponse(BaseModel):
    deleted_id: str
    current_project: ProjectRecord

