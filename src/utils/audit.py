import json
import logging
import re
from typing import Any
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from src.core.logging_config import RequestIdContextVar
from src.database import AuditLog

logger = logging.getLogger(__name__)

_REDACTED_VALUE = "********"
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "private_key",
    "pqc_key",
    "authorization",
    "access_token",
    "refresh_token",
    "session_token",
    "credential",
    "passphrase",
}

_INLINE_SECRET_PATTERNS = [
    (
        re.compile(r"(?i)\b(authorization)\s*[:=]\s*(bearer|basic)\s+([^\s,;]+)"),
        r"\1: \2 ********",
    ),
    (
        re.compile(r"(?i)\b(token|password|secret|api[_-]?key|private[_-]?key)\s*[:=]\s*([^\s,;]+)"),
        r"\1=********",
    ),
]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEYS)


def _sanitize_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in _INLINE_SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_payload_value(value: Any, *, parent_key: Optional[str] = None) -> Any:
    if parent_key and _is_sensitive_key(parent_key):
        return _REDACTED_VALUE

    if isinstance(value, dict):
        return {
            key: _sanitize_payload_value(child, parent_key=str(key))
            for key, child in value.items()
        }

    if isinstance(value, list):
        return [_sanitize_payload_value(item, parent_key=parent_key) for item in value]

    if isinstance(value, tuple):
        return [_sanitize_payload_value(item, parent_key=parent_key) for item in value]

    if isinstance(value, str):
        return _sanitize_text(value)

    return value


def _serialize_sanitized_payload(payload: Any) -> Optional[str]:
    if payload is None:
        return None
    sanitized_payload = _sanitize_payload_value(payload)
    return json.dumps(sanitized_payload, default=str, ensure_ascii=False)


def _resolve_trace_id(request: Optional[Request]) -> Optional[str]:
    """Resolve trace/request id for audit events, including background tasks."""
    if request is not None:
        state_trace = getattr(request.state, "trace_id", None)
        if isinstance(state_trace, str) and state_trace.strip():
            return state_trace.strip()

        for header_name in ("X-Trace-ID", "X-Request-ID", "X-Correlation-ID"):
            header_value = request.headers.get(header_name)
            if header_value and header_value.strip():
                return header_value.strip()

    context_trace = RequestIdContextVar.get()
    if context_trace and context_trace.strip():
        return context_trace.strip()

    try:
        # Lazy import avoids hard runtime dependency during module import.
        from src.core.tracing_middleware import get_correlation_id

        correlation_id = get_correlation_id()
        if correlation_id and correlation_id.strip():
            return correlation_id.strip()
    except Exception:
        pass

    return None


def record_audit_log(
    db: Session,
    request: Optional[Request],
    action: str,
    user_id: str = None,
    payload: dict = None,
    status_code: int = None
):
    """
    Record an action in the database-backed Audit Log.
    Also mirrors to standard logging for redundancy.
    
    Args:
        db: Database session
        request: FastAPI request object (can be None for background tasks)
        action: Action name for the audit log
        user_id: User ID performing the action
        payload: Optional payload data
        status_code: HTTP status code
    """
    try:
        trace_id = _resolve_trace_id(request)

        # 1. DB Log
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            method=request.method if request else "INTERNAL",
            path=request.url.path if request else "INTERNAL",
            payload=_serialize_sanitized_payload(payload) if payload else None,
            status_code=status_code,
            ip_address=request.client.host if request and request.client else "unknown"
        )
        db.add(log_entry)
        # Use flush() instead of commit() to preserve caller's transaction
        # The caller is responsible for committing the transaction
        db.flush()

        # 2. Mirror to logger
        extra_fields = {}
        if trace_id:
            extra_fields = {"request_id": trace_id, "trace_id": trace_id}

        logger.info(
            "AUDIT %s user_id=%s method=%s path=%s ip=%s status=%s trace_id=%s",
            action,
            user_id,
            request.method if request else None,
            request.url.path if request else None,
            log_entry.ip_address,
            status_code,
            trace_id,
            extra=extra_fields,
        )
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        # Don't raise, we don't want to break the main flow if auditing fails
        # Don't rollback - let the caller handle their own transaction

def _audit(db: Session, request: Request, action: str, **kwargs):
    """Shorthand for record_audit_log."""
    return record_audit_log(db, request, action, **kwargs)
