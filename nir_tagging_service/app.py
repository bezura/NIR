from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter

from nir_tagging_service.categorization import (
    EmbeddingCategoryClassifier,
    SentenceTransformerEmbedder,
)
from nir_tagging_service.config import Settings, get_settings
from nir_tagging_service.db.models import Base, Document, TaggingJob, TaggingResult, utc_now
from nir_tagging_service.db.session import create_engine, create_session_factory
from nir_tagging_service.llm_enhancement import OpenAICompatibleEnhancer
from nir_tagging_service.preprocessing import prepare_text
from nir_tagging_service.schemas import (
    CreateTaggingJobRequest,
    CreateTaggingJobResponse,
    ErrorPayload,
    HealthResponse,
    JobResultResponse,
    JobStatusResponse,
    TagResponse,
)
from nir_tagging_service.tag_extraction import KeyBERTKeywordExtractor, KeywordTagger


@dataclass(frozen=True, slots=True)
class PipelineServices:
    categorizer: object
    tagger: object
    enhancer: object | None = None


def build_default_pipeline_services(settings: Settings) -> PipelineServices:
    embedder = SentenceTransformerEmbedder(settings.embedding_model_name)
    enhancer = None

    if settings.llm_api_url and settings.llm_api_key and settings.llm_model:
        enhancer = OpenAICompatibleEnhancer(
            api_url=settings.llm_api_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    return PipelineServices(
        categorizer=EmbeddingCategoryClassifier(embedder=embedder),
        tagger=KeywordTagger(extractor=KeyBERTKeywordExtractor(settings.embedding_model_name)),
        enhancer=enhancer,
    )


def error_response(status_code: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    payload = ErrorPayload(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content={"error": payload.model_dump()})


def create_app(
    settings: Settings | None = None,
    pipeline_services: PipelineServices | None = None,
) -> FastAPI:
    current_settings = settings or get_settings()
    engine = create_engine(current_settings)
    session_factory = create_session_factory(current_settings, engine=engine)
    services = pipeline_services or build_default_pipeline_services(current_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(
        title=current_settings.app_name,
        lifespan=lifespan,
        docs_url=f"{current_settings.api_prefix}/docs",
        redoc_url=f"{current_settings.api_prefix}/redoc",
        openapi_url=f"{current_settings.api_prefix}/openapi.json",
    )
    app.state.settings = current_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.pipeline_services = services

    def process_job(job_id: str) -> None:
        with session_factory() as session:
            job = session.get(TaggingJob, job_id)
            if job is None:
                return

            try:
                job.status = "processing"
                job.started_at = utc_now()
                session.commit()

                document = session.get(Document, job.document_id)
                prepared = prepare_text(document.text, document.source)
                max_tags = job.options_json.get("max_tags", 5)
                category_result = services.categorizer.categorize(prepared.categorization_chunks)
                tags = services.tagger.extract_tags(prepared.tag_extraction_chunks, max_tags=max_tags)
                tags_payload = [asdict(tag) for tag in tags]
                explanation = None
                signals = {
                    "chunked": prepared.chunked,
                    "content_type": prepared.content_type,
                    "source": document.source,
                    "llm_postprocessed": False,
                }

                if job.options_json.get("use_llm_postprocess") and services.enhancer is not None:
                    try:
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
                session.add(result)
                job.status = "completed"
                job.finished_at = utc_now()
                session.commit()
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

    app.state.process_job = process_job

    @app.get("/health", response_model=HealthResponse)
    def healthcheck() -> HealthResponse:
        return HealthResponse(status="ok", service=current_settings.app_name)

    @app.post(
        f"{current_settings.api_prefix}/jobs",
        response_model=CreateTaggingJobResponse,
        status_code=202,
    )
    def create_job(
        request: CreateTaggingJobRequest,
        background_tasks: BackgroundTasks,
    ) -> CreateTaggingJobResponse:
        with session_factory() as session:
            document = Document(
                source=request.source,
                text=request.text,
                metadata_json=request.metadata,
            )
            job = TaggingJob(
                document=document,
                status="queued",
                options_json=request.options.model_dump(),
            )
            session.add_all([document, job])
            session.commit()
            session.refresh(document)
            session.refresh(job)

        background_tasks.add_task(process_job, job.id)

        return CreateTaggingJobResponse(
            job_id=job.id,
            status=job.status,
            document_id=document.id,
            status_url=f"{current_settings.api_prefix}/jobs/{job.id}",
            result_url=f"{current_settings.api_prefix}/jobs/{job.id}/result",
        )

    @app.get(f"{current_settings.api_prefix}/jobs/{{job_id}}", response_model=JobStatusResponse)
    def get_job_status(job_id: str) -> JobStatusResponse | JSONResponse:
        with session_factory() as session:
            job = session.get(TaggingJob, job_id)
            if job is None:
                return error_response(404, "job_not_found", f"Job '{job_id}' was not found")

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

    @app.get(f"{current_settings.api_prefix}/jobs/{{job_id}}/result", response_model=JobResultResponse)
    def get_job_result(job_id: str) -> JobResultResponse | JSONResponse:
        with session_factory() as session:
            job = session.get(TaggingJob, job_id)
            if job is None:
                return error_response(404, "job_not_found", f"Job '{job_id}' was not found")

            if job.status == "failed":
                return error_response(
                    409,
                    job.error_code or "processing_failed",
                    job.error_message or "The job failed during processing",
                )

            if job.status != "completed":
                return error_response(409, "result_not_ready", f"Job '{job_id}' is still {job.status}")

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

    return app


app = create_app()
