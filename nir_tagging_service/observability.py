from __future__ import annotations

"""Structured logging and lightweight stage timing utilities."""

import json
import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


def get_logger(name: str, level: str) -> logging.Logger:
    """Create or reuse a plain JSON logger for the service."""

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    logger.setLevel(level.upper())
    return logger


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    """Emit a single structured JSON log event."""

    logger.log(logger.level or logging.INFO, json.dumps({"event": event, **fields}, ensure_ascii=False))


@contextmanager
def track_stage(timings_ms: dict[str, float], stage: str) -> Iterator[None]:
    """Measure stage duration and store it in milliseconds."""

    started = perf_counter()
    try:
        yield
    finally:
        timings_ms[stage] = round((perf_counter() - started) * 1000, 3)
