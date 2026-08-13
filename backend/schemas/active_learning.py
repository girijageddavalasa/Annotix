from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ActiveLearningRankRequest(BaseModel):
    model_id: str
    prediction_run_id: str
    top_k: Literal[5, 10, 25, 50] = 10
    strategy: Literal['confidence_uncertainty'] = 'confidence_uncertainty'
    strategy_version: Literal['v1'] = 'v1'


class ActiveLearningSource(BaseModel):
    model_id: str
    prediction_run_id: str
    created_at: datetime
    predicted_images: int
    no_prediction_images: int


class RankedImage(BaseModel):
    rank: int
    image_id: str
    filename: str
    model_id: str
    prediction_run_id: str
    review_key: str
    uncertainty_score: float
    highest_uncertainty: float
    prediction_count: int
    lowest_confidence: float
    average_confidence: float
    review_status: Literal['PENDING', 'IN_REVIEW']
    explanation: str = 'Ranked highly because the model produced low-confidence predictions.'


class NoPredictionImage(BaseModel):
    image_id: str
    filename: str
    status: Literal['NO_PREDICTIONS'] = 'NO_PREDICTIONS'


class ActiveLearningRanking(BaseModel):
    ranking_id: str
    project_id: str
    model_id: str
    prediction_run_id: str
    created_at: datetime
    strategy: Literal['confidence_uncertainty']
    strategy_version: Literal['v1']
    configuration: dict
    images_available: int
    candidate_count: int
    ranked_count: int
    predicted_images: int
    no_prediction_images: int
    items: list[RankedImage] = Field(default_factory=list)
    no_prediction_items: list[NoPredictionImage] = Field(default_factory=list)


class ActiveLearningReviewRequest(BaseModel):
    image_id: str


class ActiveLearningReviewTarget(BaseModel):
    ranking_id: str
    image_id: str
    model_id: str
    prediction_run_id: str
    review_key: str
