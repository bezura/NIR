from __future__ import annotations

"""HTTP handlers for asynchronous tagging jobs."""

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from nir_tagging_service.config import Settings
from nir_tagging_service.dependencies import LoggerDep, ProcessJobDep, SessionFactoryDep, SettingsDep
from nir_tagging_service.observability import log_event
from nir_tagging_service.pipeline import (
    JobFailedError,
    JobNotFoundError,
    ResultNotReadyError,
    create_tagging_job,
    fetch_job_result,
    fetch_job_status,
)
from nir_tagging_service.schemas import (
    CreateTaggingJobRequest,
    CreateTaggingJobResponse,
    ErrorPayload,
    JobResultResponse,
    JobStatusResponse,
)


def error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    """Return a standardized error payload for job endpoints."""

    payload = ErrorPayload(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content={"error": payload.model_dump()})


def create_jobs_router(settings: Settings) -> APIRouter:
    """Build the router that exposes job creation, status and result endpoints."""

    router = APIRouter(prefix=settings.api_prefix)

    @router.post("/jobs", response_model=CreateTaggingJobResponse, status_code=202)
    async def create_job(
        payload: CreateTaggingJobRequest,
        background_tasks: BackgroundTasks,
        current_settings: SettingsDep,
        session_factory: SessionFactoryDep,
        process_job: ProcessJobDep,
        logger: LoggerDep,
    ) -> CreateTaggingJobResponse:
        """Persist a new job and enqueue background processing."""

        response, job_id, document_id, status = await create_tagging_job(
            session_factory,
            payload,
            current_settings.api_prefix,
        )
        background_tasks.add_task(process_job, job_id)
        log_event(logger, "job_queued", job_id=job_id, document_id=document_id, status=status)
        return response

    @router.get("/jobs/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(
        job_id: str,
        session_factory: SessionFactoryDep,
    ) -> JobStatusResponse | JSONResponse:
        """Return the current status and progress snapshot for a job."""

        try:
            return await fetch_job_status(session_factory, job_id)
        except JobNotFoundError as exc:
            return error_response(404, "job_not_found", str(exc))

    @router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
    async def get_job_result(
        job_id: str,
        session_factory: SessionFactoryDep,
    ) -> JobResultResponse | JSONResponse:
        """Return the completed result or a normalized job error response."""

        try:
            return await fetch_job_result(session_factory, job_id)
        except JobNotFoundError as exc:
            return error_response(404, "job_not_found", str(exc))
        except JobFailedError as exc:
            return error_response(409, exc.code, exc.message)
        except ResultNotReadyError as exc:
            return error_response(409, "result_not_ready", str(exc))

    return router
