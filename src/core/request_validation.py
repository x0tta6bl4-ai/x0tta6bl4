"""
Request Validation Middleware

Provides security validation for incoming requests:
- Request size limits
- Content-Type validation
- Input sanitization
- Injection attack prevention
- Header validation
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for request validation."""

    # Size limits
    max_content_length: int = 10 * 1024 * 1024  # 10MB default
    max_header_size: int = 8 * 1024  # 8KB for headers
    max_url_length: int = 2048  # 2KB for URL

    # Content-Type validation
    allowed_content_types: Set[str] = field(
        default_factory=lambda: {
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
        }
    )

    # Methods that require body validation
    body_methods: Set[str] = field(default_factory=lambda: {"POST", "PUT", "PATCH"})

    # Paths to exclude from validation
    excluded_paths: List[str] = field(
        default_factory=lambda: [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]
    )

    # Enable specific validations
    validate_content_type: bool = True
    validate_content_length: bool = True
    validate_headers: bool = True
    sanitize_inputs: bool = True
    block_suspicious_patterns: bool = True


# Suspicious patterns for injection detection
SUSPICIOUS_PATTERNS = [
    # SQL injection
    r"(?i)(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b.*\b(from|into|table|database)\b)",
    r"(?i)(--|#|/\*|\*/|;)\s*(select|insert|update|delete|drop)",
    r"(?i)'\s*(or|and)\s*'",  # ' OR ' or ' AND ' patterns
    # NoSQL injection
    r"(?i)\$where|\$gt|\$lt|\$ne|\$regex",
    # Command injection
    r"[;&|`$]",
    r"(?i)(bash|sh|cmd|powershell)\s*[<>|&;]",
    # Path traversal
    r"\.\./|\.\.\\",
    r"(?i)(etc/passwd|etc/shadow|proc/self)",
    # XSS patterns
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",
    # LDAP injection - more specific pattern to avoid matching Accept: */*
    r"\)\s*\(\s*\w+\s*=",  # )(uid= pattern
    r"\*\)\s*\(",  # *)( pattern
]

# Compiled patterns for efficiency
COMPILED_PATTERNS = [re.compile(p) for p in SUSPICIOUS_PATTERNS]

# Blocked headers (security-sensitive)
BLOCKED_HEADERS = {
    "x-forwarded-host",  # Can be spoofed
    "x-original-url",
    "x-rewrite-url",
}

# Required security headers to check
SECURITY_HEADERS = {
    "Content-Type",
}


def is_suspicious(value: str) -> bool:
    """Check if value contains suspicious patterns."""
    if not value:
        return False

    for pattern in COMPILED_PATTERNS:
        if pattern.search(value):
            return True
    return False


def sanitize_string(value: str, max_length: int = 10000) -> str:
    """
    Sanitize a string value.

    - Truncate to max length
    - Remove null bytes
    - Normalize whitespace
    """
    if not value:
        return value

    # Truncate
    value = value[:max_length]

    # Replace null bytes with spaces so token boundaries are preserved.
    value = value.replace("\x00", " ")

    # Normalize excessive whitespace
    value = " ".join(value.split())

    return value


