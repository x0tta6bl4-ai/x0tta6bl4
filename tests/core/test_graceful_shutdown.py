"""
Tests for Graceful Shutdown module.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.core.graceful_shutdown import (GracefulShutdownManager,
                                        ShutdownMiddleware, ShutdownState,
                                        create_lifespan)


class TestShutdownState:
    """Tests for ShutdownState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        state = ShutdownState()
        assert state.is_shutting_down is False
        assert state.shutdown_started_at is None
        assert state.active_requests == 0
        assert len(state.active_tasks) == 0
        assert len(state.cleanup_handlers) == 0


class TestGracefulShutdownManager:
    """Tests for GracefulShutdownManager."""

    def test_initialization(self):
        """Test manager initialization."""
        manager = GracefulShutdownManager(
            shutdown_timeout=60.0, drain_timeout=20.0, force_exit=False
        )
        assert manager.shutdown_timeout == 60.0
        assert manager.drain_timeout == 20.0
        assert manager.force_exit is False
        assert manager.is_shutting_down is False

    def test_track_request(self):
        """Test request tracking."""
        manager = GracefulShutdownManager()

        assert manager.active_requests == 0

        manager.track_request_start()
        assert manager.active_requests == 1

        manager.track_request_start()
        assert manager.active_requests == 2

        manager.track_request_end()
        assert manager.active_requests == 1

        manager.track_request_end()
        assert manager.active_requests == 0

        # Should not go negative
        manager.track_request_end()
        assert manager.active_requests == 0

    def test_track_request_during_shutdown(self):
        """Test that requests are not tracked during shutdown."""
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True

        manager.track_request_start()
        assert manager.active_requests == 0

    @pytest.mark.asyncio
    async def test_track_task(self):
        """Test background task tracking."""
        manager = GracefulShutdownManager()

        async def dummy_task():
            await asyncio.sleep(0.1)

        task = asyncio.create_task(dummy_task())
        manager.track_task(task)

        assert len(manager.state.active_tasks) == 1

        await task
        # Task should be removed after completion
        await asyncio.sleep(0.01)  # Allow callback to run
        assert len(manager.state.active_tasks) == 0

    def test_register_cleanup(self):
        """Test cleanup handler registration."""
        manager = GracefulShutdownManager()

        def cleanup1():
            pass

        async def cleanup2():
            pass

        manager.register_cleanup(cleanup1, name="cleanup1")
        manager.register_cleanup(cleanup2, name="cleanup2")

        assert len(manager.state.cleanup_handlers) == 2

    @pytest.mark.asyncio
    async def test_drain_requests_empty(self):
        """Test draining when no active requests."""
        manager = GracefulShutdownManager()
        await manager._drain_requests()
        # Should complete immediately

    @pytest.mark.asyncio
    async def test_drain_requests_with_timeout(self):
        """Test draining with timeout."""
        manager = GracefulShutdownManager(drain_timeout=0.5)
        manager.state.active_requests = 5

        await manager._drain_requests()
        # Should timeout after drain_timeout

    @pytest.mark.asyncio
    async def test_run_cleanup_handlers(self):
        """Test running cleanup handlers."""
        manager = GracefulShutdownManager()

        cleanup_called = []

        def sync_cleanup():
            cleanup_called.append("sync")

        async def async_cleanup():
            cleanup_called.append("async")

        manager.register_cleanup(sync_cleanup)
        manager.register_cleanup(async_cleanup)

        await manager._run_cleanup_handlers()

        assert "sync" in cleanup_called
        assert "async" in cleanup_called

    @pytest.mark.asyncio
    async def test_cleanup_handler_error(self):
        """Test that cleanup continues after handler error."""
        manager = GracefulShutdownManager()

        cleanup_called = []

        def failing_cleanup():
            raise Exception("Cleanup failed")

        def working_cleanup():
            cleanup_called.append("working")

        manager.register_cleanup(failing_cleanup)
        manager.register_cleanup(working_cleanup)

        await manager._run_cleanup_handlers()

        # Second handler should still run
        assert "working" in cleanup_called

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test full shutdown sequence."""
        manager = GracefulShutdownManager(force_exit=False)

        cleanup_called = False

        async def cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        manager.register_cleanup(cleanup)

        await manager.shutdown()

        assert manager.is_shutting_down is True
        assert cleanup_called is True
        assert manager.state.shutdown_started_at is not None

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self):
        """Test that shutdown can only run once."""
        manager = GracefulShutdownManager(force_exit=False)

        await manager.shutdown()
        assert manager.is_shutting_down is True

        # Second call should return early
        await manager.shutdown()

    def test_get_status(self):
        """Test status reporting."""
        manager = GracefulShutdownManager()
        manager.track_request_start()
        manager.register_cleanup(lambda: None)

        status = manager.get_status()

        assert status["is_shutting_down"] is False
        assert status["active_requests"] == 1
        assert status["cleanup_handlers"] == 1


class TestShutdownMiddleware:
    """Tests for ShutdownMiddleware."""

    @pytest.mark.asyncio
    async def test_normal_request(self):
        """Test normal request passes through."""
        manager = GracefulShutdownManager()

        app_called = False

        async def mock_app(scope, receive, send):
            nonlocal app_called
            app_called = True

        middleware = ShutdownMiddleware(mock_app, manager)

        await middleware({"type": "http"}, AsyncMock(), AsyncMock())

        assert app_called is True
        assert manager.active_requests == 0  # Should be decremented after

    @pytest.mark.asyncio
    async def test_reject_during_shutdown(self):
        """Test requests rejected during shutdown."""
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True

        app_called = False

        async def mock_app(scope, receive, send):
            nonlocal app_called
            app_called = True

        send_mock = AsyncMock()
        middleware = ShutdownMiddleware(mock_app, manager)

        await middleware({"type": "http"}, AsyncMock(), send_mock)

        assert app_called is False
        # Should have sent 503 response
        assert send_mock.call_count == 2

    @pytest.mark.asyncio
    async def test_non_http_passes_through(self):
        """Test non-HTTP requests pass through during shutdown."""
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True

        app_called = False

        async def mock_app(scope, receive, send):
            nonlocal app_called
            app_called = True

        middleware = ShutdownMiddleware(mock_app, manager)

        await middleware({"type": "websocket"}, AsyncMock(), AsyncMock())

        assert app_called is True


class TestLifespanFactory:
    """Tests for create_lifespan factory."""

    @pytest.mark.asyncio
    async def test_create_lifespan_with_handlers(self):
        """Test lifespan with startup handlers."""
        startup_called = False

        async def startup():
            nonlocal startup_called
            startup_called = True

        # Note: We only test startup here because shutdown calls sys.exit
        # For full lifecycle testing, see TestIntegration
        from src.core.graceful_shutdown import shutdown_manager

        # Temporarily disable force_exit for this test
        original_force_exit = shutdown_manager.force_exit
        shutdown_manager.force_exit = False

        lifespan = create_lifespan(startup_handlers=[startup])

        mock_app = Mock()

        try:
            async with lifespan(mock_app):
                assert startup_called is True
        finally:
            # Reset state for other tests
            shutdown_manager.force_exit = original_force_exit
            shutdown_manager.state.is_shutting_down = False
            shutdown_manager.state.cleanup_handlers.clear()

    @pytest.mark.asyncio
    async def test_create_lifespan_startup_error(self):
        """Test that startup errors propagate."""

        async def failing_startup():
            raise ValueError("Startup failed")

        lifespan = create_lifespan(startup_handlers=[failing_startup])
        mock_app = Mock()

        with pytest.raises(ValueError, match="Startup failed"):
            async with lifespan(mock_app):
                pass


class TestIntegration:
    """Integration tests for graceful shutdown."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete application lifecycle."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        manager = GracefulShutdownManager(force_exit=False)
        cleanup_order = []

        async def cleanup1():
            cleanup_order.append(1)

        async def cleanup2():
            cleanup_order.append(2)

        manager.register_cleanup(cleanup1)
        manager.register_cleanup(cleanup2)

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        # Add middleware
        app.add_middleware(ShutdownMiddleware, shutdown_manager=manager)

        client = TestClient(app)

        # Normal request
        response = client.get("/test")
        assert response.status_code == 200

        # Shutdown
        await manager.shutdown()

        assert manager.is_shutting_down is True
        assert cleanup_order == [1, 2]
