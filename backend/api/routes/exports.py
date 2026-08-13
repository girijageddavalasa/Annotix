from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from schemas.exports import ExportPreview, ExportRecord
from services.export_service import ExportValidationError, create_export, export_archive, preview_export

router = APIRouter(tags=["exports"])


@router.get("/preview", response_model=ExportPreview)
async def preview() -> ExportPreview:
    return preview_export()


@router.post("", response_model=ExportRecord, status_code=201)
async def create() -> ExportRecord:
    try:
        return create_export()
    except ExportValidationError as error:
        raise HTTPException(status_code=422, detail=[issue.model_dump() for issue in error.issues]) from error


@router.get("/{export_id}/download")
async def download(export_id: str) -> FileResponse:
    try:
        path, filename = export_archive(export_id)
    except (FileNotFoundError, OSError, ValueError, KeyError):
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(path, media_type="application/zip", filename=filename)

