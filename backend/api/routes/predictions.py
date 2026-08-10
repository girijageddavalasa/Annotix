import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from schemas.predictions import ModelVersion, PredictionAcceptRequest, PredictionJob, PredictionListResponse, PredictionRecord, PredictionStartRequest, PredictionStatusResponse, PredictionUpdate
from services.prediction_service import ModelCompatibilityError, PredictionConflictError, PredictionError, PredictionNotFoundError, accept_predictions, cancel_prediction, get_prediction_job, list_image_predictions, list_models, prediction_event_path, prediction_status, reject_prediction, start_prediction, update_prediction

router = APIRouter(tags=['predictions'])


def service_error(error: Exception) -> HTTPException:
    if isinstance(error, PredictionNotFoundError): return HTTPException(status_code=404,detail=str(error))
    if isinstance(error, (PredictionConflictError, ModelCompatibilityError)): return HTTPException(status_code=409,detail=str(error))
    return HTTPException(status_code=422,detail=str(error))


@router.get('/models',response_model=list[ModelVersion])
async def models(): return list_models()


@router.get('/status',response_model=PredictionStatusResponse)
async def status_response(): return prediction_status()


@router.post('/jobs',response_model=PredictionJob,status_code=status.HTTP_202_ACCEPTED)
async def create_job(data:PredictionStartRequest):
    try: return start_prediction(data)
    except PredictionError as error: raise service_error(error) from error


@router.get('/jobs/{job_id}',response_model=PredictionJob)
async def job(job_id:str):
    try: return get_prediction_job(job_id)
    except PredictionError as error: raise service_error(error) from error


@router.post('/jobs/{job_id}/cancel',response_model=PredictionJob)
async def cancel(job_id:str):
    try: return cancel_prediction(job_id)
    except PredictionError as error: raise service_error(error) from error


@router.get('/jobs/{job_id}/events')
async def events(job_id:str,request:Request):
    try: prediction_job=get_prediction_job(job_id)
    except PredictionError as error: raise service_error(error) from error
    path=prediction_event_path(prediction_job)
    async def stream():
        offset=0; heartbeat=0
        while not await request.is_disconnected():
            if path.exists():
                with path.open('r',encoding='utf-8') as source:
                    source.seek(offset)
                    for line in source:
                        try: payload=json.loads(line)
                        except json.JSONDecodeError: continue
                        yield f"event: {payload.get('type','log')}\ndata: {json.dumps(payload)}\n\n"
                    offset=source.tell()
            current=get_prediction_job(job_id)
            if current.state not in {'PREPARING','RUNNING'}:
                yield f"event: status\ndata: {json.dumps({'job':current.model_dump(mode='json')})}\n\n"; break
            heartbeat+=1
            if heartbeat>=20: yield ': keep-alive\n\n'; heartbeat=0
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


@router.get('/images/{image_id}',response_model=PredictionListResponse)
async def image_predictions(image_id:str,model_id:str|None=Query(default=None)): return list_image_predictions(image_id,model_id)


@router.patch('/items/{prediction_id}',response_model=PredictionRecord)
async def edit_prediction(prediction_id:str,data:PredictionUpdate):
    try: return update_prediction(prediction_id,data)
    except PredictionError as error: raise service_error(error) from error


@router.post('/items/{prediction_id}/accept',response_model=list[PredictionRecord])
async def accept_prediction(prediction_id:str):
    try: return accept_predictions([prediction_id])
    except PredictionError as error: raise service_error(error) from error


@router.post('/items/{prediction_id}/reject',response_model=PredictionRecord)
async def reject(prediction_id:str):
    try: return reject_prediction(prediction_id)
    except PredictionError as error: raise service_error(error) from error


@router.post('/accept-all',response_model=list[PredictionRecord])
async def accept_all(data:PredictionAcceptRequest):
    try: return accept_predictions(data.prediction_ids)
    except PredictionError as error: raise service_error(error) from error
