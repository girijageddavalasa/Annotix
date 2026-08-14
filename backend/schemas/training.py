from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AugmentationValues(BaseModel):
    rotation: int = 0
    horizontal_flip: bool = False
    vertical_flip: bool = False
    brightness: float = Field(default=1.0, ge=0.1, le=3.0)
    contrast: float = Field(default=1.0, ge=0.1, le=3.0)
    saturation: float = Field(default=1.0, ge=0.0, le=3.0)
    hue: float = Field(default=0.0, ge=-180, le=180)
    grayscale: bool = False
    pixelation: float = Field(default=0.0, ge=0, le=100)
    blur: float = Field(default=0.0, ge=0, le=20)
    noise: float = Field(default=0.0, ge=0, le=100)


class RandomAugmentation(BaseModel):
    min_operations: int = Field(default=1, ge=0)
    max_operations: int = Field(default=4, ge=0)
    seed: str | int | None = None
    enabled_operations: list[Literal['rotation', 'horizontal_flip', 'vertical_flip', 'brightness', 'contrast', 'saturation', 'hue', 'grayscale', 'pixelation', 'blur', 'noise']] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_limits(self):
        if self.max_operations < self.min_operations:
            raise ValueError('Maximum random operations must be at least the minimum')
        if self.min_operations > len(set(self.enabled_operations)):
            raise ValueError('Minimum random operations exceeds enabled operations')
        return self


class AugmentationConfiguration(BaseModel):
    enabled: bool = True
    mode: Literal['manual', 'random'] = 'manual'
    output_strategy: Literal['on_the_fly', 'save'] = 'on_the_fly'
    augmentations_per_image: int = Field(default=1, ge=1, le=100)
    manual: AugmentationValues = Field(default_factory=AugmentationValues)
    random: RandomAugmentation = Field(default_factory=RandomAugmentation)


class TrainingStartRequest(BaseModel):
    epochs: int = Field(ge=1, le=500)
    image_size: int = Field(ge=32, le=4096)
    batch_size: int = Field(ge=1, le=1024)
    device: Literal['auto', 'cpu', 'gpu'] = 'auto'
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    validation_fraction: float = Field(default=.2, gt=0, lt=1)
    augmentation: AugmentationConfiguration = Field(default_factory=AugmentationConfiguration)


class TrainingMetrics(BaseModel):
    epoch: int | None = None
    total_epochs: int | None = None
    loss: float | None = None
    box_loss: float | None = None
    class_loss: float | None = None
    validation_loss: float | None = None
    validation_box_loss: float | None = None
    validation_class_loss: float | None = None
    precision: float | None = None
    recall: float | None = None
    map50: float | None = None
    map50_95: float | None = None
    progress: float = 0


class TrainingImageReference(BaseModel):
    id: str
    filename: str


class TrainingDatasetSummary(BaseModel):
    total_images: int = 0
    training_images: int = 0
    validation_images: int = 0
    total_annotations: int = 0
    training_annotations: int = 0
    validation_annotations: int = 0
    number_of_classes: int = 0
    every_class_in_training: bool = False
    missing_training_class_ids: list[int] = Field(default_factory=list)


class TrainingJob(BaseModel):
    id: str
    project_id: str
    model_id: str
    state: Literal['IDLE', 'PREPARING', 'TRAINING', 'COMPLETED', 'FAILED', 'CANCELLED']
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    pid: int | None = None
    error: str | None = None
    metrics: TrainingMetrics = Field(default_factory=TrainingMetrics)
    configuration: TrainingStartRequest
    annotated_images: int
    class_count: int
    train_images: list[TrainingImageReference] = Field(default_factory=list)
    validation_images: list[TrainingImageReference] = Field(default_factory=list)
    dataset_summary: TrainingDatasetSummary = Field(default_factory=TrainingDatasetSummary)
    warnings: list[str] = Field(default_factory=list)
    snapshot_path: str | None = None
    model_path: str | None = None
    checkpoint_validated: bool = False
    validation_images_tested: int = 0
    smoke_images_with_predictions: int = 0
    smoke_total_predictions: int = 0


class TrainingStatusResponse(BaseModel):
    job: TrainingJob | None = None
    any_training_active: bool = False
    current_project_locked: bool = False
