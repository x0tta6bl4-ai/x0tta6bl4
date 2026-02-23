
import logging
import os
import threading
import time
from typing import Callable, Dict, Generator, Optional, Tuple

from fastapi import Request, Response
from sqlalchemy import func
from starlette.middleware.base import BaseHTTPMiddleware

from src.database import User, get_db

logger = logging.getLogger(__name__)

class MeteringMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._batch_size = max(
            1,
            int(os.getenv("MAAS_METERING_BATCH_SIZE", "1")),
        )
        self._flush_interval_seconds = max(
            0.0,
            float(os.getenv("MAAS_METERING_FLUSH_INTERVAL_SECONDS", "5")),
        )
        self._usage_buffer: Dict[str, int] = {}
        self._buffer_lock = threading.Lock()
        self._last_flush_mono = time.monotonic()

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
        if self._batch_size <= 1:
            self._flush_usage_batch(request, {api_key: 1})
            return

        pending: Optional[Dict[str, int]] = None
        now_mono = time.monotonic()
        with self._buffer_lock:
            self._usage_buffer[api_key] = self._usage_buffer.get(api_key, 0) + 1
            total_pending = sum(self._usage_buffer.values())
            interval_elapsed = (
                self._flush_interval_seconds <= 0
                or (now_mono - self._last_flush_mono) >= self._flush_interval_seconds
            )
            if total_pending >= self._batch_size or interval_elapsed:
                pending = self._usage_buffer
                self._usage_buffer = {}
                self._last_flush_mono = now_mono

        if not pending:
            return

        try:
            self._flush_usage_batch(request, pending)
        except Exception:
            with self._buffer_lock:
                for key, value in pending.items():
                    self._usage_buffer[key] = self._usage_buffer.get(key, 0) + value
            raise

    def _flush_usage_batch(self, request: Request, increments: Dict[str, int]) -> None:
        db, generator = self._resolve_db(request)
        try:
            has_changes = False
            for api_key, increment in increments.items():
                if increment <= 0:
                    continue
                usage_query = db.query(User).filter(User.api_key == api_key)
                if hasattr(usage_query, "update"):
                    updated_rows = usage_query.update(
                        {User.requests_count: func.coalesce(User.requests_count, 0) + int(increment)},
                        synchronize_session=False,
                    )
                    has_changes = has_changes or bool(updated_rows)
                    continue

                # Compatibility fallback for non-SQLAlchemy test doubles.
                user = usage_query.first()
                if user:
                    user.requests_count = (user.requests_count or 0) + int(increment)
                    has_changes = True

            if has_changes:
                try:
                    db.commit()
                except Exception:
                    rollback = getattr(db, "rollback", None)
                    if callable(rollback):
                        rollback()
                    raise
        finally:
            self._close_db(db, generator)
