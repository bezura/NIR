from __future__ import annotations

"""FastAPI dependency helpers backed by application state."""

from collections.abc import Awaitable, Callable
from logging import Logger
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nir_tagging_service.bootstrap import PipelineServices
from nir_tagging_service.config import Settings


SessionFactory = async_sessionmaker[AsyncSession]
ProcessJobCallable = Callable[[str], Awaitable[None]]


def get_settings(request: Request) -> Settings:
    """Expose the cached application settings from app state."""

    return request.app.state.settings


def get_session_factory(request: Request) -> SessionFactory:
    """Expose the async SQLAlchemy session factory from app state."""

    return request.app.state.session_factory


def get_pipeline_services(request: Request) -> PipelineServices:
    """Expose lazily initialized pipeline services from app state."""

    return request.app.state.pipeline_services


def get_logger(request: Request) -> Logger:
    """Expose the configured structured logger from app state."""

    return request.app.state.logger


def get_process_job(request: Request) -> ProcessJobCallable:
    """Expose the background job processor callable from app state."""

    return request.app.state.process_job


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]
PipelineServicesDep = Annotated[PipelineServices, Depends(get_pipeline_services)]
LoggerDep = Annotated[Logger, Depends(get_logger)]
ProcessJobDep = Annotated[ProcessJobCallable, Depends(get_process_job)]
