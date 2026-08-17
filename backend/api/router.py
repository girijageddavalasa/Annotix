from fastapi import APIRouter

from api.routes.health import router as health_router
from api.routes.dataset import router as dataset_router
from api.routes.classes import router as classes_router
from api.routes.annotations import router as annotations_router
from api.routes.projects import router as projects_router
from api.routes.training import router as training_router
from api.routes.predictions import router as predictions_router
from api.routes.review import router as review_router
from api.routes.active_learning import router as active_learning_router
from api.routes.exports import router as exports_router
from api.routes.validation import router as validation_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(dataset_router, prefix="/dataset")
api_router.include_router(classes_router, prefix="/classes")
api_router.include_router(annotations_router, prefix="/annotations")
api_router.include_router(projects_router, prefix="/projects")
api_router.include_router(training_router, prefix="/training")
api_router.include_router(predictions_router, prefix="/predictions")
api_router.include_router(review_router, prefix="/review")
api_router.include_router(active_learning_router, prefix="/active-learning")
api_router.include_router(exports_router, prefix="/exports")
api_router.include_router(validation_router, prefix="/validation")
