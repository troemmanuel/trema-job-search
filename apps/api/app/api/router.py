from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.applications import router as applications_router
from app.api.v1.candidate import router as candidate_router
from app.api.v1.scheduler import router as scheduler_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.settings import router as settings_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(applications_router)
api_v1_router.include_router(candidate_router)
api_v1_router.include_router(scheduler_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(settings_router)
