from __future__ import annotations

from dataclasses import asdict
from logging import Logger
from time import perf_counter

from fastapi.concurrency import run_in_threadpool
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nir_tagging_service.bootstrap import PipelineServices
from nir_tagging_service.db.models import Document, TaggingJob, TaggingResult, utc_now
from nir_tagging_service.job_progress import (
    complete_stage,
    fail_stage,
    initialize_job_progress,
    project_job_progress,
    skip_stage,
    start_stage,
)
from nir_tagging_service.language import resolve_output_language
from nir_tagging_service.observability import log_event, track_stage
from nir_tagging_service.preprocessing import prepare_text
from nir_tagging_service.rules import RuleHints, apply_rule_hints
from nir_tagging_service.schemas import (
    CreateTaggingJobRequest,
    CreateTaggingJobResponse,
    ErrorPayload,
    JobResultResponse,
    JobStatusResponse,
    TaggingOptions,
    TagResponse,
)
from nir_tagging_service.tag_extraction import merge_tag_candidates, reconcile_tag_candidates


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


def _merge_llm_tag_metadata(
    validated_tags: list[TagResponse],
    base_tags: list[dict],
) -> list[dict]:
    base_by_identity = {
        str(tag.get("canonical_name") or tag.get("normalized_label") or tag.get("label")): dict(tag)
        for tag in base_tags
    }
    merged: list[dict] = []

    for tag in validated_tags:
        payload = tag.model_dump()
        identity = str(payload.get("canonical_name") or payload["normalized_label"] or payload["label"])
        original = base_by_identity.get(identity)
        if original is not None:
            payload["source"] = original.get("source", payload.get("source", "model"))
            payload["method"] = original.get("method", payload.get("method", "keyword_extractor"))
            payload["confidence"] = original.get("confidence", payload.get("confidence", payload["score"]))
            payload["reason"] = original.get("reason", payload.get("reason"))
            payload["canonical_name"] = original.get("canonical_name", payload.get("canonical_name"))
        else:
            payload["source"] = payload.get("source", "llm")
            payload["method"] = payload.get("method", "llm_selected")
            payload["confidence"] = payload.get("confidence", payload["score"])
        merged.append(payload)

    return merged


async def create_tagging_job(
    session_factory: async_sessionmaker[AsyncSession],
    payload: CreateTaggingJobRequest,
    api_prefix: str,
) -> tuple[CreateTaggingJobResponse, str, str, str]:
    progress = initialize_job_progress(payload.options, utc_now())
    async with session_factory() as session:
        document = Document(
            source=payload.source,
            text=payload.text,
            metadata_json=payload.metadata,
        )
        job = TaggingJob(
            document=document,
            status="queued",
            options_json=payload.options.model_dump(),
            progress_json=progress,
        )
        session.add_all([document, job])
        await session.commit()
        await session.refresh(document)
        await session.refresh(job)

    response = CreateTaggingJobResponse(
        job_id=job.id,
        status=job.status,
        document_id=document.id,
        status_url=f"{api_prefix}/jobs/{job.id}",
        result_url=f"{api_prefix}/jobs/{job.id}/result",
    )
    return response, job.id, document.id, job.status


