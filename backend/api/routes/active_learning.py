from fastapi import APIRouter, HTTPException

from schemas.active_learning import ActiveLearningRankRequest, ActiveLearningRanking, ActiveLearningReviewRequest, ActiveLearningReviewTarget, ActiveLearningSource, RankedImage
from services.active_learning_service import ActiveLearningError, ActiveLearningNotFoundError, create_ranking, get_ranking, list_sources, review_target

router = APIRouter(tags=['active-learning'])

def _error(error: Exception) -> HTTPException: return HTTPException(status_code=404 if isinstance(error,ActiveLearningNotFoundError) else 422,detail=str(error))

@router.get('/sources',response_model=list[ActiveLearningSource])
async def sources(): return list_sources()

@router.post('/rank',response_model=ActiveLearningRanking)
async def rank(request:ActiveLearningRankRequest):
    try:return create_ranking(request)
    except ActiveLearningError as error:raise _error(error) from error

@router.get('/rankings/{ranking_id}',response_model=ActiveLearningRanking)
async def ranking(ranking_id:str):
    try:return get_ranking(ranking_id)
    except ActiveLearningError as error:raise _error(error) from error

@router.get('/rankings/{ranking_id}/items',response_model=list[RankedImage])
async def ranking_items(ranking_id:str):
    try:return get_ranking(ranking_id).items
    except ActiveLearningError as error:raise _error(error) from error

@router.post('/rankings/{ranking_id}/review',response_model=ActiveLearningReviewTarget)
async def open_review(ranking_id:str,request:ActiveLearningReviewRequest):
    try:return review_target(ranking_id,request.image_id)
    except ActiveLearningError as error:raise _error(error) from error
