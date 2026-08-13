import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from schemas.active_learning import ActiveLearningRankRequest, ActiveLearningRanking, ActiveLearningReviewTarget, ActiveLearningSource, NoPredictionImage, RankedImage
from schemas.predictions import PredictionJob, PredictionRecord
from services.dataset_service import list_images
from services.project_workspace import get_current_project_id, get_project_root


class ActiveLearningError(RuntimeError): pass
class ActiveLearningNotFoundError(ActiveLearningError): pass


def _ranking_dir() -> Path:
    path = get_project_root(get_current_project_id()) / 'metadata' / 'active_learning'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    os.replace(temporary, path)


def _job(run_id: str) -> PredictionJob:
    path = get_project_root(get_current_project_id()) / 'metadata' / 'prediction_jobs' / f'{run_id}.json'
    try: job = PredictionJob.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error: raise ActiveLearningNotFoundError('Prediction run not found in the current project') from error
    if job.state != 'COMPLETED': raise ActiveLearningError('Only completed prediction runs can be ranked')
    return job


def _run_files(model_id: str, run_id: str) -> list[Path]:
    root = get_project_root(get_current_project_id()) / 'predictions' / model_id / run_id
    return sorted(root.glob('*.json')) if root.is_dir() else []


def list_sources() -> list[ActiveLearningSource]:
    root = get_project_root(get_current_project_id())
    sources = []
    for path in (root / 'metadata' / 'prediction_jobs').glob('*.json'):
        try: job = PredictionJob.model_validate_json(path.read_text(encoding='utf-8'))
        except (OSError, ValueError): continue
        if job.state != 'COMPLETED': continue
        files = _run_files(job.model_id, job.id)
        predicted = no_predictions = 0
        for file in files:
            try: count = len(json.loads(file.read_text(encoding='utf-8')).get('predictions', []))
            except (OSError, json.JSONDecodeError): continue
            predicted += count > 0; no_predictions += count == 0
        if files: sources.append(ActiveLearningSource(model_id=job.model_id, prediction_run_id=job.id, created_at=job.created_at, predicted_images=predicted, no_prediction_images=no_predictions))
    return sorted(sources, key=lambda source: source.created_at, reverse=True)


def create_ranking(request: ActiveLearningRankRequest) -> ActiveLearningRanking:
    project_id = get_current_project_id()
    job = _job(request.prediction_run_id)
    if job.model_id != request.model_id: raise ActiveLearningError('Prediction run does not belong to the selected model')
    fingerprint = json.dumps({'project_id':project_id, **request.model_dump(mode='json')}, sort_keys=True)
    ranking_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    path = _ranking_dir() / f'{ranking_id}.json'
    if path.exists(): return ActiveLearningRanking.model_validate_json(path.read_text(encoding='utf-8'))
    images = {image.id:image for image in list_images()}
    candidates = []; no_prediction_items = []
    for file in _run_files(request.model_id, request.prediction_run_id):
        image = images.get(file.stem)
        if not image: continue
        try: records = [PredictionRecord.model_validate(item) for item in json.loads(file.read_text(encoding='utf-8')).get('predictions', [])]
        except (OSError, json.JSONDecodeError, ValueError): continue
        if not records:
            no_prediction_items.append(NoPredictionImage(image_id=image.id, filename=image.filename)); continue
        pending = [record for record in records if record.status == 'pending']
        if not pending: continue
        confidences = [record.confidence for record in pending]
        status = 'PENDING' if len(pending) == len(records) else 'IN_REVIEW'
        candidates.append({'image':image, 'confidence':confidences, 'status':status})
    candidates.sort(key=lambda item: (-(1 - sum(item['confidence']) / len(item['confidence'])), min(item['confidence']), item['image'].id))
    ranked = []
    for rank, item in enumerate(candidates[:request.top_k], 1):
        confidences=item['confidence']; image=item['image']
        ranked.append(RankedImage(rank=rank,image_id=image.id,filename=image.filename,model_id=request.model_id,prediction_run_id=request.prediction_run_id,review_key=f'{image.id}:{request.model_id}:{request.prediction_run_id}',uncertainty_score=1-sum(confidences)/len(confidences),highest_uncertainty=1-min(confidences),prediction_count=len(confidences),lowest_confidence=min(confidences),average_confidence=sum(confidences)/len(confidences),review_status=item['status']))
    ranking = ActiveLearningRanking(ranking_id=ranking_id,project_id=project_id,model_id=request.model_id,prediction_run_id=request.prediction_run_id,created_at=datetime.now(UTC),strategy=request.strategy,strategy_version=request.strategy_version,configuration={'top_k':request.top_k,'aggregation':'mean(1 - confidence)','tie_breakers':['lowest_confidence','image_id']},images_available=len(candidates)+len(no_prediction_items),candidate_count=len(candidates),ranked_count=len(ranked),predicted_images=len(candidates),no_prediction_images=len(no_prediction_items),items=ranked,no_prediction_items=sorted(no_prediction_items,key=lambda item:item.image_id))
    _atomic_json(path, ranking.model_dump(mode='json')); return ranking


def get_ranking(ranking_id: str) -> ActiveLearningRanking:
    path = _ranking_dir() / f'{ranking_id}.json'
    try: return ActiveLearningRanking.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error: raise ActiveLearningNotFoundError('Active-learning ranking not found') from error


def review_target(ranking_id: str, image_id: str) -> ActiveLearningReviewTarget:
    ranking = get_ranking(ranking_id)
    item = next((item for item in ranking.items if item.image_id == image_id), None)
    if not item: raise ActiveLearningNotFoundError('Ranked image not found')
    return ActiveLearningReviewTarget(ranking_id=ranking_id,image_id=image_id,model_id=ranking.model_id,prediction_run_id=ranking.prediction_run_id,review_key=item.review_key)
