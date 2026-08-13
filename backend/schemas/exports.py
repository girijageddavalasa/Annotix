from datetime import datetime

from pydantic import BaseModel, Field


class ExportIssue(BaseModel):
    image_id: str | None = None
    annotation_id: str | None = None
    message: str


class ExportStats(BaseModel):
    images: int = 0
    annotated_images: int = 0
    objects: int = 0
    classes: int = 0
    train_images: int = 0
    validation_images: int = 0


class ExportPreview(BaseModel):
    format: str = "yolo"
    source: str
    source_snapshot: str | None = None
    stats: ExportStats
    issues: list[ExportIssue] = Field(default_factory=list)


class ExportRecord(ExportPreview):
    id: str
    project_id: str
    created_at: datetime
    filename: str

