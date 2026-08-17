from pydantic import BaseModel
from typing import Literal, Optional


class CheckResult(BaseModel):
    name: str
    status: Literal["PASS", "WARNING", "FAIL"]
    message: str
    details: Optional[str] = None


class CategoryResult(BaseModel):
    category: str
    status: Literal["PASS", "WARNING", "FAIL"]
    checks: list[CheckResult]
    warnings: list[str] = []


class ValidationReport(BaseModel):
    project_id: str
    timestamp: str
    overall_status: Literal["PASS", "WARNING", "FAIL"]
    categories: list[CategoryResult]
    summary: dict[str, str]
