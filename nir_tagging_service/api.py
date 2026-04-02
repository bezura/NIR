from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from nir_tagging_service.config import Settings
from nir_tagging_service.dependencies import LoggerDep, ProcessJobDep, SessionFactoryDep, SettingsDep
from nir_tagging_service.job_service import (
    JobFailedError,
    JobNotFoundError,
    ResultNotReadyError,
    create_tagging_job,
    fetch_job_result,
    fetch_job_status,
)
from nir_tagging_service.observability import log_event
from nir_tagging_service.schemas import (
    CreateTaggingJobRequest,
    CreateTaggingJobResponse,
    ErrorPayload,
    HealthResponse,
    JobResultResponse,
    JobStatusResponse,
    ReadinessResponse,
)


def error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    payload = ErrorPayload(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content={"error": payload.model_dump()})


def create_api_router(settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    async def healthcheck(current_settings: SettingsDep) -> HealthResponse:
        return HealthResponse(status="ok", service=current_settings.app_name)

    @router.get("/readiness", response_model=ReadinessResponse)
    async def readinesscheck(current_settings: SettingsDep) -> ReadinessResponse:
        return ReadinessResponse(status="ready", service=current_settings.app_name)

    @router.post(
        f"{settings.api_prefix}/jobs",
        response_model=CreateTaggingJobResponse,
        status_code=202,
    )
    async def create_job(
        payload: CreateTaggingJobRequest,
        background_tasks: BackgroundTasks,
        current_settings: SettingsDep,
        session_factory: SessionFactoryDep,
        process_job: ProcessJobDep,
        logger: LoggerDep,
    ) -> CreateTaggingJobResponse:
        response, job_id, document_id, status = await run_in_threadpool(
            create_tagging_job,
            session_factory,
            payload,
            current_settings.api_prefix,
        )
        background_tasks.add_task(process_job, job_id)
        log_event(logger, "job_queued", job_id=job_id, document_id=document_id, status=status)
        return response

    @router.get(f"{settings.api_prefix}/jobs/{{job_id}}", response_model=JobStatusResponse)
    async def get_job_status(
        job_id: str,
        session_factory: SessionFactoryDep,
    ) -> JobStatusResponse | JSONResponse:
        try:
            return await run_in_threadpool(fetch_job_status, session_factory, job_id)
        except JobNotFoundError as exc:
            return error_response(404, "job_not_found", str(exc))

    @router.get(f"{settings.api_prefix}/jobs/{{job_id}}/result", response_model=JobResultResponse)
    async def get_job_result(
        job_id: str,
        session_factory: SessionFactoryDep,
    ) -> JobResultResponse | JSONResponse:
        try:
            return await run_in_threadpool(fetch_job_result, session_factory, job_id)
        except JobNotFoundError as exc:
            return error_response(404, "job_not_found", str(exc))
        except JobFailedError as exc:
            return error_response(409, exc.code, exc.message)
        except ResultNotReadyError as exc:
            return error_response(409, "result_not_ready", str(exc))

    return router
