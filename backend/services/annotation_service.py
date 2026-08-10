import json
import os
import threading
import uuid
from pathlib import Path

from schemas.annotations import AnnotationInput, AnnotationRecord
from services.class_service import ClassNotFoundError, list_classes
from services.dataset_service import get_image_file
from services.project_workspace import get_project_directories, touch_current_project

_write_lock = threading.Lock()
MIN_BOX_SIZE = 1.0


class AnnotationNotFoundError(LookupError):
    pass


class AnnotationValidationError(ValueError):
    pass


class AnnotationMetadataError(RuntimeError):
    pass


def _annotation_path(image_id: str) -> Path:
    annotations_dir = get_project_directories()[2]
    return annotations_dir / f"{image_id}.json"


def _require_image(image_id: str):
    result = get_image_file(image_id)
    if result is None:
        raise AnnotationValidationError("Image not found")
    return result[1]


def _load_records(image_id: str) -> list[AnnotationRecord]:
    _require_image(image_id)
    path = _annotation_path(image_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [AnnotationRecord.model_validate(item) for item in payload.get("annotations", [])]
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise AnnotationMetadataError("Annotation metadata is unreadable") from exc


def _save_records(image_id: str, records: list[AnnotationRecord]) -> None:
    path = _annotation_path(image_id)
    temporary_path = path.with_suffix(".tmp")
    payload = {"image_id": image_id, "annotations": [record.model_dump() for record in records]}
    try:
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary_path, path)
        touch_current_project()
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise AnnotationMetadataError("Annotations could not be saved") from exc


def _validate_input(image, data: AnnotationInput, class_ids: set[int]) -> None:
    if data.class_id not in class_ids:
        raise ClassNotFoundError(f"Class {data.class_id} was not found")
    if data.x2 - data.x1 < MIN_BOX_SIZE or data.y2 - data.y1 < MIN_BOX_SIZE:
        raise AnnotationValidationError("Bounding box is too small")
    if data.x2 > image.width or data.y2 > image.height:
        raise AnnotationValidationError("Bounding box exceeds the original image dimensions")


def list_annotations(image_id: str) -> list[AnnotationRecord]:
    return _load_records(image_id)


def replace_annotations(image_id: str, inputs: list[AnnotationInput]) -> list[AnnotationRecord]:
    with _write_lock:
        image = _require_image(image_id)
        existing_ids = {record.id for record in _load_records(image_id)}
        class_ids = {record.id for record in list_classes()}
        records: list[AnnotationRecord] = []
        used_ids: set[str] = set()
        for data in inputs:
            _validate_input(image, data, class_ids)
            annotation_id = data.id if data.id in existing_ids else uuid.uuid4().hex
            if annotation_id in used_ids:
                raise AnnotationValidationError("Duplicate annotation ID in request")
            used_ids.add(annotation_id)
            records.append(AnnotationRecord(id=annotation_id, image_id=image_id, **data.model_dump(exclude={"id"})))
        _save_records(image_id, records)
        return records


def update_annotation(image_id: str, annotation_id: str, data: AnnotationInput) -> AnnotationRecord:
    with _write_lock:
        image = _require_image(image_id)
        records = _load_records(image_id)
        index = next((index for index, item in enumerate(records) if item.id == annotation_id), None)
        if index is None:
            raise AnnotationNotFoundError("Annotation not found")
        _validate_input(image, data, {record.id for record in list_classes()})
        updated = AnnotationRecord(id=annotation_id, image_id=image_id, **data.model_dump(exclude={"id"}))
        records[index] = updated
        _save_records(image_id, records)
        return updated


def delete_annotation(image_id: str, annotation_id: str) -> None:
    with _write_lock:
        records = _load_records(image_id)
        record = next((item for item in records if item.id == annotation_id), None)
        if record is None:
            raise AnnotationNotFoundError("Annotation not found")
        records.remove(record)
        _save_records(image_id, records)
