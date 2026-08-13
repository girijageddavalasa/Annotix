from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ModelVersion(BaseModel):
    id: str
    created_at: datetime
    completed_at: datetime
    class_count: int
    best_weights: str


class PredictionStartRequest(BaseModel):
    model_id: str
    mode: Literal['current', 'unannotated']
    image_id: str | None = None
    confidence_threshold: float = Field(default=.25, ge=.05, le=.95)
    max_detections: Literal[25, 50, 100, 200] = 100

    @model_validator(mode='after')
    def require_current_image(self):
        if self.mode == 'current' and not self.image_id:
            raise ValueError('image_id is required for current-image prediction')
        return self


class PredictionRecord(BaseModel):
    id: str
    run_id: str
    image_id: str
    model_id: str
    class_id: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    original_class_id: int
    original_box: list[float]
    status: Literal['pending', 'accepted', 'edited', 'rejected'] = 'pending'
    corrected: bool = False
    edit_history: list[dict] = Field(default_factory=list)
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    annotation_id: str | None = None


class PredictionUpdate(BaseModel):
    class_id: int | None = None
    x1: float | None = Field(default=None, ge=0)
    y1: float | None = Field(default=None, ge=0)
    x2: float | None = Field(default=None, ge=0)
    y2: float | None = Field(default=None, ge=0)


class PredictionAcceptRequest(BaseModel):
    prediction_ids: list[str]


class PredictionListResponse(BaseModel):
    image_id: str
    predictions: list[PredictionRecord]


class PredictionJob(BaseModel):
    id: str
    project_id: str
    model_id: str
    mode: Literal['current', 'unannotated']
    image_ids: list[str]
    confidence_threshold: float
    max_detections: Literal[25, 50, 100, 200] = 100
    state: Literal['PREPARING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED']
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    pid: int | None = None
    error: str | None = None
    processed: int = 0
    total: int = 0
    prediction_count: int = 0
    images_with_predictions: int = 0
    images_without_predictions: int = 0
    average_confidence: float | None = None
    highest_confidence: float | None = None
    lowest_confidence: float | None = None


class PredictionStatusResponse(BaseModel):
    job: PredictionJob | None = None
    running: bool = False
