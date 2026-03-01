"""Unified API error responses for FastAPI applications."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


def resolve_trace_id(request: Request) -> str:
    """Resolve trace id from headers/state, falling back to generated UUID."""
    header_trace = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID")
    if header_trace and header_trace.strip():
        return header_trace.strip()

    state_trace = getattr(request.state, "trace_id", None)
    if isinstance(state_trace, str) and state_trace.strip():
        return state_trace.strip()

    generated = uuid.uuid4().hex
    request.state.trace_id = generated
    return generated


def build_error_payload(*, detail: Any, code: str, trace_id: str) -> dict[str, Any]:
    """Build unified API error payload."""
    return {
        "status": "error",
        "detail": detail,
        "code": code,
        "trace_id": trace_id,
    }


def _http_error_code(status_code: int, detail: Any) -> str:
    if isinstance(detail, dict):
        explicit_code = detail.get("code")
        if explicit_code:
            return str(explicit_code)
    return f"HTTP_{status_code}"


def register_api_error_handlers(app: FastAPI) -> None:
    """Register unified error handlers on a FastAPI app."""

    @app.middleware("http")
    async def _trace_id_response_middleware(request: Request, call_next):
        trace_id = resolve_trace_id(request)
        response = await call_next(request)
        response.headers.setdefault("X-Trace-ID", trace_id)
        return response

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        trace_id = resolve_trace_id(request)
        payload = build_error_payload(
            detail=exc.errors(),
            code="VALIDATION_ERROR",
            trace_id=trace_id,
        )
        return JSONResponse(
            status_code=422,
            content=payload,
            headers={"X-Trace-ID": trace_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        trace_id = resolve_trace_id(request)
        payload = build_error_payload(
            detail=exc.detail,
            code=_http_error_code(exc.status_code, exc.detail),
            trace_id=trace_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            headers={"X-Trace-ID": trace_id},
        )

    @app.exception_handler(Exception)
    async def _unhandled_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        trace_id = resolve_trace_id(request)
        logger.error("Unhandled API exception trace_id=%s: %s", trace_id, exc, exc_info=True)
        payload = build_error_payload(
            detail="Internal server error",
            code="INTERNAL_ERROR",
            trace_id=trace_id,
        )
        return JSONResponse(
            status_code=500,
            content=payload,
            headers={"X-Trace-ID": trace_id},
        )
