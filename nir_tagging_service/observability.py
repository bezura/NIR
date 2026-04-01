from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Iterator


def get_logger(name: str, level: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    logger.setLevel(level.upper())
    return logger


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    logger.log(logger.level or logging.INFO, json.dumps({"event": event, **fields}, ensure_ascii=False))


@contextmanager
def track_stage(timings_ms: dict[str, float], stage: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        timings_ms[stage] = round((perf_counter() - started) * 1000, 3)
