import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from schemas.dataset import DatasetImage, DatasetState, DatasetStats, ImportIssue, ImportResult
from services.class_service import get_class_count
from services.project_workspace import get_project_directories, touch_current_project

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
METADATA_FILENAME = "dataset.json"
METADATA_SCHEMA_VERSION = 2
COPY_BUFFER_SIZE = 1024 * 1024
EXIF_ORIENTATION_TAG = 274


class DatasetImportError(ValueError):
    pass


def _metadata_path() -> Path:
    return get_project_directories()[3] / METADATA_FILENAME


def _load_images() -> list[DatasetImage]:
    path = _metadata_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        images = [DatasetImage.model_validate(item) for item in payload.get("images", [])]
        if int(payload.get("schema_version", 1)) < METADATA_SCHEMA_VERSION:
            images_dir = get_project_directories()[1]
            for image in images:
                image_path = images_dir / image.relative_path
                try:
                    with Image.open(image_path) as image_file:
                        width, height = image_file.size
                        if image_file.getexif().get(EXIF_ORIENTATION_TAG) in {5, 6, 7, 8}:
                            width, height = height, width
                        image.width, image.height = width, height
                except (UnidentifiedImageError, OSError, ValueError):
                    continue
            try:
                _write_images_payload(path, images)
            except OSError:
                pass
        return images
    except (json.JSONDecodeError, OSError, ValueError):
        return []


def _save_images(images: list[DatasetImage]) -> None:
    path = _metadata_path()
    _write_images_payload(path, images)
    touch_current_project()


def _write_images_payload(path: Path, images: list[DatasetImage]) -> None:
    payload = {"schema_version": METADATA_SCHEMA_VERSION, "images": [image.model_dump() for image in images]}
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary_path, path)


def _stats(images: list[DatasetImage]) -> DatasetStats:
    object_counts = _annotation_counts()
    annotated = sum(object_counts.get(image.id, 0) > 0 for image in images)
    return DatasetStats(
        total_images=len(images),
        annotated_images=annotated,
        unannotated_images=len(images) - annotated,
        classes=get_class_count(),
        total_objects=sum(object_counts.values()),
    )


def _annotation_counts() -> dict[str, int]:
    annotations_dir = get_project_directories()[2]
    counts: dict[str, int] = {}
    for path in annotations_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            image_id = str(payload.get("image_id") or path.stem)
            counts[image_id] = len(payload.get("annotations", []))
        except (json.JSONDecodeError, OSError, TypeError):
            continue
    return counts


def get_dataset_state() -> DatasetState:
    project_id = get_project_directories()[0]
    return DatasetState(project_id=project_id, stats=_stats(_load_images()))


def list_images() -> list[DatasetImage]:
    counts = _annotation_counts()
    return [image.model_copy(update={"annotation_status": "annotated" if counts.get(image.id, 0) else "unannotated", "annotation_count": counts.get(image.id, 0)}) for image in _load_images()]


def get_image_file(image_id: str) -> tuple[Path, DatasetImage] | None:
    _, images_dir, _, _ = get_project_directories()
    image = next((item for item in _load_images() if item.id == image_id), None)
    if image is None:
        return None
    path = (images_dir / image.relative_path).resolve()
    if images_dir.resolve() not in path.parents or not path.is_file():
        return None
    return path, image


def get_thumbnail_file(image_id: str) -> Path | None:
    result = get_image_file(image_id)
    if result is None:
        return None
    source_path, _ = result
    metadata_dir = get_project_directories()[3]
    thumbnail_dir = metadata_dir / "thumbnails"
    thumbnail_path = thumbnail_dir / f"{image_id}.jpg"
    if thumbnail_path.exists() and thumbnail_path.stat().st_mtime >= source_path.stat().st_mtime:
        return thumbnail_path
    try:
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((320, 240), Image.Resampling.LANCZOS)
            image.save(thumbnail_path, "JPEG", quality=82, optimize=True)
        return thumbnail_path
    except (UnidentifiedImageError, OSError, ValueError):
        thumbnail_path.unlink(missing_ok=True)
        return None


def _safe_relative_path(raw_path: str) -> Path | None:
    normalized = raw_path.replace("\\", "/").lstrip("/")
    path = PurePosixPath(normalized)
    if not path.name or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return Path(*path.parts)


