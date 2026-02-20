
import logging
import json
from typing import Callable, Optional, Tuple, Generator
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from src.database import User, AuditLog, get_db

logger = logging.getLogger(__name__)

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for centralized audit logging of MaaS API requests.
    Captures user identity, action, payload (filtered), and outcome.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only audit MaaS API
        if not request.url.path.startswith("/api/v1/maas"):
            return await call_next(request)

        # Skip login/register payloads for security/privacy
        sensitive_paths = ["/api/v1/maas/auth/login", "/api/v1/maas/auth/register", "/api/v1/maas/users/register"]
        is_sensitive = any(request.url.path.startswith(p) for p in sensitive_paths)

        payload = None
        # Capture payload for mutating methods
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not is_sensitive:
            try:
                # Capture body
                body = await request.body()
                if body:
                    try:
                        payload_json = json.loads(body)
                        # Basic filtering of sensitive keys
                        sensitive_keys = ["password", "token", "secret", "api_key", "pqc_key", "private_key"]
                        self._filter_sensitive_data(payload_json, sensitive_keys)
                        payload = json.dumps(payload_json)
                    except json.JSONDecodeError:
                        # Fallback for non-JSON or malformed JSON
                        payload = body.decode("utf-8", errors="replace")[:1000]
                
                # Re-wrap the request body for downstream consumers
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            except Exception as e:
                logger.error(f"AuditMiddleware: Failed to capture body: {e}")

        # Process the request
        response = await call_next(request)

        # Log to DB after request is processed
        try:
            self._log_audit(request, response, payload)
        except Exception as e:
            logger.error(f"AuditMiddleware: Failed to log audit: {e}")

        return response

    def _filter_sensitive_data(self, data: any, sensitive_keys: list):
        """Recursively redact sensitive keys from a dictionary or list."""
        if isinstance(data, dict):
            for key in list(data.keys()):
                if any(s in key.lower() for s in sensitive_keys):
                    data[key] = "********"
                else:
                    self._filter_sensitive_data(data[key], sensitive_keys)
        elif isinstance(data, list):
            for item in data:
                self._filter_sensitive_data(item, sensitive_keys)

    def _log_audit(self, request: Request, response: Response, payload: Optional[str]):
        db, generator = self._resolve_db(request)
        try:
            # Try to identify user
            user_id = None
            
            # 1. Try X-API-Key
            api_key = request.headers.get("X-API-Key")
            if api_key:
                user = db.query(User).filter(User.api_key == api_key).first()
                if user:
                    user_id = user.id
            
            # 2. Try Authorization Bearer
            if not user_id:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    from src.database import Session as UserSession
                    session = db.query(UserSession).filter(UserSession.token == token).first()
                    if session:
                        user_id = session.user_id

            # Create Audit Log entry
            audit_entry = AuditLog(
                user_id=user_id,
                action=f"{request.method} {request.url.path}",
                method=request.method,
                path=request.url.path,
                payload=payload,
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None
            )
            db.add(audit_entry)
            db.commit()
        finally:
            self._close_db(db, generator)

    def _resolve_db(self, request: Request) -> Tuple[object, Optional[Generator]]:
        """Resolve DB session from FastAPI app dependency overrides or default get_db."""
        provider = request.app.dependency_overrides.get(get_db, get_db)
        db_source = provider()
        if hasattr(db_source, "__next__"):
            generator = db_source
            db = next(generator)
            return db, generator
        return db_source, None

    def _close_db(self, db: object, generator: Optional[Generator]) -> None:
        """Close DB session properly."""
        if generator is not None:
            try:
                next(generator)
            except StopIteration:
                pass
            return
        close = getattr(db, "close", None)
        if callable(close):
            close()
