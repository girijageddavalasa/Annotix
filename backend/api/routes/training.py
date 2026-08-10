import asyncio
import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from schemas.training import TrainingJob, TrainingStartRequest, TrainingStatusResponse
from services.dataset_service import get_dataset_state
from services.training_service import TrainingConflictError, TrainingJobNotFoundError, TrainingValidationError, cancel_training, event_path, get_job, get_training_status, start_training

router = APIRouter(tags=['training'])


def _error(error: Exception) -> HTTPException:
    if isinstance(error, TrainingJobNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, TrainingConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))


@router.get('/status', response_model=TrainingStatusResponse)
async def training_status() -> TrainingStatusResponse:
    return get_training_status()


@router.post('/jobs', response_model=TrainingJob, status_code=status.HTTP_202_ACCEPTED)
async def create_training_job(data: TrainingStartRequest) -> TrainingJob:
    try:
        stats = get_dataset_state().stats
        return start_training(data, stats.annotated_images, stats.classes)
    except (TrainingConflictError, TrainingValidationError) as error:
        raise _error(error) from error


@router.post('/jobs/{job_id}/cancel', response_model=TrainingJob)
async def stop_training(job_id: str) -> TrainingJob:
    try:
        return cancel_training(job_id)
    except (TrainingConflictError, TrainingJobNotFoundError) as error:
        raise _error(error) from error


@router.get('/jobs/{job_id}', response_model=TrainingJob)
async def training_job(job_id: str) -> TrainingJob:
    try:
        return get_job(job_id)
    except TrainingJobNotFoundError as error:
        raise _error(error) from error


@router.get('/jobs/{job_id}/events')
async def training_events(job_id: str, request: Request) -> StreamingResponse:
    try:
        job = get_job(job_id)
    except TrainingJobNotFoundError as error:
        raise _error(error) from error
    path = event_path(job)

    async def stream():
        offset = 0
        last_heartbeat = 0
        while not await request.is_disconnected():
            if path.exists():
                with path.open('r', encoding='utf-8') as events:
                    events.seek(offset)
                    for line in events:
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        yield f"event: {payload.get('type', 'log')}\ndata: {json.dumps(payload)}\n\n"
                    offset = events.tell()
            current = get_job(job_id)
            if current.state not in {'PREPARING', 'TRAINING'}:
                yield f"event: status\ndata: {json.dumps({'type': 'status', 'job': current.model_dump(mode='json')})}\n\n"
                break
            last_heartbeat += 1
            if last_heartbeat >= 20:
                yield ': keep-alive\n\n'
                last_heartbeat = 0
            await asyncio.sleep(.5)

    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

