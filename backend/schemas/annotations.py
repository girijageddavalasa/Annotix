from pydantic import BaseModel, Field, model_validator


class AnnotationInput(BaseModel):
    id: str | None = None
    class_id: int = Field(ge=0)
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(gt=0)
    y2: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_box(self):
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("Bounding box must have positive width and height")
        return self


class AnnotationRecord(BaseModel):
    id: str
    image_id: str
    class_id: int
    x1: float
    y1: float
    x2: float
    y2: float


class AnnotationSaveRequest(BaseModel):
    annotations: list[AnnotationInput]


class AnnotationListResponse(BaseModel):
    image_id: str
    annotations: list[AnnotationRecord]


class DeleteAnnotationResponse(BaseModel):
    deleted_id: str

