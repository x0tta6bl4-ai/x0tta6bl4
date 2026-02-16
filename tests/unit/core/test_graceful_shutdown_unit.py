"""Unit tests for src.core.graceful_shutdown module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.graceful_shutdown import (GracefulShutdownManager,
                                        ShutdownMiddleware, ShutdownState)


class TestShutdownState:
    """Tests for ShutdownState dataclass defaults."""

    def test_defaults(self):
        state = ShutdownState()
        assert state.is_shutting_down is False
        assert state.shutdown_started_at is None
        assert state.active_requests == 0
        assert state.active_tasks == set()
        assert state.cleanup_handlers == []


class TestGracefulShutdownManager:
    """Tests for GracefulShutdownManager."""

    def test_initial_state(self):
        manager = GracefulShutdownManager()
        assert manager.is_shutting_down is False
        assert manager.active_requests == 0
        assert manager.shutdown_timeout == 30.0
        assert manager.drain_timeout == 10.0
        assert manager.force_exit is True

    def test_custom_init_params(self):
        manager = GracefulShutdownManager(
            shutdown_timeout=60.0,
            drain_timeout=20.0,
            force_exit=False,
        )
        assert manager.shutdown_timeout == 60.0
        assert manager.drain_timeout == 20.0
        assert manager.force_exit is False

    def test_track_request_start_increments(self):
        manager = GracefulShutdownManager()
        manager.track_request_start()
        assert manager.active_requests == 1
        manager.track_request_start()
        assert manager.active_requests == 2

    def test_track_request_end_decrements(self):
        manager = GracefulShutdownManager()
        manager.track_request_start()
        manager.track_request_start()
        manager.track_request_end()
        assert manager.active_requests == 1

    def test_track_request_end_does_not_go_below_zero(self):
        manager = GracefulShutdownManager()
        assert manager.active_requests == 0
        manager.track_request_end()
        assert manager.active_requests == 0

    def test_track_request_start_ignored_during_shutdown(self):
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True
        manager.track_request_start()
        assert manager.active_requests == 0

    def test_register_cleanup_adds_handler(self):
        manager = GracefulShutdownManager()

        def my_cleanup():
            pass

        manager.register_cleanup(my_cleanup, name="my_cleanup")
        assert len(manager.state.cleanup_handlers) == 1
        assert manager.state.cleanup_handlers[0] is my_cleanup
        assert manager.state.cleanup_handlers[0]._cleanup_name == "my_cleanup"

    def test_register_cleanup_without_name(self):
        manager = GracefulShutdownManager()

        def another_cleanup():
            pass

        manager.register_cleanup(another_cleanup)
        assert len(manager.state.cleanup_handlers) == 1
        assert not hasattr(manager.state.cleanup_handlers[0], "_cleanup_name")

    def test_get_status(self):
        manager = GracefulShutdownManager()
        manager.track_request_start()
        manager.register_cleanup(lambda: None, name="test")

        status = manager.get_status()

        assert status == {
            "is_shutting_down": False,
            "active_requests": 1,
            "active_tasks": 0,
            "cleanup_handlers": 1,
            "shutdown_started_at": None,
        }

    def test_get_status_during_shutdown(self):
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True
        manager.state.shutdown_started_at = 1700000000.0

        status = manager.get_status()
        assert status["is_shutting_down"] is True
        assert status["shutdown_started_at"] == 1700000000.0

    @pytest.mark.asyncio
    async def test_track_task(self):
        manager = GracefulShutdownManager()

        async def dummy_coro():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_coro())
        manager.track_task(task)
        assert task in manager.state.active_tasks

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # done_callback should have removed the task
        assert task not in manager.state.active_tasks

    @pytest.mark.asyncio
    async def test_shutdown_sets_is_shutting_down(self):
        manager = GracefulShutdownManager(force_exit=False)
        assert manager.is_shutting_down is False

        await manager.shutdown()

        assert manager.is_shutting_down is True
        assert manager.state.shutdown_started_at is not None

    @pytest.mark.asyncio
    async def test_shutdown_runs_sync_cleanup_handler(self):
        manager = GracefulShutdownManager(force_exit=False)
        called = []

        def sync_handler():
            called.append("sync")

        manager.register_cleanup(sync_handler, name="sync_handler")
        await manager.shutdown()

        assert called == ["sync"]

    @pytest.mark.asyncio
    async def test_shutdown_runs_async_cleanup_handler(self):
        manager = GracefulShutdownManager(force_exit=False)
        called = []

        async def async_handler():
            called.append("async")

        manager.register_cleanup(async_handler, name="async_handler")
        await manager.shutdown()

        assert called == ["async"]

    @pytest.mark.asyncio
    async def test_shutdown_runs_multiple_handlers_in_order(self):
        manager = GracefulShutdownManager(force_exit=False)
        order = []

        def first():
            order.append(1)

        async def second():
            order.append(2)

        def third():
            order.append(3)

        manager.register_cleanup(first, name="first")
        manager.register_cleanup(second, name="second")
        manager.register_cleanup(third, name="third")

        await manager.shutdown()

        assert order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self):
        manager = GracefulShutdownManager(force_exit=False)
        call_count = 0

        def handler():
            nonlocal call_count
            call_count += 1

        manager.register_cleanup(handler, name="handler")

        await manager.shutdown()
        await manager.shutdown()  # second call should exit early

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_shutdown_with_force_exit(self):
        manager = GracefulShutdownManager(force_exit=True)

        with patch("sys.exit") as mock_exit:
            await manager.shutdown()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_shutdown_cancels_tracked_tasks(self):
        manager = GracefulShutdownManager(force_exit=False)

        async def long_running():
            await asyncio.sleep(100)

        task = asyncio.create_task(long_running())
        manager.track_task(task)

        await manager.shutdown()

        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_shutdown_handles_cleanup_exception(self):
        """Cleanup handler that raises should not prevent other handlers from running."""
        manager = GracefulShutdownManager(force_exit=False)
        called = []

        def failing_handler():
            raise RuntimeError("cleanup failed")

        def good_handler():
            called.append("good")

        manager.register_cleanup(failing_handler, name="failing")
        manager.register_cleanup(good_handler, name="good")

        await manager.shutdown()

        assert called == ["good"]


class TestShutdownMiddleware:
    """Tests for ShutdownMiddleware."""

    @pytest.mark.asyncio
    async def test_passes_non_http_requests_through(self):
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True

        inner_app = AsyncMock()
        middleware = ShutdownMiddleware(inner_app, manager)

        scope = {"type": "websocket"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        inner_app.assert_awaited_once_with(scope, receive, send)

    @pytest.mark.asyncio
    async def test_rejects_requests_during_shutdown_with_503(self):
        manager = GracefulShutdownManager()
        manager.state.is_shutting_down = True

        inner_app = AsyncMock()
        middleware = ShutdownMiddleware(inner_app, manager)

        scope = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Inner app should NOT be called
        inner_app.assert_not_awaited()

        # Should have sent a 503 response
        assert send.await_count == 2
        start_call = send.await_args_list[0][0][0]
        assert start_call["type"] == "http.response.start"
        assert start_call["status"] == 503

        body_call = send.await_args_list[1][0][0]
        assert body_call["type"] == "http.response.body"
        assert b"Service shutting down" in body_call["body"]

    @pytest.mark.asyncio
    async def test_tracks_requests_when_not_shutting_down(self):
        manager = GracefulShutdownManager()

        async def mock_app(scope, receive, send):
            # During the request, active_requests should be 1
            assert manager.active_requests == 1

        middleware = ShutdownMiddleware(mock_app, manager)

        scope = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # After the request completes, active_requests should be back to 0
        assert manager.active_requests == 0

    @pytest.mark.asyncio
    async def test_tracks_request_end_even_on_exception(self):
        manager = GracefulShutdownManager()

        async def failing_app(scope, receive, send):
            raise RuntimeError("app error")

        middleware = ShutdownMiddleware(failing_app, manager)

        scope = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        with pytest.raises(RuntimeError, match="app error"):
            await middleware(scope, receive, send)

        # track_request_end should still be called via finally
        assert manager.active_requests == 0
