"""API router composition for system and job endpoints."""

from fastapi import APIRouter

from nir_tagging_service.api.jobs import create_jobs_router
from nir_tagging_service.api.system import router as system_router
from nir_tagging_service.config import Settings


def create_api_router(settings: Settings) -> APIRouter:
    """Build the top-level API router with all mounted subrouters."""

    router = APIRouter()
    router.include_router(system_router)
    router.include_router(create_jobs_router(settings))
    return router
