from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from nir_tagging_service.api import create_api_router
from nir_tagging_service.bootstrap import PipelineServices, build_default_pipeline_services
from nir_tagging_service.config import Settings, get_settings
from nir_tagging_service.db.models import Base
from nir_tagging_service.db.session import create_engine, create_session_factory
from nir_tagging_service.observability import get_logger
from nir_tagging_service.pipeline import process_job


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
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield

    async def process_job_runner(job_id: str) -> None:
        await process_job(
            job_id=job_id,
            session_factory=session_factory,
            services=services,
            logger=logger,
        )

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
    app.state.process_job = process_job_runner
    app.include_router(create_api_router(current_settings))
    return app


app = create_app()
