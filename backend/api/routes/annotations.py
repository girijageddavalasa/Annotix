from fastapi import APIRouter, HTTPException, status

from schemas.annotations import AnnotationInput, AnnotationListResponse, AnnotationRecord, AnnotationSaveRequest, DeleteAnnotationResponse
from services.annotation_service import (
    AnnotationMetadataError,
    AnnotationNotFoundError,
    AnnotationValidationError,
    delete_annotation,
    list_annotations,
    replace_annotations,
    update_annotation,
)
from services.class_service import ClassNotFoundError
from services.training_service import TrainingConflictError, require_project_editable

router = APIRouter(tags=["annotations"])


def _raise_service_error(error: Exception) -> HTTPException:
    if isinstance(error, TrainingConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, AnnotationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, (AnnotationValidationError, ClassNotFoundError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


@router.get("/{image_id}", response_model=AnnotationListResponse)
async def get_image_annotations(image_id: str) -> AnnotationListResponse:
    try:
        return AnnotationListResponse(image_id=image_id, annotations=list_annotations(image_id))
    except (AnnotationValidationError, AnnotationMetadataError) as exc:
        raise _raise_service_error(exc) from exc


@router.post("/{image_id}", response_model=AnnotationListResponse)
async def save_image_annotations(image_id: str, data: AnnotationSaveRequest) -> AnnotationListResponse:
    try:
        require_project_editable()
        records = replace_annotations(image_id, data.annotations)
        return AnnotationListResponse(image_id=image_id, annotations=records)
    except (AnnotationValidationError, AnnotationMetadataError, ClassNotFoundError, TrainingConflictError) as exc:
        raise _raise_service_error(exc) from exc


@router.put("/{image_id}/{annotation_id}", response_model=AnnotationRecord)
async def edit_image_annotation(image_id: str, annotation_id: str, data: AnnotationInput) -> AnnotationRecord:
    try:
        require_project_editable()
        return update_annotation(image_id, annotation_id, data)
    except (AnnotationNotFoundError, AnnotationValidationError, AnnotationMetadataError, ClassNotFoundError, TrainingConflictError) as exc:
        raise _raise_service_error(exc) from exc


@router.delete("/{image_id}/{annotation_id}", response_model=DeleteAnnotationResponse)
async def remove_image_annotation(image_id: str, annotation_id: str) -> DeleteAnnotationResponse:
    try:
        require_project_editable()
        delete_annotation(image_id, annotation_id)
        return DeleteAnnotationResponse(deleted_id=annotation_id)
    except (AnnotationNotFoundError, AnnotationValidationError, AnnotationMetadataError, TrainingConflictError) as exc:
        raise _raise_service_error(exc) from exc
