"""Structured logging via structlog.

Console renderer in development (pretty, colored), JSON in production (one event
per line, ready for ingestion). Every log line carries the request-scoped
``request_id`` once :func:`bind_request_id` is called by the middleware, so a
single request can be traced across the whole application from its logs.
"""

from __future__ import annotations

import logging
import sys
from typing import cast

import structlog
from opentelemetry import trace
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.config import settings


def _add_trace_correlation(
    _logger: object, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Bind the active trace/span id so a log line can be pivoted to its trace."""
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def configure_logging() -> None:
    """Configure structlog + stdlib logging. Call once on startup."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_trace_correlation,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy) through the same level.
    logging.basicConfig(level=level, handlers=[], force=True)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))


def bind_request_id(request_id: str) -> None:
    bind_contextvars(request_id=request_id)


def clear_request_context() -> None:
    clear_contextvars()


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
