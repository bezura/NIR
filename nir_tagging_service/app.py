from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial

from fastapi import FastAPI

from nir_tagging_service.api import create_api_router
from nir_tagging_service.categorization import (
    EmbeddingCategoryClassifier,
    SentenceTransformerEmbedder,
)
from nir_tagging_service.config import Settings, get_settings
from nir_tagging_service.db.models import Base
from nir_tagging_service.db.session import create_engine, create_session_factory
from nir_tagging_service.embeddings import SharedSentenceTransformerProvider
from nir_tagging_service.job_service import process_job
from nir_tagging_service.llm_enhancement import OpenAICompatibleEnhancer
from nir_tagging_service.observability import get_logger
from nir_tagging_service.tag_extraction import KeyBERTKeywordExtractor, KeywordTagger


@dataclass(frozen=True, slots=True)
class PipelineServices:
    categorizer: object
    tagger: object
    enhancer: object | None = None


def build_default_pipeline_services(settings: Settings) -> PipelineServices:
    embedding_provider = SharedSentenceTransformerProvider(settings.embedding_model_name)
    embedder = SentenceTransformerEmbedder(embedding_provider)
    enhancer = None

    if settings.openai_base_url and settings.openai_api_key and settings.openai_model:
        enhancer = OpenAICompatibleEnhancer(
            api_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            folder_id=settings.openai_project,
            timeout_seconds=settings.openai_timeout_seconds,
        )

    return PipelineServices(
        categorizer=EmbeddingCategoryClassifier(embedder=embedder),
        tagger=KeywordTagger(extractor=KeyBERTKeywordExtractor(embedding_provider)),
        enhancer=enhancer,
    )


def create_app(
    settings: Settings | None = None,
    pipeline_services: PipelineServices | None = None,
) -> FastAPI:
    current_settings = settings or get_settings()
    engine = create_engine(current_settings)
    session_factory = create_session_factory(current_settings, engine=engine)
    services = pipeline_services or build_default_pipeline_services(current_settings)
    logger = get_logger("nir_tagging_service.pipeline", current_settings.log_level)

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
    app.state.logger = logger
    app.state.process_job = partial(
        process_job,
        session_factory=session_factory,
        services=services,
        logger=logger,
    )
    app.include_router(create_api_router(current_settings))
    return app


app = create_app()