async def fetch_job_status(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
) -> JobStatusResponse:
    async with session_factory() as session:
        job = await session.get(TaggingJob, job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        error = None
        if job.error_code and job.error_message:
            error = ErrorPayload(code=job.error_code, message=job.error_message)

        options = TaggingOptions.model_validate(job.options_json)
        progress = project_job_progress(
            job.progress_json,
            options,
            job.status,
            created_at=job.created_at,
        )

        return JobStatusResponse(
            job_id=job.id,
            document_id=job.document_id,
            status=job.status,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            result_available=job.status == "completed",
            current_stage=progress["current_stage"],
            stage_label=progress["stage_label"],
            progress_percent=progress["progress_percent"],
            stage_history=progress["stage_history"],
            pending_stages=progress["pending_stages"],
            error=error,
        )


async def fetch_job_result(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
) -> JobResultResponse:
    async with session_factory() as session:
        job = await session.get(TaggingJob, job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        if job.status == "failed":
            raise JobFailedError(
                job.error_code or "processing_failed",
                job.error_message or "The job failed during processing",
            )

        if job.status != "completed":
            raise ResultNotReadyError(job_id, job.status)

        result = await session.scalar(select(TaggingResult).where(TaggingResult.job_id == job_id))
        if result is None:
            raise ResultNotReadyError(job_id, job.status)

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


async def process_job(
    job_id: str,
    session_factory: async_sessionmaker[AsyncSession],
    services: PipelineServices,
    logger: Logger,
) -> None:
    async with session_factory() as session:
        job = await session.get(TaggingJob, job_id)
        if job is None:
            return

        try:
            total_started = perf_counter()
            options = TaggingOptions.model_validate(job.options_json)
            job.status = "processing"
            job.started_at = utc_now()
            job.progress_json = complete_stage(job.progress_json, "queued", job.started_at, options)
            job.progress_json = start_stage(job.progress_json, "preprocessing", job.started_at, options)
            await session.commit()
            log_event(
                logger,
                "job_processing_started",
                job_id=job.id,
                document_id=job.document_id,
                status=job.status,
            )

            document = await session.get(Document, job.document_id)
            if document is None:
                raise RuntimeError(f"Document '{job.document_id}' was not found")

            timings_ms: dict[str, float] = {}

            with track_stage(timings_ms, "preprocessing"):
                prepared = await run_in_threadpool(
                    prepare_text,
                    document.text,
                    document.source,
                    document.metadata_json,
                )

            max_tags = options.max_tags
            resolved_output_language = (
                resolve_output_language(options.output_language, prepared.language_profile)
                or options.output_language
            )

            if options.enable_rules:
                stage_now = utc_now()
                job.progress_json = complete_stage(job.progress_json, "preprocessing", stage_now, options)
                job.progress_json = start_stage(job.progress_json, "rule_hints", stage_now, options)
                await session.commit()

                with track_stage(timings_ms, "rule_hints"):
                    rule_hints = apply_rule_hints(
                        source=document.source,
                        metadata=document.metadata_json,
                        title_text=prepared.title_text,
                        metadata_terms=prepared.metadata_terms,
                        language_profile=prepared.language_profile,
                        output_language=resolved_output_language,
                    )
            else:
                rule_hints = RuleHints()

            categorization_started_at = utc_now()
            job.progress_json = complete_stage(
                job.progress_json,
                "rule_hints" if options.enable_rules else "preprocessing",
                categorization_started_at,
                options,
            )
            job.progress_json = start_stage(job.progress_json, "categorization", categorization_started_at, options)
            await session.commit()

            with track_stage(timings_ms, "categorization"):
                category_result = await run_in_threadpool(
                    services.categorizer.categorize,
                    prepared.categorization_chunks,
                    rule_hints.category_boosts,
                )

            tagging_started_at = utc_now()
            job.progress_json = complete_stage(job.progress_json, "categorization", tagging_started_at, options)
            job.progress_json = start_stage(job.progress_json, "tagging", tagging_started_at, options)
            await session.commit()

            with track_stage(timings_ms, "tagging"):
                extracted_tags = await run_in_threadpool(
                    services.tagger.extract_tags,
                    prepared.tag_extraction_chunks,
                    max_tags=max_tags,
                    language_profile=prepared.language_profile,
                    title_text=prepared.title_text,
                )
                combined_tags = merge_tag_candidates(
                    rule_hints.tags,
                    extracted_tags,
                    max_tags=max_tags * 2,
                )
                tags = reconcile_tag_candidates(
                    combined_tags,
                    max_tags=max_tags,
                    tagging_mode=options.tagging_mode,
                    existing_tags=options.existing_tags,
                    curated_tags=options.curated_tags,
                    output_language=resolved_output_language,
                    category_codes=[node.code for node in category_result.category_path],
                )

            tags_payload = [asdict(tag) for tag in tags]
            explanation = None
            signals = {
                "chunked": prepared.chunked,
                "content_type": prepared.content_type,
                "num_chunks": len(prepared.chunks),
                "source": document.source,
                "language": {
                    "dominant": prepared.language_profile.dominant_language,
                    "secondary": prepared.language_profile.secondary_language,
                    "mixed": prepared.language_profile.mixed_language,
                    "distribution": prepared.language_profile.distribution,
                },
                "pipeline": {
                    "content_type_hint": options.content_type_hint,
                    "content_type_hint_applied": False,
                    "tagging_mode": options.tagging_mode,
                    "output_language": resolved_output_language,
                    "enable_rules": options.enable_rules,
                    "llm_strategy": options.llm_strategy,
                },
                "rule_hints": {
                    "category_boosts": dict(rule_hints.category_boosts),
                    "matched_rules": list(rule_hints.matched_rules),
                    "tags": [asdict(tag) for tag in rule_hints.tags],
                },
                "classification": {
                    "top_1_score": category_result.effective_top_1_score,
                    "top_2_score": category_result.effective_top_2_score,
                    "confidence_gap": category_result.effective_confidence_gap,
                    "low_confidence": category_result.low_confidence,
                    "low_confidence_reasons": list(category_result.low_confidence_reasons),
                    "num_chunks_scored": category_result.num_chunks_scored or len(prepared.categorization_chunks),
                    "informative_chunk_indices": list(category_result.informative_chunk_indices),
                    "num_informative_chunks": len(category_result.informative_chunk_indices),
                    "category_path": [
                        {
                            "code": node.code,
                            "label": node.label,
                        }
                        for node in category_result.category_path
                    ],
                    "category_depth": category_result.category_depth,
                    "category_is_leaf": category_result.category_is_leaf,
                    "classification_trace": list(category_result.classification_trace),
                },
                "llm_postprocessed": False,
                "timings_ms": dict(timings_ms),
                "category_scores_top_k": category_result.top_k(3),
            }

            should_run_llm = False
            if services.enhancer is not None:
                if options.llm_strategy == "always":
                    should_run_llm = True
                elif options.llm_strategy == "low_confidence_only":
                    should_run_llm = category_result.low_confidence
                elif options.use_llm_postprocess:
                    should_run_llm = True

            db_write_stage_started_at = utc_now()
            job.progress_json = complete_stage(job.progress_json, "tagging", db_write_stage_started_at, options)

            if should_run_llm:
                job.progress_json = start_stage(job.progress_json, "llm_postprocess", db_write_stage_started_at, options)
                await session.commit()
                try:
                    with track_stage(timings_ms, "llm_postprocess"):
                        enhanced = await run_in_threadpool(
                            services.enhancer.enhance,
                            text=document.text,
                            category={
                                "code": category_result.category.code,
                                "label": category_result.category.label,
                                "score": category_result.score,
                            },
                            tags=tags_payload,
                            allowed_tags=[tag.model_dump() for tag in [*options.curated_tags, *options.existing_tags]],
                            output_language=resolved_output_language,
                        )
                        validated_tags = TypeAdapter(list[TagResponse]).validate_python(
                            enhanced.get("tags", tags_payload)
                        )
                        candidate_explanation = enhanced.get("explanation")
                        if candidate_explanation is not None and not isinstance(candidate_explanation, str):
                            raise TypeError("enhancer explanation must be a string or null")
                        tags_payload = _merge_llm_tag_metadata(validated_tags, tags_payload)
                        explanation = candidate_explanation
                        signals["llm_postprocessed"] = True
                        db_write_stage_started_at = utc_now()
                        job.progress_json = complete_stage(
                            job.progress_json,
                            "llm_postprocess",
                            db_write_stage_started_at,
                            options,
                        )
                except Exception:  # noqa: BLE001
                    signals["llm_postprocessed"] = False
                    signals["llm_postprocess_error"] = True
                    db_write_stage_started_at = utc_now()
                    job.progress_json = fail_stage(job.progress_json, "llm_postprocess", db_write_stage_started_at, options)
                    log_event(
                        logger,
                        "llm_postprocess_fallback",
                        job_id=job.id,
                        document_id=document.id,
                        status="fallback",
                    )
            elif options.use_llm_postprocess or options.llm_strategy != "disabled":
                job.progress_json = skip_stage(job.progress_json, "llm_postprocess", db_write_stage_started_at, options)

            job.progress_json = start_stage(job.progress_json, "db_write", db_write_stage_started_at, options)
            await session.commit()

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
                await session.flush()

            timings_ms["total"] = round((perf_counter() - total_started) * 1000, 3)
            result.signals_json = {
                **signals,
                "timings_ms": dict(timings_ms),
            }
            completed_at = utc_now()
            job.progress_json = complete_stage(job.progress_json, "db_write", completed_at, options)
            job.progress_json = complete_stage(job.progress_json, "completed", completed_at, options)
            job.status = "completed"
            job.finished_at = completed_at
            await session.commit()
            log_event(logger, "job_completed", job_id=job.id, document_id=document.id, status=job.status)
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            failed_job = await session.get(TaggingJob, job_id)
            if failed_job is None:
                return

            failed_job.status = "failed"
            failed_job.error_code = "processing_failed"
            failed_job.error_message = str(exc)
            failed_job.finished_at = utc_now()
            failed_options = TaggingOptions.model_validate(failed_job.options_json)
            current_stage = (
                (failed_job.progress_json or {}).get("current_stage")
                or "queued"
            )
            failed_job.progress_json = fail_stage(
                failed_job.progress_json or {},
                current_stage,
                failed_job.finished_at,
                failed_options,
            )
            await session.commit()
            log_event(
                logger,
                "job_failed",
                job_id=failed_job.id,
                document_id=failed_job.document_id,
                status=failed_job.status,
                error_message=str(exc),
            )
