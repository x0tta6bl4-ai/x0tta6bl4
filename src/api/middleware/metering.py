
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from src.database import SessionLocal, User

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
                    self._update_usage(api_key)
                except Exception as e:
                    logger.error(f"Failed to update usage stats: {e}")

        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    def _update_usage(self, api_key: str):
        # Create a new DB session for logging (async safe-ish)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            if user:
                user.requests_count += 1
                db.commit()
        finally:
            db.close()
