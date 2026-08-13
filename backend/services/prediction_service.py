import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psutil

from schemas.annotations import AnnotationInput
from schemas.predictions import ModelVersion, PredictionJob, PredictionListResponse, PredictionRecord, PredictionStartRequest, PredictionStatusResponse, PredictionUpdate
from schemas.training import TrainingJob
from services.annotation_service import list_annotations, replace_annotations
from services.class_service import list_classes
from services.dataset_service import get_image_file, list_images
from services.project_workspace import get_current_project_id, get_project_root

ACTIVE_STATES = {'PREPARING', 'RUNNING'}
_lock = threading.RLock()


class PredictionError(RuntimeError): pass
class PredictionConflictError(PredictionError): pass
class PredictionNotFoundError(PredictionError): pass
class ModelCompatibilityError(PredictionError): pass


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    os.replace(temporary, path)


def _job_dir(project_id: str) -> Path:
    path = get_project_root(project_id) / 'metadata' / 'prediction_jobs'; path.mkdir(parents=True, exist_ok=True); return path


def _read_job(path: Path) -> PredictionJob | None:
    try: return PredictionJob.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return None


def _jobs(project_id: str) -> list[PredictionJob]:
    jobs = [job for path in _job_dir(project_id).glob('*.json') if (job := _read_job(path))]
    return sorted(jobs, key=lambda job: job.created_at, reverse=True)


def _alive(pid: int | None) -> bool:
    if not pid: return False
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied): return False


def _refresh(job: PredictionJob) -> PredictionJob:
    if job.state in ACTIVE_STATES and not _alive(job.pid):
        updated = job.model_copy(update={'state': 'FAILED', 'finished_at': datetime.now(UTC), 'error': 'Prediction process stopped unexpectedly.'})
        _atomic_json(_job_dir(job.project_id) / f'{job.id}.json', updated.model_dump(mode='json'))
        return updated
    return job


def active_prediction_job(project_id: str | None = None) -> PredictionJob | None:
    project_id = project_id or get_current_project_id()
    return next((job for item in _jobs(project_id) if (job := _refresh(item)).state in ACTIVE_STATES), None)


def list_models() -> list[ModelVersion]:
    project_id = get_current_project_id(); root = get_project_root(project_id)
    completed = {}
    for path in (root / 'metadata' / 'training').glob('*.json'):
        try:
            job = TrainingJob.model_validate_json(path.read_text(encoding='utf-8'))
            if job.state == 'COMPLETED': completed[job.model_id] = job
        except (OSError, ValueError): continue
    models = []
    for model_id, job in completed.items():
        model_root = root / 'models' / model_id
        if (model_root / 'best.pt').is_file() and (model_root / 'class_mapping.json').is_file():
            models.append(ModelVersion(id=model_id, created_at=job.created_at, completed_at=job.finished_at or job.created_at, class_count=job.class_count, best_weights=f"models/{model_id}/best.pt"))
    return sorted(models, key=lambda model: model.completed_at, reverse=True)


