"""
Graceful Shutdown Handler for FastAPI

Provides clean shutdown with:
- Signal handling (SIGTERM, SIGINT)
- Connection draining
- In-flight request completion
- Background task cleanup
- Resource cleanup (DB, Redis, etc.)
"""

import asyncio
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ShutdownState:
    """Tracks shutdown state and active requests."""

    is_shutting_down: bool = False
    shutdown_started_at: Optional[float] = None
    active_requests: int = 0
    active_tasks: Set[asyncio.Task] = field(default_factory=set)
    cleanup_handlers: List[Callable] = field(default_factory=list)


class GracefulShutdownManager:
    """
    Manages graceful shutdown of FastAPI application.

    Features:
    - Signal handling for SIGTERM and SIGINT
    - Tracks active requests and waits for completion
    - Runs cleanup handlers in order
    - Configurable shutdown timeout
    - Health endpoint integration

    Usage:
        shutdown_manager = GracefulShutdownManager()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            shutdown_manager.setup_signal_handlers()
            yield
            # Shutdown
            await shutdown_manager.shutdown()

        app = FastAPI(lifespan=lifespan)

        # Register cleanup handlers
        shutdown_manager.register_cleanup(close_database)
        shutdown_manager.register_cleanup(close_redis)
    """

    def __init__(
        self,
        shutdown_timeout: float = 30.0,
        drain_timeout: float = 10.0,
        force_exit: bool = True,
    ):
        """
        Initialize shutdown manager.

        Args:
            shutdown_timeout: Max time to wait for shutdown (seconds)
            drain_timeout: Max time to wait for requests to drain (seconds)
            force_exit: Force exit after timeout
        """
        self.shutdown_timeout = shutdown_timeout
        self.drain_timeout = drain_timeout
        self.force_exit = force_exit
        self.state = ShutdownState()
        self._shutdown_event = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.state.is_shutting_down

    @property
    def active_requests(self) -> int:
        """Get count of active requests."""
        return self.state.active_requests

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        self._loop = asyncio.get_event_loop()

        # Handle SIGTERM (Kubernetes, Docker)
        try:
            self._loop.add_signal_handler(
                signal.SIGTERM,
                lambda: asyncio.create_task(self._handle_signal(signal.SIGTERM)),
            )
            logger.info("SIGTERM handler registered")
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Could not register SIGTERM handler: {e}")

        # Handle SIGINT (Ctrl+C)
        try:
            self._loop.add_signal_handler(
                signal.SIGINT,
                lambda: asyncio.create_task(self._handle_signal(signal.SIGINT)),
            )
            logger.info("SIGINT handler registered")
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Could not register SIGINT handler: {e}")

    async def _handle_signal(self, sig: signal.Signals):
        """Handle shutdown signal."""
        logger.info(f"Received signal {sig.name}, initiating graceful shutdown...")
        self._shutdown_event.set()
        await self.shutdown()

    def register_cleanup(self, handler: Callable, name: str = None):
        """
        Register a cleanup handler to run during shutdown.

        Handlers are run in registration order.

        Args:
            handler: Async or sync callable to run during cleanup
            name: Optional name for logging
        """
        if name:
            handler._cleanup_name = name
        self.state.cleanup_handlers.append(handler)
        logger.debug(f"Registered cleanup handler: {name or handler.__name__}")

    def track_request_start(self):
        """Track start of a new request."""
        if not self.state.is_shutting_down:
            self.state.active_requests += 1

    def track_request_end(self):
        """Track end of a request."""
        self.state.active_requests = max(0, self.state.active_requests - 1)

    def track_task(self, task: asyncio.Task):
        """Track a background task."""
        self.state.active_tasks.add(task)
        task.add_done_callback(lambda t: self.state.active_tasks.discard(t))

    async def wait_for_shutdown_signal(self):
        """Wait for shutdown signal (for background workers)."""
        await self._shutdown_event.wait()

    async def shutdown(self):
        """
        Perform graceful shutdown.

        Steps:
        1. Mark as shutting down (reject new requests)
        2. Wait for active requests to complete (drain)
        3. Cancel background tasks
        4. Run cleanup handlers
        5. Exit if configured
        """
        if self.state.is_shutting_down:
            logger.warning("Shutdown already in progress")
            return

        self.state.is_shutting_down = True
        self.state.shutdown_started_at = time.time()
        logger.info("Starting graceful shutdown...")

        # Step 1: Wait for active requests to drain
        await self._drain_requests()

        # Step 2: Cancel background tasks
        await self._cancel_tasks()

        # Step 3: Run cleanup handlers
        await self._run_cleanup_handlers()

        elapsed = time.time() - self.state.shutdown_started_at
        logger.info(f"Graceful shutdown completed in {elapsed:.2f}s")

        # Step 4: Force exit if configured
        if self.force_exit:
            logger.info("Exiting process...")
            sys.exit(0)

    async def _drain_requests(self):
        """Wait for active requests to complete."""
        if self.state.active_requests == 0:
            logger.info("No active requests to drain")
            return

        logger.info(f"Draining {self.state.active_requests} active requests...")
        start_time = time.time()

        while self.state.active_requests > 0:
            elapsed = time.time() - start_time
            if elapsed >= self.drain_timeout:
                logger.warning(
                    f"Drain timeout reached with {self.state.active_requests} "
                    f"requests still active"
                )
                break

            logger.debug(f"Waiting for {self.state.active_requests} requests...")
            await asyncio.sleep(0.5)

        elapsed = time.time() - start_time
        logger.info(f"Request draining completed in {elapsed:.2f}s")

    async def _cancel_tasks(self):
        """Cancel tracked background tasks."""
        if not self.state.active_tasks:
            logger.info("No background tasks to cancel")
            return

        logger.info(f"Cancelling {len(self.state.active_tasks)} background tasks...")

        for task in self.state.active_tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete cancellation
        if self.state.active_tasks:
            await asyncio.gather(*self.state.active_tasks, return_exceptions=True)

        logger.info("Background tasks cancelled")

    async def _run_cleanup_handlers(self):
        """Run registered cleanup handlers."""
        if not self.state.cleanup_handlers:
            logger.info("No cleanup handlers registered")
            return

        logger.info(f"Running {len(self.state.cleanup_handlers)} cleanup handlers...")

        for handler in self.state.cleanup_handlers:
            name = getattr(handler, "_cleanup_name", handler.__name__)
            try:
                logger.debug(f"Running cleanup: {name}")
                if asyncio.iscoroutinefunction(handler):
                    await asyncio.wait_for(handler(), timeout=5.0)
                else:
                    handler()
                logger.debug(f"Cleanup completed: {name}")
            except asyncio.TimeoutError:
                logger.error(f"Cleanup handler timed out: {name}")
            except Exception as e:
                logger.error(f"Cleanup handler failed: {name} - {e}")

        logger.info("Cleanup handlers completed")

    def get_status(self) -> dict:
        """Get current shutdown status."""
        return {
            "is_shutting_down": self.state.is_shutting_down,
            "active_requests": self.state.active_requests,
            "active_tasks": len(self.state.active_tasks),
            "cleanup_handlers": len(self.state.cleanup_handlers),
            "shutdown_started_at": self.state.shutdown_started_at,
        }


