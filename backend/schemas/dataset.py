from typing import Literal

from pydantic import BaseModel, Field


class DatasetStats(BaseModel):
    total_images: int = 0
    annotated_images: int = 0
    unannotated_images: int = 0
    classes: int = 0
    total_objects: int = 0


class DatasetImage(BaseModel):
    id: str
    filename: str
    relative_path: str
    width: int
    height: int
    annotation_status: Literal["annotated", "unannotated"] = "unannotated"
    annotation_count: int = 0


class DatasetState(BaseModel):
    project_id: str
    stats: DatasetStats


class ImportIssue(BaseModel):
    filename: str
    reason: str


class ImportResult(BaseModel):
    imported_count: int
    stats: DatasetStats
    issues: list[ImportIssue] = Field(default_factory=list)