def _available_destination(images_dir: Path, relative_path: Path) -> Path:
    destination = images_dir / relative_path
    counter = 1
    while destination.exists():
        destination = destination.with_name(f"{relative_path.stem}_{counter}{relative_path.suffix}")
        counter += 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def _index_imported_files(paths: list[Path], issues: list[ImportIssue]) -> ImportResult:
    project_id, images_dir, _, _ = get_project_directories()
    existing = _load_images()
    existing_paths = {image.relative_path for image in existing}
    imported: list[DatasetImage] = []

    for path in paths:
        try:
            with Image.open(path) as image_file:
                image_file.verify()
            with Image.open(path) as image_file:
                width, height = image_file.size
                if image_file.getexif().get(EXIF_ORIENTATION_TAG) in {5, 6, 7, 8}:
                    width, height = height, width
        except (UnidentifiedImageError, OSError, ValueError):
            issues.append(ImportIssue(filename=path.name, reason="File is not a readable image"))
            path.unlink(missing_ok=True)
            continue

        relative_path = path.relative_to(images_dir).as_posix()
        if relative_path in existing_paths:
            continue
        image_id = hashlib.sha256(f"{project_id}:{relative_path}".encode()).hexdigest()[:24]
        imported.append(
            DatasetImage(
                id=image_id,
                filename=path.name,
                relative_path=relative_path,
                width=width,
                height=height,
            )
        )
        existing_paths.add(relative_path)

    all_images = existing + imported
    _save_images(all_images)
    return ImportResult(imported_count=len(imported), stats=_stats(all_images), issues=issues)


async def import_folder(files: list[UploadFile]) -> ImportResult:
    if not files:
        raise DatasetImportError("No files were selected")

    _, images_dir, _, _ = get_project_directories()
    imported_paths: list[Path] = []
    issues: list[ImportIssue] = []
    for upload in files:
        relative_path = _safe_relative_path(upload.filename or "")
        display_name = upload.filename or "Unnamed file"
        if relative_path is None:
            issues.append(ImportIssue(filename=display_name, reason="Invalid relative path"))
            continue
        if relative_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            issues.append(ImportIssue(filename=display_name, reason="Unsupported file type"))
            continue

        destination = _available_destination(images_dir, relative_path)
        try:
            with destination.open("wb") as target:
                while chunk := await upload.read(COPY_BUFFER_SIZE):
                    target.write(chunk)
            imported_paths.append(destination)
        except OSError as exc:
            destination.unlink(missing_ok=True)
            issues.append(ImportIssue(filename=display_name, reason=f"Could not save file: {exc}"))
        finally:
            await upload.close()

    result = _index_imported_files(imported_paths, issues)
    if result.imported_count == 0 and not result.issues:
        raise DatasetImportError("The selected folder contains no supported images")
    return result


async def import_zip(upload: UploadFile) -> ImportResult:
    if not upload.filename or Path(upload.filename).suffix.lower() != ".zip":
        raise DatasetImportError("Please select a valid .zip file")

    _, images_dir, _, _ = get_project_directories()
    imported_paths: list[Path] = []
    issues: list[ImportIssue] = []

    temporary_file = tempfile.NamedTemporaryFile(prefix="annotix_", suffix=".zip", delete=False)
    temporary_path = Path(temporary_file.name)
    try:
        with temporary_file:
            while chunk := await upload.read(COPY_BUFFER_SIZE):
                temporary_file.write(chunk)
        try:
            with zipfile.ZipFile(temporary_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    relative_path = _safe_relative_path(member.filename)
                    if relative_path is None:
                        issues.append(ImportIssue(filename=member.filename, reason="Unsafe or invalid archive path"))
                        continue
                    if relative_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                        issues.append(ImportIssue(filename=member.filename, reason="Unsupported file type"))
                        continue
                    destination = _available_destination(images_dir, relative_path)
                    try:
                        with archive.open(member) as source, destination.open("wb") as target:
                            shutil.copyfileobj(source, target, COPY_BUFFER_SIZE)
                        imported_paths.append(destination)
                    except (OSError, zipfile.BadZipFile) as exc:
                        destination.unlink(missing_ok=True)
                        issues.append(ImportIssue(filename=member.filename, reason=f"Could not extract file: {exc}"))
        except (zipfile.BadZipFile, OSError) as exc:
            raise DatasetImportError("The ZIP file is invalid or corrupted") from exc
    finally:
        temporary_path.unlink(missing_ok=True)
        await upload.close()

    result = _index_imported_files(imported_paths, issues)
    if result.imported_count == 0 and not result.issues:
        raise DatasetImportError("The ZIP file contains no supported images")
    return result
