"""
Legacy MaaS compatibility middleware.

Provides FastAPI middleware for the historical `/api/v1/maas` namespace:
- Request/response logging
- Error handling and standardization
- Request ID tracking
- Performance metrics
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error Response Models
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    request_id: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None


class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    field: str
    message: str
    value: Optional[Any] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response with field details."""
    error: str = "validation_error"
    message: str = "Request validation failed"
    request_id: str
    timestamp: str
    details: List[ValidationErrorDetail]


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class MaaSError(Exception):
    """Base exception for MaaS API."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "internal_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(MaaSError):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} '{identifier}' not found",
            error_code="not_found",
            status_code=404,
            details={"resource": resource, "identifier": identifier},
        )


class UnauthorizedError(MaaSError):
    """Authentication required."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="unauthorized",
            status_code=401,
        )


class ForbiddenError(MaaSError):
    """Access denied."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="forbidden",
            status_code=403,
        )


class ValidationError(MaaSError):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        field_errors: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            message=message,
            error_code="validation_error",
            status_code=422,
            details={"field_errors": field_errors or []},
        )


class RateLimitError(MaaSError):
    """Rate limit exceeded."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message="Rate limit exceeded",
            error_code="rate_limit_exceeded",
            status_code=429,
            details={"retry_after": retry_after},
        )


class BillingError(MaaSError):
    """Billing-related error."""
    
    def __init__(self, message: str, plan_required: Optional[str] = None):
        details = {}
        if plan_required:
            details["plan_required"] = plan_required
        super().__init__(
            message=message,
            error_code="billing_error",
            status_code=402,
            details=details,
        )


class MeshError(MaaSError):
    """Mesh operation error."""
    
    def __init__(self, message: str, mesh_id: Optional[str] = None):
        details = {}
        if mesh_id:
            details["mesh_id"] = mesh_id
        super().__init__(
            message=message,
            error_code="mesh_error",
            status_code=400,
            details=details,
        )


# ---------------------------------------------------------------------------
# Request Context
# ---------------------------------------------------------------------------

@dataclass
class RequestContext:
    """Context for a single request."""
    
    request_id: str
    start_time: float
    method: str
    path: str
    client_ip: Optional[str] = None
    user_id: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "client_ip": self.client_ip,
            "user_id": self.user_id,
            "duration_ms": round((time.time() - self.start_time) * 1000, 2),
        }


# Thread-local request context
_request_context: Optional[RequestContext] = None


def get_request_context() -> Optional[RequestContext]:
    """Get the current request context."""
    return _request_context


