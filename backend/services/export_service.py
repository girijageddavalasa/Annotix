import json
import shutil
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

from schemas.exports import ExportIssue, ExportPreview, ExportRecord, ExportStats
from services.project_workspace import get_current_project_id, get_project_root


class ExportValidationError(ValueError):
    def __init__(self, issues: list[ExportIssue]):
        super().__init__("Export validation failed")
        self.issues = issues


def yolo_box(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[float, float, float, float]:
    return ((x1 + x2) / (2 * width), (y1 + y2) / (2 * height), (x2 - x1) / width, (y2 - y1) / height)


def class_mapping(classes: list[dict]) -> tuple[dict[int, int], list[str]]:
    ordered = sorted(classes, key=lambda item: int(item["id"]))
    return ({int(item["id"]): index for index, item in enumerate(ordered)}, [str(item["name"]) for item in ordered])


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_valid_training_snapshot(root: Path, image_ids: set[str]) -> tuple[Path, dict] | None:
    candidates = []
    for path in (root / "metadata" / "training_history").glob("*.json"):
        try:
            job = _read_json(path)
            state = job.get("state") or job.get("training_status")
            snapshot_reference = job.get("snapshot_path") or job.get("dataset_snapshot")
            if state != "COMPLETED" or not snapshot_reference:
                continue
            snapshot_path = root / str(snapshot_reference)
            snapshot = _read_json(snapshot_path)
            snapshot_ids = {str(item["id"]) for item in snapshot.get("images", [])}
            if snapshot_ids and snapshot_ids <= image_ids:
                candidates.append((str(job.get("finished_at") or job.get("created_at") or ""), snapshot_path, snapshot))
        except (OSError, ValueError, TypeError, KeyError):
            continue
    if not candidates:
        return None
    _, path, snapshot = max(candidates, key=lambda item: item[0])
    return path, snapshot


def _collect(root: Path) -> tuple[ExportPreview, list[dict], dict[str, list[dict]], dict[int, int], list[str]]:
    dataset = _read_json(root / "metadata" / "dataset.json") if (root / "metadata" / "dataset.json").exists() else {"images": []}
    classes_payload = _read_json(root / "metadata" / "classes.json") if (root / "metadata" / "classes.json").exists() else {"classes": []}
    images_by_id = {str(item["id"]): item for item in dataset.get("images", [])}
    mapping, names = class_mapping(classes_payload.get("classes", []))
    annotations: dict[str, list[dict]] = {}
    issues: list[ExportIssue] = []
    for path in sorted((root / "annotations").glob("*.json")):
        try:
            payload = _read_json(path)
            image_id = str(payload.get("image_id") or path.stem)
            if image_id not in images_by_id:
                issues.append(ExportIssue(image_id=image_id, message="Annotation file references an image that does not exist"))
                continue
            records = payload.get("annotations", [])
            for item in records:
                annotation_id = str(item.get("id", "")) or None
                class_id = item.get("class_id")
                if class_id not in mapping:
                    issues.append(ExportIssue(image_id=image_id, annotation_id=annotation_id, message=f"Class {class_id} does not exist"))
                    continue
                image = images_by_id[image_id]
                try:
                    x1, y1, x2, y2 = (float(item[key]) for key in ("x1", "y1", "x2", "y2"))
                    width, height = int(image["width"]), int(image["height"])
                except (KeyError, TypeError, ValueError):
                    issues.append(ExportIssue(image_id=image_id, annotation_id=annotation_id, message="Bounding box metadata is invalid"))
                    continue
                if width <= 0 or height <= 0 or x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1 or x2 > width or y2 > height:
                    issues.append(ExportIssue(image_id=image_id, annotation_id=annotation_id, message="Bounding box is invalid or outside the original image dimensions"))
            annotations[image_id] = records
        except (OSError, ValueError, TypeError):
            issues.append(ExportIssue(image_id=path.stem, message="Annotation file is unreadable"))

    annotated_ids = {image_id for image_id, records in annotations.items() if records}
    training = _latest_valid_training_snapshot(root, set(images_by_id))
    if training:
        snapshot_path, snapshot = training
        members = [item for item in snapshot["images"] if str(item["id"]) in annotated_ids]
        source = "latest-training-snapshot"
        source_snapshot = snapshot_path.relative_to(root).as_posix()
    else:
        ordered_ids = sorted(annotated_ids)
        validation_count = 0 if len(ordered_ids) < 2 else min(max(1, round(len(ordered_ids) * .2)), len(ordered_ids) - 1)
        validation_ids = set(ordered_ids[-validation_count:]) if validation_count else set()
        members = [{"id": image_id, "split": "validation" if image_id in validation_ids else "train"} for image_id in ordered_ids]
        source, source_snapshot = "deterministic-current-annotations", None
    selected = []
    for member in members:
        image = images_by_id[str(member["id"])]
        selected.append({**image, "split": "validation" if member.get("split") in {"validation", "val"} else "train"})
    stats = ExportStats(images=len(selected), annotated_images=len(selected), objects=sum(len(annotations[item["id"]]) for item in selected), classes=len(names), train_images=sum(item["split"] == "train" for item in selected), validation_images=sum(item["split"] == "validation" for item in selected))
    return ExportPreview(source=source, source_snapshot=source_snapshot, stats=stats, issues=issues), selected, annotations, mapping, names


def preview_export() -> ExportPreview:
    return _collect(get_project_root(get_current_project_id()))[0]


def create_export() -> ExportRecord:
    project_id = get_current_project_id()
    root = get_project_root(project_id)
    preview, images, annotations, mapping, names = _collect(root)
    if preview.issues:
        raise ExportValidationError(preview.issues)
    if not images:
        raise ExportValidationError([ExportIssue(message="There are no annotated images to export")])
    export_id = uuid.uuid4().hex
    workspace = root / "generated" / "exports" / export_id
    for split in ("train", "val"):
        (workspace / "images" / split).mkdir(parents=True)
        (workspace / "labels" / split).mkdir(parents=True)
    manifest_images = []
    for image in images:
        split = "val" if image["split"] == "validation" else "train"
        source = (root / "images" / image["relative_path"]).resolve()
        if root.resolve() not in source.parents or not source.is_file():
            shutil.rmtree(workspace, ignore_errors=True)
            raise ExportValidationError([ExportIssue(image_id=image["id"], message="Original image file is missing")])
        filename = f'{image["id"]}{source.suffix.lower()}'
        shutil.copy2(source, workspace / "images" / split / filename)
        lines = []
        for item in annotations[image["id"]]:
            cx, cy, width, height = yolo_box(float(item["x1"]), float(item["y1"]), float(item["x2"]), float(item["y2"]), int(image["width"]), int(image["height"]))
            lines.append(f'{mapping[int(item["class_id"])]} {cx:.8f} {cy:.8f} {width:.8f} {height:.8f}')
        (workspace / "labels" / split / f'{image["id"]}.txt').write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        manifest_images.append({"id": image["id"], "filename": image["filename"], "split": split})
    (workspace / "data.yaml").write_text(yaml.safe_dump({"path": ".", "train": "images/train", "val": "images/val", "names": {index: name for index, name in enumerate(names)}}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    created_at = datetime.now(UTC)
    record = ExportRecord(id=export_id, project_id=project_id, created_at=created_at, filename=f"annotix-{project_id[:8]}-{export_id[:8]}.zip", **preview.model_dump())
    (workspace / "export.json").write_text(json.dumps({**record.model_dump(mode="json"), "class_mapping": {str(key): value for key, value in mapping.items()}, "images": manifest_images}, indent=2), encoding="utf-8")
    archive_path = workspace / record.filename
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(workspace.rglob("*")):
            if path.is_file() and path != archive_path:
                archive.write(path, path.relative_to(workspace).as_posix())
    return record


def export_archive(export_id: str) -> tuple[Path, str]:
    if len(export_id) != 32 or any(character not in "0123456789abcdef" for character in export_id):
        raise FileNotFoundError
    workspace = get_project_root(get_current_project_id()) / "generated" / "exports" / export_id
    metadata = _read_json(workspace / "export.json")
    path = workspace / metadata["filename"]
    if not path.is_file():
        raise FileNotFoundError
    return path, metadata["filename"]
