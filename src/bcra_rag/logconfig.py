from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(
    *,
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handlers: list[logging.Handler] = []
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    handlers.append(stream)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8", delay=True)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    logger = logging.getLogger("bcra_rag")
    logger.setLevel(level)
    logger.propagate = False
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
        existing.close()
    for handler in handlers:
        logger.addHandler(handler)
