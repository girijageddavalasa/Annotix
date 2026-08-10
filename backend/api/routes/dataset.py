from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from schemas.dataset import DatasetImage, DatasetState, ImportResult
from services.dataset_service import (
    DatasetImportError,
    get_dataset_state,
    get_image_file,
    get_thumbnail_file,
    import_folder,
    import_zip,
    list_images,
)
from services.training_service import TrainingConflictError, require_project_editable

router = APIRouter(tags=["dataset"])


@router.get("", response_model=DatasetState)
async def dataset_state() -> DatasetState:
    return get_dataset_state()


@router.get("/images", response_model=list[DatasetImage])
async def dataset_images() -> list[DatasetImage]:
    return list_images()


@router.get("/images/{image_id}", response_class=FileResponse)
async def serve_dataset_image(image_id: str) -> FileResponse:
    result = get_image_file(image_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    path, _ = result
    return FileResponse(path)


@router.get("/images/{image_id}/thumbnail", response_class=FileResponse)
async def serve_dataset_thumbnail(image_id: str) -> FileResponse:
    path = get_thumbnail_file(image_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/upload-zip", response_model=ImportResult)
async def upload_dataset_zip(file: UploadFile = File(...)) -> ImportResult:
    try:
        require_project_editable()
        return await import_zip(file)
    except (DatasetImportError, TrainingConflictError) as exc:
        code = status.HTTP_409_CONFLICT if isinstance(exc, TrainingConflictError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/upload-folder", response_model=ImportResult)
async def upload_dataset_folder(files: list[UploadFile] = File(...)) -> ImportResult:
    try:
        require_project_editable()
        return await import_folder(files)
    except (DatasetImportError, TrainingConflictError) as exc:
        code = status.HTTP_409_CONFLICT if isinstance(exc, TrainingConflictError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc
