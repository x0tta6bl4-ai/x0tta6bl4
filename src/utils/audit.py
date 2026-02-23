from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session
from src.database import AuditLog
import json
import logging

logger = logging.getLogger(__name__)

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
        # 1. DB Log
        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            method=request.method if request else "INTERNAL",
            path=request.url.path if request else "INTERNAL",
            payload=json.dumps(payload) if payload else None,
            status_code=status_code,
            ip_address=request.client.host if request and request.client else "unknown"
        )
        db.add(log_entry)
        # Use flush() instead of commit() to preserve caller's transaction
        # The caller is responsible for committing the transaction
        db.flush()
        
        # 2. Mirror to logger
        logger.info(
            "AUDIT %s user_id=%s method=%s path=%s ip=%s status=%s",
            action, user_id, request.method if request else None, 
            request.url.path if request else None, 
            log_entry.ip_address, status_code
        )
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")
        # Don't raise, we don't want to break the main flow if auditing fails
        # Don't rollback - let the caller handle their own transaction

def _audit(db: Session, request: Request, action: str, **kwargs):
    """Shorthand for record_audit_log."""
    return record_audit_log(db, request, action, **kwargs)
