import json
from collections import defaultdict

from schemas.predictions import PredictionRecord
from schemas.review import ReviewItemResponse, ReviewQueueItem, ReviewQueueResponse, ReviewSummary
from services.dataset_service import list_images
from services.prediction_service import PredictionNotFoundError, _prediction_files
from services.project_workspace import get_current_project_id


def _records() -> list[PredictionRecord]:
    records = []
    for path in _prediction_files():
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            records.extend(PredictionRecord.model_validate(item) for item in payload.get('predictions', []))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return records


def _queue_item(records: list[PredictionRecord], image) -> ReviewQueueItem:
    counts = {status: sum(record.status == status for record in records) for status in ('pending','accepted','edited','rejected')}
    image_status = 'PENDING' if counts['pending'] == len(records) else 'IN_REVIEW' if counts['pending'] else 'REVIEWED'
    confidences = [record.confidence for record in records]
    first = records[0]
    pending_confidences = [record.confidence for record in records if record.status == 'pending']
    return ReviewQueueItem(key=f'{first.image_id}:{first.model_id}:{first.run_id}', image_id=first.image_id, filename=image.filename, width=image.width, height=image.height, model_id=first.model_id, prediction_run_id=first.run_id, newest_prediction_at=max(record.created_at for record in records), prediction_count=len(records), pending_count=counts['pending'], accepted_count=counts['accepted'], edited_count=counts['edited'], rejected_count=counts['rejected'], permanent_annotations_added=counts['accepted'] + counts['edited'], highest_confidence=max(confidences), average_confidence=sum(confidences) / len(confidences), lowest_confidence=min(confidences), has_high_confidence=any(value >= .75 for value in pending_confidences), has_medium_confidence=any(.4 <= value < .75 for value in pending_confidences), has_low_confidence=any(value < .4 for value in pending_confidences), status=image_status)


def review_queue() -> ReviewQueueResponse:
    images = {image.id: image for image in list_images()}
    grouped = defaultdict(list)
    all_records = _records()
    for record in all_records:
        if record.image_id in images:
            grouped[(record.image_id, record.model_id, record.run_id)].append(record)
    items = [_queue_item(records, images[key[0]]) for key, records in grouped.items() if records]
    reviewed_keys = {item.image_id for item in items if item.status == 'REVIEWED'}
    pending_keys = {item.image_id for item in items if item.status != 'REVIEWED'}
    summary = ReviewSummary(pending_images=len(pending_keys), reviewed_images=len(reviewed_keys - pending_keys), pending_predictions=sum(record.status == 'pending' for record in all_records), accepted=sum(record.status == 'accepted' for record in all_records), edited=sum(record.status == 'edited' for record in all_records), rejected=sum(record.status == 'rejected' for record in all_records))
    return ReviewQueueResponse(project_id=get_current_project_id(), items=items, summary=summary, model_ids=sorted({item.model_id for item in items}, reverse=True))


def review_item(image_id: str, model_id: str, run_id: str) -> ReviewItemResponse:
    image = next((image for image in list_images() if image.id == image_id), None)
    if not image:
        raise PredictionNotFoundError('Review image not found')
    records = [record for record in _records() if record.image_id == image_id and record.model_id == model_id and record.run_id == run_id]
    if not records:
        raise PredictionNotFoundError('Review item not found')
    records.sort(key=lambda record: record.confidence, reverse=True)
    return ReviewItemResponse(item=_queue_item(records, image), predictions=records)
