from fastapi import APIRouter, HTTPException, status

from schemas.classes import ClassCreate, ClassRecord, ClassUpdate, DeleteClassResponse
from services.class_service import (
    ClassInUseError,
    ClassMetadataError,
    ClassNotFoundError,
    DuplicateClassNameError,
    create_class,
    delete_class,
    list_classes,
    update_class,
)
from services.training_service import TrainingConflictError, require_project_editable

router = APIRouter(tags=["classes"])


def _service_error(error: Exception) -> HTTPException:
    if isinstance(error, TrainingConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ClassNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, (DuplicateClassNameError, ClassInUseError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


@router.get("", response_model=list[ClassRecord])
async def get_classes() -> list[ClassRecord]:
    try:
        return list_classes()
    except ClassMetadataError as exc:
        raise _service_error(exc) from exc


@router.post("", response_model=ClassRecord, status_code=status.HTTP_201_CREATED)
async def add_class(data: ClassCreate) -> ClassRecord:
    try:
        require_project_editable()
        return create_class(data)
    except (DuplicateClassNameError, ClassMetadataError, TrainingConflictError) as exc:
        raise _service_error(exc) from exc


@router.patch("/{class_id}", response_model=ClassRecord)
async def edit_class(class_id: int, data: ClassUpdate) -> ClassRecord:
    try:
        require_project_editable()
        return update_class(class_id, data)
    except (ClassNotFoundError, DuplicateClassNameError, ClassMetadataError, ValueError, TrainingConflictError) as exc:
        raise _service_error(exc) from exc


@router.delete("/{class_id}", response_model=DeleteClassResponse)
async def remove_class(class_id: int) -> DeleteClassResponse:
    try:
        require_project_editable()
        delete_class(class_id)
        return DeleteClassResponse(deleted_id=class_id)
    except (ClassNotFoundError, ClassInUseError, ClassMetadataError, TrainingConflictError) as exc:
        raise _service_error(exc) from exc