def sanitize_dict(
    data: Dict[str, Any], max_depth: int = 10, current_depth: int = 0
) -> Dict[str, Any]:
    """Recursively sanitize dictionary values."""
    if current_depth >= max_depth:
        return {}

    result = {}
    for key, value in data.items():
        # Sanitize key
        clean_key = sanitize_string(str(key), max_length=256)

        # Sanitize value based on type
        if isinstance(value, str):
            result[clean_key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[clean_key] = sanitize_dict(value, max_depth, current_depth + 1)
        elif isinstance(value, list):
            result[clean_key] = [
                (
                    sanitize_string(str(v))
                    if isinstance(v, str)
                    else (
                        sanitize_dict(v, max_depth, current_depth + 1)
                        if isinstance(v, dict)
                        else v
                    )
                )
                for v in value[:1000]  # Limit list size
            ]
        else:
            result[clean_key] = value

    return result


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for validating and sanitizing incoming requests.

    Features:
    - Content length validation
    - Content-Type validation
    - Header validation
    - Injection pattern detection
    - Input sanitization
    """

    def __init__(self, app, config: Optional[ValidationConfig] = None):
        super().__init__(app)
        self.config = config or ValidationConfig()
        logger.info(
            f"Request validation middleware initialized "
            f"(max_size={self.config.max_content_length}, "
            f"sanitize={self.config.sanitize_inputs})"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip validation for excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.config.excluded_paths):
            return await call_next(request)

        return await self._validate_and_process(request, call_next, path=path)

    async def _validate_and_process(
        self, request: Request, call_next, *, path: str
    ) -> Response:

        # Validate URL length
        if len(str(request.url)) > self.config.max_url_length:
            logger.warning(f"URL too long: {len(str(request.url))} bytes")
            return JSONResponse(status_code=414, content={"error": "URI Too Long"})

        # Validate Content-Length
        if self.config.validate_content_length:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    length = int(content_length)
                    if length > self.config.max_content_length:
                        logger.warning(f"Request too large: {length} bytes")
                        return JSONResponse(
                            status_code=413,
                            content={
                                "error": "Payload Too Large",
                                "max_size": self.config.max_content_length,
                            },
                        )
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Invalid Content-Length header"},
                    )

        # Validate Content-Type for body methods
        if self.config.validate_content_type:
            if request.method in self.config.body_methods:
                content_type = request.headers.get("content-type", "")
                # Extract base content type (without charset etc.)
                base_type = content_type.split(";")[0].strip().lower()

                if base_type and base_type not in self.config.allowed_content_types:
                    logger.warning(f"Invalid content type: {content_type}")
                    return JSONResponse(
                        status_code=415,
                        content={
                            "error": "Unsupported Media Type",
                            "allowed": list(self.config.allowed_content_types),
                        },
                    )

        # Validate headers
        if self.config.validate_headers:
            validation_error = self._validate_headers(request, path=path)
            if validation_error:
                return validation_error

        # Check for suspicious patterns in URL and query params
        if self.config.block_suspicious_patterns:
            # Check URL path
            if is_suspicious(request.url.path):
                logger.warning(f"Suspicious pattern in path: {request.url.path}")
                return JSONResponse(
                    status_code=400, content={"error": "Invalid request path"}
                )

            # Check query params
            for key, value in request.query_params.items():
                if is_suspicious(key) or is_suspicious(value):
                    logger.warning(f"Suspicious pattern in query: {key}={value}")
                    return JSONResponse(
                        status_code=400, content={"error": "Invalid query parameters"}
                    )

        return await call_next(request)

    def _validate_headers(
        self, request: Request, *, path: str = ""
    ) -> Optional[JSONResponse]:
        """Validate request headers."""
        total_header_size = 0
        is_html_page = path.endswith(".html") or path == "/"

        for name, value in request.headers.items():
            # Check header size
            header_size = len(name) + len(value)
            total_header_size += header_size

            if total_header_size > self.config.max_header_size:
                logger.warning(f"Headers too large: {total_header_size} bytes")
                return JSONResponse(
                    status_code=431,
                    content={"error": "Request Header Fields Too Large"},
                )

            # Check for blocked headers
            if name.lower() in BLOCKED_HEADERS:
                logger.warning(f"Blocked header: {name}")
                return JSONResponse(
                    status_code=400, content={"error": f"Header not allowed: {name}"}
                )

            # Check for suspicious patterns in headers
            if self.config.block_suspicious_patterns:
                # Skip suspicious-pattern validation for browser HTML pages and
                # known safe headers that commonly contain special characters.
                skip_headers = {
                    "user-agent",
                    "cookie",
                    "referer",
                    "sec-ch-ua",
                    "accept",
                    "sec-ch-ua-mobile",
                    "sec-ch-ua-platform",
                    "sec-fetch-dest",
                    "sec-fetch-mode",
                    "sec-fetch-site",
                    "sec-fetch-user",
                    "upgrade-insecure-requests",
                    "x-api-key",
                    "authorization",
                    "connection",
                    "accept-encoding",
                    "accept-language",
                }

                header_name = name.lower()
                skip_header_scan = (
                    is_html_page
                    or header_name in skip_headers
                    or header_name.startswith("sec-")
                )
                if not skip_header_scan and is_suspicious(value):
                    logger.warning(
                        f"🛡️ Suspicious pattern detected in header '{name}': {value}"
                    )
                    return JSONResponse(
                        status_code=400, content={"error": "Invalid header value"}
                    )

        return None


class JSONSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware specifically for sanitizing JSON request bodies.

    This middleware reads and sanitizes JSON bodies before they reach
    the application.

    Note: This middleware buffers the entire request body, so it should
    only be used when necessary and with appropriate size limits.
    """

    def __init__(
        self, app, max_body_size: int = 1024 * 1024, max_depth: int = 10  # 1MB
    ):
        super().__init__(app)
        self.max_body_size = max_body_size
        self.max_depth = max_depth

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only process JSON requests
        content_type = request.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return await call_next(request)

        # Only process methods with bodies
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        try:
            # Read body
            body = await request.body()

            if len(body) > self.max_body_size:
                return JSONResponse(
                    status_code=413, content={"error": "JSON body too large"}
                )

            if body:
                import json

                try:
                    data = json.loads(body)
                    if isinstance(data, dict):
                        # Sanitize the data
                        sanitized = sanitize_dict(data, max_depth=self.max_depth)
                        # Note: We can't easily replace the body in Starlette
                        # So we just validate here
                        for key, value in sanitized.items():
                            if isinstance(value, str) and is_suspicious(value):
                                logger.warning(
                                    f"Suspicious content in JSON field: {key}"
                                )
                                return JSONResponse(
                                    status_code=400,
                                    content={"error": f"Invalid value in field: {key}"},
                                )
                except json.JSONDecodeError:
                    return JSONResponse(
                        status_code=400, content={"error": "Invalid JSON"}
                    )

        except Exception as e:
            logger.error(f"Error processing request body: {e}")

        return await call_next(request)


# Default configuration instance
default_config = ValidationConfig()


__all__ = [
    "RequestValidationMiddleware",
    "JSONSanitizationMiddleware",
    "ValidationConfig",
    "is_suspicious",
    "sanitize_string",
    "sanitize_dict",
    "default_config",
]
