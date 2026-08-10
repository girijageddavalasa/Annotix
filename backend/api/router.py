from fastapi import APIRouter

from api.routes.health import router as health_router
from api.routes.dataset import router as dataset_router
from api.routes.classes import router as classes_router
from api.routes.annotations import router as annotations_router
from api.routes.projects import router as projects_router
from api.routes.training import router as training_router
from api.routes.predictions import router as predictions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(dataset_router, prefix="/dataset")
api_router.include_router(classes_router, prefix="/classes")
api_router.include_router(annotations_router, prefix="/annotations")
api_router.include_router(projects_router, prefix="/projects")
api_router.include_router(training_router, prefix="/training")
api_router.include_router(predictions_router, prefix="/predictions")
