"""Exception handlers: turn exceptions into RFC 9457 problem+json responses.

This is the *only* place that maps errors to HTTP. Services raise domain
exceptions (``app/exceptions.py``); handlers here render them consistently so
every client, in every situation, gets the same predictable error shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.exceptions import AppError
from app.schemas.common import Problem

if TYPE_CHECKING:
    from fastapi import FastAPI

log = get_logger(__name__)
PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem_response(problem: Problem, *, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        problem = Problem(
            title=exc.title,
            status=exc.status_code,
            detail=exc.detail,
            code=exc.code,
            instance=request.url.path,
            request_id=_request_id(request),
        )
        # Errors may carry response headers (e.g. Retry-After on a 429).
        headers = exc.extra.get("headers")
        return _problem_response(problem, headers=headers if isinstance(headers, dict) else None)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        problem = Problem(
            title="Validation Failed",
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more fields are invalid.",
            code="validation_error",
            instance=request.url.path,
            request_id=_request_id(request),
            # jsonable_encoder makes ValueErrors from custom validators safe to
            # serialize — without it a custom-validator error degrades into a 500.
            errors=jsonable_encoder(exc.errors()),
        )
        return _problem_response(problem)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals. Log the real cause, return an opaque 500.
        log.exception("unhandled_exception", path=request.url.path)
        problem = Problem(
            title="Internal Server Error",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
            code="internal_error",
            instance=request.url.path,
            request_id=_request_id(request),
        )
        return _problem_response(problem)
