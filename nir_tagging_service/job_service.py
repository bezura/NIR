from __future__ import annotations

from dataclasses import asdict
from logging import Logger
from time import perf_counter
from typing import Any

from pydantic import TypeAdapter

from nir_tagging_service.db.models import Document, TaggingJob, TaggingResult, utc_now
from nir_tagging_service.observability import log_event, track_stage
from nir_tagging_service.preprocessing import prepare_text
from nir_tagging_service.schemas import (
    CreateTaggingJobRequest,
    CreateTaggingJobResponse,
    ErrorPayload,
    JobResultResponse,
    JobStatusResponse,
    TagResponse,
)


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job '{job_id}' was not found")


class JobFailedError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ResultNotReadyError(Exception):
    def __init__(self, job_id: str, status: str) -> None:
        self.job_id = job_id
        self.status = status
        super().__init__(f"Job '{job_id}' is still {status}")


def create_tagging_job(
    session_factory: Any,
    payload: CreateTaggingJobRequest,
    api_prefix: str,
) -> tuple[CreateTaggingJobResponse, str, str, str]:
    with session_factory() as session:
        document = Document(
            source=payload.source,
            text=payload.text,
            metadata_json=payload.metadata,
        )
        job = TaggingJob(
            document=document,
            status="queued",
            options_json=payload.options.model_dump(),
        )
        session.add_all([document, job])
        session.commit()
        session.refresh(document)
        session.refresh(job)

    response = CreateTaggingJobResponse(
        job_id=job.id,
        status=job.status,
        document_id=document.id,
        status_url=f"{api_prefix}/jobs/{job.id}",
        result_url=f"{api_prefix}/jobs/{job.id}/result",
    )
    return response, job.id, document.id, job.status


def fetch_job_status(session_factory: Any, job_id: str) -> JobStatusResponse:
    with session_factory() as session:
        job = session.get(TaggingJob, job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        error = None
        if job.error_code and job.error_message:
            error = ErrorPayload(code=job.error_code, message=job.error_message)

        return JobStatusResponse(
            job_id=job.id,
            document_id=job.document_id,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            result_available=job.status == "completed",
            error=error,
        )


def fetch_job_result(session_factory: Any, job_id: str) -> JobResultResponse:
    with session_factory() as session:
        job = session.get(TaggingJob, job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        if job.status == "failed":
            raise JobFailedError(
                job.error_code or "processing_failed",
                job.error_message or "The job failed during processing",
            )

        if job.status != "completed":
            raise ResultNotReadyError(job_id, job.status)

        result = session.query(TaggingResult).filter(TaggingResult.job_id == job_id).one()
        return JobResultResponse(
            job_id=job.id,
            document_id=result.document_id,
            category={
                "code": result.category_code,
                "label": result.category_label,
                "score": result.category_score,
            },
            tags=result.tags_json,
            score=result.score,
            signals=result.signals_json,
            explanation=result.explanation,
        )


def process_job(
    job_id: str,
    session_factory: Any,
    services: Any,
    logger: Logger,
) -> None:
    with session_factory() as session:
        job = session.get(TaggingJob, job_id)
        if job is None:
            return

        try:
            total_started = perf_counter()
            job.status = "processing"
            job.started_at = utc_now()
            session.commit()
            log_event(
                logger,
                "job_processing_started",
                job_id=job.id,
                document_id=job.document_id,
                status=job.status,
            )

            document = session.get(Document, job.document_id)
            timings_ms: dict[str, float] = {}

            with track_stage(timings_ms, "preprocessing"):
                prepared = prepare_text(document.text, document.source)

            max_tags = job.options_json.get("max_tags", 5)

            with track_stage(timings_ms, "categorization"):
                category_result = services.categorizer.categorize(prepared.categorization_chunks)

            with track_stage(timings_ms, "tagging"):
                tags = services.tagger.extract_tags(prepared.tag_extraction_chunks, max_tags=max_tags)

            tags_payload = [asdict(tag) for tag in tags]
            explanation = None
            signals = {
                "chunked": prepared.chunked,
                "content_type": prepared.content_type,
                "num_chunks": len(prepared.chunks),
                "source": document.source,
                "pipeline": {
                    "content_type_hint": job.options_json.get("content_type_hint"),
                    "content_type_hint_applied": False,
                },
                "llm_postprocessed": False,
                "timings_ms": timings_ms,
                "category_scores_top_k": category_result.top_k(3),
            }

            if job.options_json.get("use_llm_postprocess") and services.enhancer is not None:
                try:
                    with track_stage(timings_ms, "llm_postprocess"):
                        enhanced = services.enhancer.enhance(
                            text=document.text,
                            category={
                                "code": category_result.category.code,
                                "label": category_result.category.label,
                                "score": category_result.score,
                            },
                            tags=tags_payload,
                        )
                        validated_tags = TypeAdapter(list[TagResponse]).validate_python(
                            enhanced.get("tags", tags_payload)
                        )
                        candidate_explanation = enhanced.get("explanation")
                        if candidate_explanation is not None and not isinstance(candidate_explanation, str):
                            raise TypeError("enhancer explanation must be a string or null")
                        tags_payload = [tag.model_dump() for tag in validated_tags]
                        explanation = candidate_explanation
                        signals["llm_postprocessed"] = True
                except Exception:  # noqa: BLE001
                    signals["llm_postprocessed"] = False
                    signals["llm_postprocess_error"] = True
                    log_event(
                        logger,
                        "llm_postprocess_fallback",
                        job_id=job.id,
                        document_id=document.id,
                        status="fallback",
                    )

            result = TaggingResult(
                job_id=job.id,
                document_id=document.id,
                category_code=category_result.category.code,
                category_label=category_result.category.label,
                category_score=category_result.score,
                score=category_result.score,
                tags_json=tags_payload,
                signals_json=signals,
                explanation=explanation,
            )
            with track_stage(timings_ms, "db_write"):
                session.add(result)
                job.status = "completed"
                job.finished_at = utc_now()
                session.commit()

            timings_ms["total"] = round((perf_counter() - total_started) * 1000, 3)
            result.signals_json = signals
            session.commit()
            log_event(logger, "job_completed", job_id=job.id, document_id=document.id, status=job.status)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            failed_job = session.get(TaggingJob, job_id)
            if failed_job is None:
                return

            failed_job.status = "failed"
            failed_job.error_code = "processing_failed"
            failed_job.error_message = str(exc)
            failed_job.finished_at = utc_now()
            session.commit()
            log_event(
                logger,
                "job_failed",
                job_id=failed_job.id,
                document_id=failed_job.document_id,
                status=failed_job.status,
                error_message=str(exc),
            )
