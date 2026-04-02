from __future__ import annotations

from collections.abc import Callable
from logging import Logger
from typing import Annotated, Any

from fastapi import Depends, Request

from nir_tagging_service.config import Settings


SessionFactory = Callable[[], Any]
ProcessJobCallable = Callable[[str], None]


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_factory(request: Request) -> SessionFactory:
    return request.app.state.session_factory


def get_pipeline_services(request: Request) -> Any:
    return request.app.state.pipeline_services


def get_logger(request: Request) -> Logger:
    return request.app.state.logger


def get_process_job(request: Request) -> ProcessJobCallable:
    return request.app.state.process_job


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionFactoryDep = Annotated[SessionFactory, Depends(get_session_factory)]
PipelineServicesDep = Annotated[Any, Depends(get_pipeline_services)]
LoggerDep = Annotated[Logger, Depends(get_logger)]
ProcessJobDep = Annotated[ProcessJobCallable, Depends(get_process_job)]
