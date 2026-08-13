from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.predictions import PredictionRecord


class ReviewQueueItem(BaseModel):
    key: str
    image_id: str
    filename: str
    width: int
    height: int
    model_id: str
    prediction_run_id: str
    newest_prediction_at: datetime
    prediction_count: int
    pending_count: int
    accepted_count: int
    edited_count: int
    rejected_count: int
    permanent_annotations_added: int
    highest_confidence: float
    average_confidence: float
    lowest_confidence: float
    has_high_confidence: bool = False
    has_medium_confidence: bool = False
    has_low_confidence: bool = False
    status: Literal['PENDING', 'IN_REVIEW', 'REVIEWED']


class ReviewSummary(BaseModel):
    pending_images: int = 0
    reviewed_images: int = 0
    pending_predictions: int = 0
    accepted: int = 0
    edited: int = 0
    rejected: int = 0


class ReviewQueueResponse(BaseModel):
    project_id: str
    items: list[ReviewQueueItem] = Field(default_factory=list)
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    model_ids: list[str] = Field(default_factory=list)


class ReviewItemResponse(BaseModel):
    item: ReviewQueueItem
    predictions: list[PredictionRecord]


class ReviewBulkRequest(BaseModel):
    prediction_ids: list[str]