def validate_model(model_id: str) -> tuple[Path, dict[int, int]]:
    model = next((item for item in list_models() if item.id == model_id), None)
    if not model: raise ModelCompatibilityError('The selected model is not a completed model in the current project')
    root = get_project_root(get_current_project_id()) / 'models' / model_id
    try: mapping_payload = json.loads((root / 'class_mapping.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error: raise ModelCompatibilityError('Model class mapping is missing or unreadable') from error
    trained_classes = {int(item['id']): item['name'] for item in mapping_payload.get('classes', [])}
    current_classes = {item.id: item.name for item in list_classes()}
    if trained_classes != current_classes:
        raise ModelCompatibilityError('Model classes no longer match this project. Restore the class definitions or train a new model.')
    yolo_to_stable = {int(yolo): int(stable) for stable, yolo in mapping_payload.get('stable_to_yolo', {}).items()}
    return root / 'best.pt', yolo_to_stable


def prediction_status() -> PredictionStatusResponse:
    jobs = _jobs(get_current_project_id())
    latest = _refresh(jobs[0]) if jobs else None
    return PredictionStatusResponse(job=latest, running=bool(latest and latest.state in ACTIVE_STATES))


def start_prediction(data: PredictionStartRequest) -> PredictionJob:
    with _lock:
        project_id = get_current_project_id()
        if active_prediction_job(project_id): raise PredictionConflictError('A prediction job is already running')
        from services.training_service import active_job
        if active_job(): raise PredictionConflictError('Prediction cannot start while model training is running')
        validate_model(data.model_id)
        images = list_images()
        if data.mode == 'current':
            images = [image for image in images if image.id == data.image_id]
            if not images: raise PredictionNotFoundError('Image not found in the current project')
        else: images = [image for image in images if image.annotation_count == 0]
        job_id = uuid.uuid4().hex
        job = PredictionJob(id=job_id, project_id=project_id, model_id=data.model_id, mode=data.mode, image_ids=[image.id for image in images], confidence_threshold=data.confidence_threshold, max_detections=data.max_detections, state='PREPARING', created_at=datetime.now(UTC), total=len(images))
        _atomic_json(_job_dir(project_id) / f'{job.id}.json', job.model_dump(mode='json'))
        worker = Path(__file__).resolve().parents[1] / 'prediction_worker.py'
        process = subprocess.Popen([sys.executable, str(worker), '--project-id', project_id, '--job-id', job.id], cwd=str(Path(__file__).resolve().parents[1]), creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        job = job.model_copy(update={'pid': process.pid})
        _atomic_json(_job_dir(project_id) / f'{job.id}.json', job.model_dump(mode='json'))
        return job


def get_prediction_job(job_id: str) -> PredictionJob:
    job = next((job for job in _jobs(get_current_project_id()) if job.id == job_id), None)
    if not job: raise PredictionNotFoundError('Prediction job not found')
    return _refresh(job)


def cancel_prediction(job_id: str) -> PredictionJob:
    job = get_prediction_job(job_id)
    if job.state not in ACTIVE_STATES: raise PredictionConflictError('Prediction job is not running')
    (_job_dir(job.project_id) / f'{job.id}.cancel').touch()
    return job


def prediction_event_path(job: PredictionJob) -> Path:
    return get_project_root(job.project_id) / 'logs' / f'prediction-{job.id}.jsonl'


def _prediction_files(model_id: str | None = None):
    root = get_project_root(get_current_project_id()) / 'predictions'
    pattern = f'{model_id}/*/*.json' if model_id else '*/*/*.json'
    return root.glob(pattern)


def list_image_predictions(image_id: str, model_id: str | None = None) -> PredictionListResponse:
    records = []
    for path in _prediction_files(model_id):
        if path.stem != image_id: continue
        try: records.extend(PredictionRecord.model_validate(item) for item in json.loads(path.read_text(encoding='utf-8')).get('predictions', []))
        except (OSError, json.JSONDecodeError, ValueError): continue
    return PredictionListResponse(image_id=image_id, predictions=sorted(records, key=lambda item: item.confidence, reverse=True))


def _find_prediction(prediction_id: str) -> tuple[Path, dict, int, PredictionRecord]:
    for path in _prediction_files():
        try: payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError): continue
        for index, item in enumerate(payload.get('predictions', [])):
            if item.get('id') == prediction_id: return path, payload, index, PredictionRecord.model_validate(item)
    raise PredictionNotFoundError('Prediction not found')


def update_prediction(prediction_id: str, data: PredictionUpdate) -> PredictionRecord:
    path, payload, index, record = _find_prediction(prediction_id)
    if record.status != 'pending': raise PredictionConflictError('Reviewed predictions cannot be edited')
    changes = data.model_dump(exclude_none=True)
    values = record.model_dump(); values.update(changes); updated = PredictionRecord.model_validate(values)
    image_result = get_image_file(updated.image_id)
    if not image_result: raise PredictionNotFoundError('Prediction image not found')
    image = image_result[1]
    if updated.x2 <= updated.x1 or updated.y2 <= updated.y1 or updated.x2 > image.width or updated.y2 > image.height: raise PredictionError('Prediction box is outside the original image')
    if updated.class_id not in {item.id for item in list_classes()}: raise ModelCompatibilityError('Prediction class does not exist')
    changed = updated.class_id != record.class_id or [updated.x1,updated.y1,updated.x2,updated.y2] != [record.x1,record.y1,record.x2,record.y2]
    history = list(record.edit_history)
    if changed:
        history.append({'edited_at': datetime.now(UTC).isoformat(), 'reviewed_by': 'local-user', 'before': {'class_id': record.class_id, 'box': [record.x1,record.y1,record.x2,record.y2]}, 'after': {'class_id': updated.class_id, 'box': [updated.x1,updated.y1,updated.x2,updated.y2]}})
    updated = updated.model_copy(update={'corrected': updated.class_id != record.original_class_id or [updated.x1,updated.y1,updated.x2,updated.y2] != record.original_box, 'edit_history': history})
    payload['predictions'][index] = updated.model_dump(mode='json'); _atomic_json(path, payload); return updated


def reject_prediction(prediction_id: str) -> PredictionRecord:
    path, payload, index, record = _find_prediction(prediction_id)
    if record.status == 'rejected': return record
    if record.status != 'pending': raise PredictionConflictError('Prediction has already been reviewed')
    updated = record.model_copy(update={'status':'rejected','reviewed_at':datetime.now(UTC),'reviewed_by':'local-user'})
    payload['predictions'][index] = updated.model_dump(mode='json'); _atomic_json(path,payload); return updated


def accept_predictions(prediction_ids: list[str]) -> list[PredictionRecord]:
    if not prediction_ids: return []
    found = [_find_prediction(item) for item in dict.fromkeys(prediction_ids)]
    records = [item[3] for item in found]
    already_accepted = [record for record in records if record.status in {'accepted','edited'}]
    records = [record for record in records if record.status == 'pending']
    if not records: return already_accepted
    if any(record.status != 'pending' for record in records): raise PredictionConflictError('One or more predictions have already been reviewed')
    if len({record.image_id for record in records}) != 1: raise PredictionError('Predictions must belong to one image')
    image_id = records[0].image_id
    existing = [AnnotationInput(id=item.id,class_id=item.class_id,x1=item.x1,y1=item.y1,x2=item.x2,y2=item.y2) for item in list_annotations(image_id)]
    additions = [AnnotationInput(class_id=item.class_id,x1=item.x1,y1=item.y1,x2=item.x2,y2=item.y2) for item in records]
    saved = replace_annotations(image_id, existing + additions)
    new_records = saved[len(existing):]
    updated_records = []
    for record, annotation in zip(records,new_records):
        path, payload, index, _ = _find_prediction(record.id)
        updated = record.model_copy(update={'status':'edited' if record.corrected else 'accepted','reviewed_at':datetime.now(UTC),'reviewed_by':'local-user','annotation_id':annotation.id})
        payload['predictions'][index] = updated.model_dump(mode='json'); _atomic_json(path,payload); updated_records.append(updated)
    return already_accepted + updated_records


def reject_predictions(prediction_ids: list[str]) -> list[PredictionRecord]:
    return [reject_prediction(prediction_id) for prediction_id in dict.fromkeys(prediction_ids)]