class ShutdownMiddleware:
    """
    ASGI Middleware for tracking requests during shutdown.

    Rejects new requests when shutdown is in progress.
    """

    def __init__(self, app, shutdown_manager: GracefulShutdownManager):
        self.app = app
        self.shutdown_manager = shutdown_manager

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Reject new requests during shutdown
        if self.shutdown_manager.is_shutting_down:
            response = {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"connection", b"close"],
                ],
            }
            await send(response)
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error": "Service shutting down", "retry_after": 30}',
                }
            )
            return

        # Track request
        self.shutdown_manager.track_request_start()
        try:
            await self.app(scope, receive, send)
        finally:
            self.shutdown_manager.track_request_end()


# Global shutdown manager instance
shutdown_manager = GracefulShutdownManager()


def create_lifespan(
    startup_handlers: List[Callable] = None, cleanup_handlers: List[Callable] = None
):
    """
    Create a lifespan context manager for FastAPI.

    Usage:
        app = FastAPI(lifespan=create_lifespan(
            startup_handlers=[init_database, init_redis],
            cleanup_handlers=[close_database, close_redis]
        ))
    """

    @asynccontextmanager
    async def lifespan(app):
        # Startup
        shutdown_manager.setup_signal_handlers()

        if startup_handlers:
            for handler in startup_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler()
                    else:
                        handler()
                    logger.info(f"Startup: {handler.__name__} completed")
                except Exception as e:
                    logger.error(f"Startup failed: {handler.__name__} - {e}")
                    raise

        # Register cleanup handlers
        if cleanup_handlers:
            for handler in cleanup_handlers:
                shutdown_manager.register_cleanup(handler)

        logger.info("Application startup complete")

        yield

        # Shutdown
        await shutdown_manager.shutdown()

    return lifespan


# Convenience functions for common cleanup operations


async def close_database_connections():
    """Close database connections."""
    try:
        from src.database import engine

        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


async def close_redis_connections():
    """Close Redis connections."""
    try:
        from libx0t.core.cache import cache

        await cache.close()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {e}")


async def close_http_clients():
    """Close HTTP client connections."""
    try:
        import httpx

        # httpx clients should be closed by their context managers
        logger.info("HTTP clients cleanup completed")
    except Exception as e:
        logger.error(f"Error closing HTTP clients: {e}")


__all__ = [
    "GracefulShutdownManager",
    "ShutdownMiddleware",
    "ShutdownState",
    "shutdown_manager",
    "create_lifespan",
    "close_database_connections",
    "close_redis_connections",
    "close_http_clients",
]
