
import logging
import time
from typing import Callable, Generator, Optional, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.database import User, get_db

logger = logging.getLogger(__name__)

class MeteringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Check if it's a MaaS API call
        if request.url.path.startswith("/api/v1/maas") and request.url.path not in ["/api/v1/maas/register", "/api/v1/maas/login"]:
            # Extract API Key from header
            api_key = request.headers.get("X-API-Key")
            if api_key:
                try:
                    self._update_usage(request, api_key)
                except Exception as e:
                    logger.error(f"Failed to update usage stats: {e}")

        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    def _resolve_db(self, request: Request) -> Tuple[object, Optional[Generator]]:
        """
        Resolve DB dependency the same way routes do, including test overrides.
        """
        provider = request.app.dependency_overrides.get(get_db, get_db)
        db_source = provider()
        if hasattr(db_source, "__next__"):
            generator = db_source
            db = next(generator)
            return db, generator
        return db_source, None

    @staticmethod
    def _close_db(db: object, generator: Optional[Generator]) -> None:
        if generator is not None:
            try:
                next(generator)
            except StopIteration:
                pass
            return

        close = getattr(db, "close", None)
        if callable(close):
            close()

    def _update_usage(self, request: Request, api_key: str) -> None:
        db, generator = self._resolve_db(request)
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            if user:
                user.requests_count = (user.requests_count or 0) + 1
                try:
                    db.commit()
                except Exception:
                    rollback = getattr(db, "rollback", None)
                    if callable(rollback):
                        rollback()
                    raise
        finally:
            self._close_db(db, generator)
