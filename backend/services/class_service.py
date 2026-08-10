import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path

from schemas.classes import ClassCreate, ClassRecord, ClassUpdate
from services.project_workspace import get_project_directories, touch_current_project

CLASSES_FILENAME = "classes.json"
_write_lock = threading.Lock()


class ClassNotFoundError(LookupError):
    pass


class DuplicateClassNameError(ValueError):
    pass


class ClassInUseError(ValueError):
    def __init__(self, usage_count: int):
        self.usage_count = usage_count
        super().__init__(f"Class is used by {usage_count} annotations and cannot be deleted")


class ClassMetadataError(RuntimeError):
    pass


def _classes_path() -> Path:
    return get_project_directories()[3] / CLASSES_FILENAME


def _empty_payload() -> dict:
    return {"next_id": 0, "classes": []}


def _load_payload() -> dict:
    path = _classes_path()
    if not path.exists():
        return _empty_payload()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        next_id = int(payload["next_id"])
        records = [ClassRecord.model_validate(item) for item in payload.get("classes", [])]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as exc:
        raise ClassMetadataError("Class metadata is unreadable; no changes were made") from exc

    highest_id = max((record.id for record in records), default=-1)
    if next_id <= highest_id:
        raise ClassMetadataError("Class metadata contains an invalid ID counter")
    return {"next_id": next_id, "classes": records}


def _save_payload(next_id: int, records: list[ClassRecord]) -> None:
    path = _classes_path()
    temporary_path = path.with_suffix(".tmp")
    payload = {
        "next_id": next_id,
        "classes": [record.model_dump(mode="json") for record in records],
    }
    try:
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary_path, path)
        touch_current_project()
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        raise ClassMetadataError("Class metadata could not be saved") from exc


def _find_class(records: list[ClassRecord], class_id: int) -> ClassRecord:
    record = next((item for item in records if item.id == class_id), None)
    if record is None:
        raise ClassNotFoundError(f"Class {class_id} was not found")
    return record


def _actual_usage_counts() -> dict[int, int]:
    annotations_dir = get_project_directories()[2]
    counts: dict[int, int] = {}
    for path in annotations_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for annotation in payload.get("annotations", []):
                class_id = int(annotation["class_id"])
                counts[class_id] = counts.get(class_id, 0) + 1
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
            continue
    return counts


def _with_actual_usage(records: list[ClassRecord]) -> list[ClassRecord]:
    counts = _actual_usage_counts()
    return [record.model_copy(update={"usage_count": counts.get(record.id, 0)}) for record in records]


def _ensure_unique_name(records: list[ClassRecord], name: str, excluded_id: int | None = None) -> None:
    normalized = name.casefold()
    if any(record.id != excluded_id and record.name.casefold() == normalized for record in records):
        raise DuplicateClassNameError(f'A class named "{name}" already exists')


def list_classes() -> list[ClassRecord]:
    return _with_actual_usage(_load_payload()["classes"])


def get_class_count() -> int:
    return len(list_classes())


def create_class(data: ClassCreate) -> ClassRecord:
    with _write_lock:
        payload = _load_payload()
        records = payload["classes"]
        _ensure_unique_name(records, data.name)
        record = ClassRecord(
            id=payload["next_id"],
            name=data.name,
            color=data.color.upper(),
            created_at=datetime.now(UTC),
            usage_count=0,
        )
        records.append(record)
        _save_payload(record.id + 1, records)
        return record


def update_class(class_id: int, data: ClassUpdate) -> ClassRecord:
    if data.name is None and data.color is None:
        raise ValueError("Provide a name or color to update")
    with _write_lock:
        payload = _load_payload()
        records = payload["classes"]
        record = _find_class(records, class_id)
        if data.name is not None:
            _ensure_unique_name(records, data.name, excluded_id=class_id)
            record.name = data.name
        if data.color is not None:
            record.color = data.color.upper()
        _save_payload(payload["next_id"], records)
        return record


def delete_class(class_id: int) -> None:
    with _write_lock:
        payload = _load_payload()
        records = payload["classes"]
        stored_record = _find_class(records, class_id)
        actual_record = _find_class(_with_actual_usage(records), class_id)
        if actual_record.usage_count > 0:
            raise ClassInUseError(actual_record.usage_count)
        records.remove(stored_record)
        _save_payload(payload["next_id"], records)


def adjust_usage_count(class_id: int, amount: int) -> ClassRecord:
    """Reserved for the annotation service to call in the next implementation step."""
    with _write_lock:
        payload = _load_payload()
        records = payload["classes"]
        record = _find_class(records, class_id)
        new_count = record.usage_count + amount
        if new_count < 0:
            raise ValueError("Class usage count cannot be negative")
        record.usage_count = new_count
        _save_payload(payload["next_id"], records)
        return record
