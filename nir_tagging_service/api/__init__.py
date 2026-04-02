from fastapi import APIRouter

from nir_tagging_service.api.jobs import create_jobs_router
from nir_tagging_service.api.system import router as system_router
from nir_tagging_service.config import Settings


def create_api_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    router.include_router(system_router)
    router.include_router(create_jobs_router(settings))
    return router
