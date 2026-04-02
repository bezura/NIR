from __future__ import annotations

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
    return request.app.state.settings


def get_session_factory(request: Request) -> SessionFactory:
    return request.app.state.session_factory


def get_pipeline_services(request: Request) -> PipelineServices:
    return request.app.state.pipeline_services


def get_logger(request: Request) -> Logger:
    return request.app.state.logger


def get_process_job(request: Request) -> ProcessJobCallable:
    return request.app.state.process_job


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]
PipelineServicesDep = Annotated[PipelineServices, Depends(get_pipeline_services)]
LoggerDep = Annotated[Logger, Depends(get_logger)]
ProcessJobDep = Annotated[ProcessJobCallable, Depends(get_process_job)]
