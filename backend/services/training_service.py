import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psutil

from schemas.training import TrainingJob, TrainingStartRequest, TrainingStatusResponse
from services.project_workspace import PROJECTS_DIR, get_current_project_id, get_project_root

ACTIVE_STATES = {'PREPARING', 'TRAINING'}
_training_lock = threading.RLock()


class TrainingConflictError(RuntimeError):
    pass


class TrainingValidationError(ValueError):
    pass


class TrainingJobNotFoundError(LookupError):
    pass


def _training_dir(project_id: str) -> Path:
    path = get_project_root(project_id) / 'metadata' / 'training'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_path(project_id: str, job_id: str) -> Path:
    return _training_dir(project_id) / f'{job_id}.json'


def _read_job(path: Path) -> TrainingJob | None:
    try:
        return TrainingJob.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _is_process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def _jobs() -> list[TrainingJob]:
    jobs = []
    if not PROJECTS_DIR.exists():
        return jobs
    for path in PROJECTS_DIR.glob('*/metadata/training/*.json'):
        job = _read_job(path)
        if job:
            jobs.append(job)
    return sorted(jobs, key=lambda item: item.created_at, reverse=True)


def _refresh_stale(job: TrainingJob) -> TrainingJob:
    if job.state in ACTIVE_STATES and not _is_process_alive(job.pid):
        updated = job.model_copy(update={'state': 'FAILED', 'finished_at': datetime.now(UTC), 'error': 'Training process stopped unexpectedly.'})
        _write_job(updated)
        return updated
    return job


def _write_job(job: TrainingJob) -> None:
    path = _job_path(job.project_id, job.id)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(job.model_dump_json(indent=2), encoding='utf-8')
    os.replace(temporary, path)


def active_job(project_id: str | None = None) -> TrainingJob | None:
    for job in _jobs():
        job = _refresh_stale(job)
        if job.state in ACTIVE_STATES and (project_id is None or job.project_id == project_id):
            return job
    return None


def project_training_locked(project_id: str | None = None) -> bool:
    return active_job(project_id or get_current_project_id()) is not None


def require_project_editable() -> None:
    if project_training_locked():
        raise TrainingConflictError('Dataset and annotations are locked while this project is training')


def get_training_status() -> TrainingStatusResponse:
    project_id = get_current_project_id()
    project_jobs = [job for job in _jobs() if job.project_id == project_id]
    latest = _refresh_stale(project_jobs[0]) if project_jobs else None
    return TrainingStatusResponse(job=latest, any_training_active=active_job() is not None, current_project_locked=bool(latest and latest.state in ACTIVE_STATES))


def start_training(configuration: TrainingStartRequest, annotated_images: int, class_count: int) -> TrainingJob:
    with _training_lock:
        if active_job():
            raise TrainingConflictError('A training job is already running')
        from services.prediction_service import active_prediction_job
        if active_prediction_job():
            raise TrainingConflictError('Training cannot start while prediction is running')
        if annotated_images < 1:
            raise TrainingValidationError('At least one annotated image is required')
        if class_count < 1:
            raise TrainingValidationError('At least one class is required')
        project_id = get_current_project_id()
        job_id = uuid.uuid4().hex
        model_id = f'model-{datetime.now(UTC).strftime("%Y%m%d-%H%M%S")}-{job_id[:8]}'
        job = TrainingJob(id=job_id, project_id=project_id, model_id=model_id, state='PREPARING', created_at=datetime.now(UTC), configuration=configuration, annotated_images=annotated_images, class_count=class_count)
        _write_job(job)
        log_path = get_project_root(project_id) / 'logs' / f'training-{job_id}.jsonl'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        worker = Path(__file__).resolve().parents[1] / 'training_worker.py'
        process = subprocess.Popen([sys.executable, str(worker), '--project-id', project_id, '--job-id', job_id], cwd=str(Path(__file__).resolve().parents[1]), creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        job = job.model_copy(update={'pid': process.pid})
        _write_job(job)
        return job


def cancel_training(job_id: str) -> TrainingJob:
    with _training_lock:
        job = next((item for item in _jobs() if item.id == job_id), None)
        if not job:
            raise TrainingJobNotFoundError('Training job not found')
        if job.state not in ACTIVE_STATES:
            raise TrainingConflictError('Training job is not running')
        (get_project_root(job.project_id) / 'metadata' / 'training' / f'{job.id}.cancel').touch()
        return job


def get_job(job_id: str) -> TrainingJob:
    job = next((item for item in _jobs() if item.id == job_id), None)
    if not job:
        raise TrainingJobNotFoundError('Training job not found')
    return _refresh_stale(job)


def event_path(job: TrainingJob) -> Path:
    return get_project_root(job.project_id) / 'logs' / f'training-{job.id}.jsonl'
