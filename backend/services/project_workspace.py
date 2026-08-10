import json
import os
import re
import shutil
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from core.config import settings
from schemas.projects import ProjectRecord, ProjectStats

PROJECTS_DIR = settings.data_dir / "projects"
CURRENT_PROJECT_FILE = settings.data_dir / "current_project.json"
PROJECT_METADATA_FILENAME = "project.json"
PROJECT_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_project_lock = threading.RLock()


class ProjectNotFoundError(LookupError):
    pass


class DuplicateProjectNameError(ValueError):
    pass


class ProjectMetadataError(RuntimeError):
    pass


def _project_root(project_id: str) -> Path:
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ProjectNotFoundError("Project not found")
    root = (PROJECTS_DIR / project_id).resolve()
    if root.parent != PROJECTS_DIR.resolve():
        raise ProjectNotFoundError("Project not found")
    return root


def get_project_root(project_id: str) -> Path:
    """Return a validated project root for services that operate on an explicit project."""
    root = _project_root(project_id)
    if not root.is_dir():
        raise ProjectNotFoundError('Project not found')
    return root


def _ensure_directories(project_id: str) -> Path:
    root = _project_root(project_id)
    for name in ("images", "annotations", "predictions", "metadata", "models", "logs", "generated"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def _metadata_path(project_id: str) -> Path:
    return _project_root(project_id) / "metadata" / PROJECT_METADATA_FILENAME


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary_path, path)


def _write_project(record: ProjectRecord) -> None:
    path = _metadata_path(record.id)
    payload = record.model_dump(mode="json", exclude={"stats"})
    _write_json_atomic(path, payload)


def _read_project(project_id: str) -> ProjectRecord:
    path = _metadata_path(project_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = ProjectRecord.model_validate(payload)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise ProjectMetadataError(f"Project metadata for {project_id} is unreadable") from exc
    if record.id != project_id:
        raise ProjectMetadataError("Project metadata ID does not match its directory")
    return record.model_copy(update={"stats": _project_stats(project_id)})


def _project_stats(project_id: str) -> ProjectStats:
    root = _project_root(project_id)
    images = classes = annotations = 0
    try:
        dataset = json.loads((root / "metadata" / "dataset.json").read_text(encoding="utf-8"))
        images = len(dataset.get("images", []))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        pass
    try:
        class_data = json.loads((root / "metadata" / "classes.json").read_text(encoding="utf-8"))
        classes = len(class_data.get("classes", []))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        pass
    for path in (root / "annotations").glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            annotations += len(payload.get("annotations", []))
        except (json.JSONDecodeError, OSError, TypeError):
            continue
    return ProjectStats(images=images, annotations=annotations, classes=classes)


def _create_project_record(name: str) -> ProjectRecord:
    project_id = uuid.uuid4().hex
    _ensure_directories(project_id)
    now = datetime.now(UTC)
    record = ProjectRecord(id=project_id, name=name, created_at=now, updated_at=now)
    _write_project(record)
    return record


def _write_active_project(project_id: str) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(CURRENT_PROJECT_FILE, {"project_id": project_id})


def _migrate_or_create_initial_project() -> str:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    existing_active = None
    if CURRENT_PROJECT_FILE.exists():
        try:
            existing_active = str(json.loads(CURRENT_PROJECT_FILE.read_text(encoding="utf-8")).get("project_id", ""))
        except (json.JSONDecodeError, OSError):
            pass
    if existing_active and PROJECT_ID_PATTERN.fullmatch(existing_active) and _project_root(existing_active).is_dir():
        _ensure_directories(existing_active)
        if not _metadata_path(existing_active).exists():
            now = datetime.now(UTC)
            _write_project(ProjectRecord(id=existing_active, name="Untitled project", created_at=now, updated_at=now))
        return existing_active

    for directory in PROJECTS_DIR.iterdir():
        if directory.is_dir() and PROJECT_ID_PATTERN.fullmatch(directory.name) and _metadata_path(directory.name).exists():
            _write_active_project(directory.name)
            return directory.name

    record = _create_project_record("Untitled project")
    _write_active_project(record.id)
    return record.id


def get_current_project_id() -> str:
    with _project_lock:
        project_id = _migrate_or_create_initial_project()
        try:
            pointer = json.loads(CURRENT_PROJECT_FILE.read_text(encoding="utf-8"))
            requested_id = str(pointer.get("project_id", ""))
            if requested_id and _metadata_path(requested_id).exists():
                return requested_id
        except (json.JSONDecodeError, OSError, ProjectNotFoundError):
            pass
        _write_active_project(project_id)
        return project_id


def get_project_directories() -> tuple[str, Path, Path, Path]:
    project_id = get_current_project_id()
    root = _ensure_directories(project_id)
    return project_id, root / "images", root / "annotations", root / "metadata"


def list_projects() -> list[ProjectRecord]:
    with _project_lock:
        get_current_project_id()
        records = []
        for directory in PROJECTS_DIR.iterdir():
            if directory.is_dir() and PROJECT_ID_PATTERN.fullmatch(directory.name) and _metadata_path(directory.name).exists():
                records.append(_read_project(directory.name))
        return sorted(records, key=lambda record: record.created_at)


def get_current_project() -> ProjectRecord:
    return _read_project(get_current_project_id())


def create_project(name: str) -> ProjectRecord:
    with _project_lock:
        _ensure_unique_name(name)
        record = _create_project_record(name)
        _write_active_project(record.id)
        return _read_project(record.id)


def activate_project(project_id: str) -> ProjectRecord:
    with _project_lock:
        record = _read_project(project_id)
        _write_active_project(project_id)
        return record


def rename_project(project_id: str, name: str) -> ProjectRecord:
    with _project_lock:
        _ensure_unique_name(name, excluded_id=project_id)
        record = _read_project(project_id)
        updated = record.model_copy(update={"name": name, "updated_at": datetime.now(UTC), "stats": ProjectStats()})
        _write_project(updated)
        return _read_project(project_id)


def touch_current_project() -> None:
    with _project_lock:
        record = _read_project(get_current_project_id())
        _write_project(record.model_copy(update={"updated_at": datetime.now(UTC), "stats": ProjectStats()}))


def delete_project(project_id: str) -> tuple[str, ProjectRecord]:
    with _project_lock:
        _read_project(project_id)
        target = _project_root(project_id)
        if target.parent != PROJECTS_DIR.resolve() or target == PROJECTS_DIR.resolve():
            raise ProjectNotFoundError("Invalid project deletion target")
        shutil.rmtree(target)
        remaining = list_projects()
        if remaining:
            current = remaining[0]
            if get_current_project_id() != project_id:
                try:
                    current = _read_project(get_current_project_id())
                except (ProjectNotFoundError, ProjectMetadataError):
                    pass
        else:
            current = _create_project_record("Untitled project")
        _write_active_project(current.id)
        return project_id, _read_project(current.id)


def _ensure_unique_name(name: str, excluded_id: str | None = None) -> None:
    normalized = name.casefold()
    if any(record.id != excluded_id and record.name.casefold() == normalized for record in list_projects()):
        raise DuplicateProjectNameError(f'A project named "{name}" already exists')
