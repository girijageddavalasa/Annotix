from fastapi import APIRouter

from schemas.validation import ValidationReport
from services.validation_service import run_full_validation

router = APIRouter(tags=["validation"])


@router.get("/", response_model=ValidationReport)
async def validate_pipeline() -> ValidationReport:
    """Run complete end-to-end pipeline validation for the active project."""
    return run_full_validation()