def set_request_context(ctx: Optional[RequestContext]) -> None:
    """Set the current request context."""
    global _request_context
    _request_context = ctx


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class MaaSMiddleware(BaseHTTPMiddleware):
    """
    MaaS API Middleware.
    
    Features:
    - Request ID generation and tracking
    - Request/response logging
    - Error handling and standardization
    - Performance metrics
    """
    
    def __init__(
        self,
        app,
        log_requests: bool = True,
        log_responses: bool = True,
        log_request_body: bool = False,
        log_response_body: bool = False,
        exclude_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/ready"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through middleware."""
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Create request context
        ctx = RequestContext(
            request_id=request_id,
            start_time=time.time(),
            method=request.method,
            path=request.url.path,
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )
        set_request_context(ctx)
        
        # Log request
        if self.log_requests:
            await self._log_request(request, ctx)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Update context with user info if available
            # (would be set by auth middleware)
            
            # Log response
            if self.log_responses:
                self._log_response(response, ctx)
            
            # Add request ID to response
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except MaaSError as e:
            # Handle MaaS errors
            return self._handle_maas_error(e, ctx)
            
        except Exception as e:
            # Handle unexpected errors
            return self._handle_unexpected_error(e, ctx)
        
        finally:
            set_request_context(None)
    
    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP from request."""
        # Check X-Forwarded-For header first
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client
        if request.client:
            return request.client.host
        
        return None
    
    async def _log_request(self, request: Request, ctx: RequestContext) -> None:
        """Log incoming request."""
        log_data = {
            "event": "request",
            "request_id": ctx.request_id,
            "method": ctx.method,
            "path": ctx.path,
            "client_ip": ctx.client_ip,
            "user_agent": ctx.user_agent,
        }
        
        if self.log_request_body and request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                log_data["body_size"] = len(body)
            except Exception:
                pass
        
        logger.info(f"Request: {ctx.method} {ctx.path}", extra=log_data)
    
    def _log_response(self, response: Response, ctx: RequestContext) -> None:
        """Log outgoing response."""
        duration_ms = round((time.time() - ctx.start_time) * 1000, 2)
        
        log_data = {
            "event": "response",
            "request_id": ctx.request_id,
            "method": ctx.method,
            "path": ctx.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        
        # Log level based on status code
        if response.status_code >= 500:
            logger.error(f"Response: {response.status_code}", extra=log_data)
        elif response.status_code >= 400:
            logger.warning(f"Response: {response.status_code}", extra=log_data)
        else:
            logger.info(f"Response: {response.status_code}", extra=log_data)
    
    def _handle_maas_error(self, error: MaaSError, ctx: RequestContext) -> JSONResponse:
        """Handle MaaS-specific errors."""
        duration_ms = round((time.time() - ctx.start_time) * 1000, 2)
        
        logger.warning(
            f"MaaSError: {error.error_code} - {error.message}",
            extra={
                "request_id": ctx.request_id,
                "error_code": error.error_code,
                "status_code": error.status_code,
                "details": error.details,
                "duration_ms": duration_ms,
            },
        )
        
        response = ErrorResponse(
            error=error.error_code,
            message=error.message,
            request_id=ctx.request_id,
            timestamp=datetime.utcnow().isoformat(),
            details=error.details,
        )
        
        return JSONResponse(
            status_code=error.status_code,
            content=response.model_dump(),
        )
    
    def _handle_unexpected_error(self, error: Exception, ctx: RequestContext) -> JSONResponse:
        """Handle unexpected errors."""
        duration_ms = round((time.time() - ctx.start_time) * 1000, 2)
        
        logger.exception(
            f"Unexpected error: {type(error).__name__}: {error}",
            extra={
                "request_id": ctx.request_id,
                "error_type": type(error).__name__,
                "duration_ms": duration_ms,
            },
        )
        
        response = ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            request_id=ctx.request_id,
            timestamp=datetime.utcnow().isoformat(),
        )
        
        return JSONResponse(
            status_code=500,
            content=response.model_dump(),
        )


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

async def maas_exception_handler(request: Request, exc: MaaSError) -> JSONResponse:
    """FastAPI exception handler for MaaS errors."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    response = ErrorResponse(
        error=exc.error_code,
        message=exc.message,
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
        details=exc.details,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI exception handler for generic errors."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    logger.exception(f"Unhandled exception: {exc}")
    
    response = ErrorResponse(
        error="internal_error",
        message="An unexpected error occurred",
        request_id=request_id,
        timestamp=datetime.utcnow().isoformat(),
    )
    
    return JSONResponse(
        status_code=500,
        content=response.model_dump(),
    )


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def create_error_response(
    error: str,
    message: str,
    request_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a standard error response dictionary."""
    return {
        "error": error,
        "message": message,
        "request_id": request_id or str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "details": details,
    }


__all__ = [
    # Models
    "ErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    # Exceptions
    "MaaSError",
    "NotFoundError",
    "UnauthorizedError",
    "ForbiddenError",
    "ValidationError",
    "RateLimitError",
    "BillingError",
    "MeshError",
    # Middleware
    "MaaSMiddleware",
    "RequestContext",
    "get_request_context",
    "set_request_context",
    # Handlers
    "maas_exception_handler",
    "generic_exception_handler",
    # Utilities
    "create_error_response",
]

