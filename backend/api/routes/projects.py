from fastapi import APIRouter, HTTPException, status

from schemas.projects import ProjectCreate, ProjectDeleteResponse, ProjectListResponse, ProjectRecord, ProjectUpdate
from services.project_workspace import (
    DuplicateProjectNameError,
    ProjectMetadataError,
    ProjectNotFoundError,
    activate_project,
    create_project,
    delete_project,
    get_current_project,
    get_current_project_id,
    list_projects,
    rename_project,
)
from services.training_service import TrainingConflictError, project_training_locked

router = APIRouter(tags=["projects"])


def _project_error(error: Exception) -> HTTPException:
    if isinstance(error, TrainingConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, DuplicateProjectNameError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))


@router.get("", response_model=ProjectListResponse)
async def projects() -> ProjectListResponse:
    try:
        return ProjectListResponse(current_project_id=get_current_project_id(), projects=list_projects())
    except ProjectMetadataError as exc:
        raise _project_error(exc) from exc


@router.get("/current", response_model=ProjectRecord)
async def current_project() -> ProjectRecord:
    try:
        return get_current_project()
    except (ProjectNotFoundError, ProjectMetadataError) as exc:
        raise _project_error(exc) from exc


@router.post("", response_model=ProjectRecord, status_code=status.HTTP_201_CREATED)
async def add_project(data: ProjectCreate) -> ProjectRecord:
    try:
        return create_project(data.name)
    except (DuplicateProjectNameError, ProjectMetadataError) as exc:
        raise _project_error(exc) from exc


@router.post("/{project_id}/activate", response_model=ProjectRecord)
async def set_active_project(project_id: str) -> ProjectRecord:
    try:
        return activate_project(project_id)
    except (ProjectNotFoundError, ProjectMetadataError) as exc:
        raise _project_error(exc) from exc


@router.patch("/{project_id}", response_model=ProjectRecord)
async def update_project(project_id: str, data: ProjectUpdate) -> ProjectRecord:
    try:
        return rename_project(project_id, data.name)
    except (ProjectNotFoundError, DuplicateProjectNameError, ProjectMetadataError) as exc:
        raise _project_error(exc) from exc


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def remove_project(project_id: str) -> ProjectDeleteResponse:
    try:
        if project_training_locked(project_id):
            raise TrainingConflictError('A project cannot be deleted while it is training')
        deleted_id, current = delete_project(project_id)
        return ProjectDeleteResponse(deleted_id=deleted_id, current_project=current)
    except (ProjectNotFoundError, ProjectMetadataError, TrainingConflictError) as exc:
        raise _project_error(exc) from exc
