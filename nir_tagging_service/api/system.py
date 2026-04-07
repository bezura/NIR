"""Technical liveness and readiness endpoints."""

from fastapi import APIRouter

from nir_tagging_service.dependencies import SettingsDep
from nir_tagging_service.schemas import HealthResponse, ReadinessResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def healthcheck(current_settings: SettingsDep) -> HealthResponse:
    """Return a lightweight liveness probe response."""

    return HealthResponse(status="ok", service=current_settings.app_name)


@router.get("/readiness", response_model=ReadinessResponse)
async def readinesscheck(current_settings: SettingsDep) -> ReadinessResponse:
    """Return readiness once the API application has been initialized."""

    return ReadinessResponse(status="ready", service=current_settings.app_name)
