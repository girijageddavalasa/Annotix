from fastapi import APIRouter, HTTPException

from schemas.predictions import PredictionRecord
from schemas.review import ReviewBulkRequest, ReviewItemResponse, ReviewQueueResponse
from services.prediction_service import PredictionError, accept_predictions, reject_predictions
from services.review_service import review_item, review_queue

router = APIRouter(tags=['review'])


def _error(error: Exception) -> HTTPException:
    return HTTPException(status_code=404 if 'not found' in str(error).lower() else 409, detail=str(error))


@router.get('/queue', response_model=ReviewQueueResponse)
async def queue() -> ReviewQueueResponse:
    return review_queue()


@router.get('/items/{image_id}/{model_id}/{run_id}', response_model=ReviewItemResponse)
async def item(image_id: str, model_id: str, run_id: str) -> ReviewItemResponse:
    try: return review_item(image_id, model_id, run_id)
    except PredictionError as error: raise _error(error) from error


@router.post('/accept-all', response_model=list[PredictionRecord])
async def accept_all(data: ReviewBulkRequest) -> list[PredictionRecord]:
    try: return accept_predictions(data.prediction_ids)
    except PredictionError as error: raise _error(error) from error


@router.post('/reject-all', response_model=list[PredictionRecord])
async def reject_all(data: ReviewBulkRequest) -> list[PredictionRecord]:
    try: return reject_predictions(data.prediction_ids)
    except PredictionError as error: raise _error(error) from error
