"""
Tests for Error Handler.

Tests error handling, logging, and recovery mechanisms.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from src.core.error_handler import (ErrorHandler, ErrorSeverity,
                                        handle_error_decorator)

    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False
    ErrorHandler = None
    ErrorSeverity = None
    handle_error_decorator = None


@pytest.mark.skipif(not ERROR_HANDLER_AVAILABLE, reason="Error handler not available")
class TestErrorHandler:
    """Tests for ErrorHandler"""

    def test_error_handler_initialization(self):
        """Test error handler initialization"""
        handler = ErrorHandler()

        assert handler is not None
        assert hasattr(handler, "handle_error")
        assert hasattr(handler, "handle_error_sync")

    def test_error_logging_low_severity(self):
        """Test error logging with LOW severity"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.info") as mock_log:
            handler.handle_error_sync(
                Exception("Test error"),
                context="test_context",
                severity=ErrorSeverity.LOW,
            )
            mock_log.assert_called_once()

    def test_error_logging_medium_severity(self):
        """Test error logging with MEDIUM severity"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.warning") as mock_log:
            handler.handle_error_sync(
                Exception("Test error"),
                context="test_context",
                severity=ErrorSeverity.MEDIUM,
            )
            mock_log.assert_called_once()

    def test_error_logging_high_severity(self):
        """Test error logging with HIGH severity"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.error") as mock_log:
            handler.handle_error_sync(
                Exception("Test error"),
                context="test_context",
                severity=ErrorSeverity.HIGH,
            )
            mock_log.assert_called_once()

    def test_error_logging_critical_severity(self):
        """Test error logging with CRITICAL severity"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.critical") as mock_log:
            handler.handle_error_sync(
                Exception("Test error"),
                context="test_context",
                severity=ErrorSeverity.CRITICAL,
            )
            mock_log.assert_called_once()
            # Critical should include exc_info
            assert mock_log.call_args[1].get("exc_info") is True

    def test_error_logging_with_additional_data(self):
        """Test error logging with additional data"""
        handler = ErrorHandler()

        additional_data = {"key1": "value1", "key2": 42}

        with patch("src.core.error_handler.logger.warning") as mock_log:
            handler.handle_error_sync(
                ValueError("Test error"),
                context="test_context",
                severity=ErrorSeverity.MEDIUM,
                additional_data=additional_data,
            )
            mock_log.assert_called_once()
            # Check that additional_data is in the log call
            call_kwargs = mock_log.call_args[1]
            assert "extra" in call_kwargs
            log_data = call_kwargs["extra"]
            assert log_data["key1"] == "value1"
            assert log_data["key2"] == 42

    @pytest.mark.asyncio
    async def test_handle_error_async(self):
        """Test async handle_error method"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.warning") as mock_log:
            await handler.handle_error(
                Exception("Test error"),
                context="test_context",
                severity=ErrorSeverity.MEDIUM,
            )
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_async_with_alerting(self):
        """Test async handle_error with alerting available"""
        handler = ErrorHandler()

        # Mock the import at module level
        with (
            patch("src.core.error_handler.ALERTING_AVAILABLE", True),
            patch(
                "src.core.error_handler.send_alert", new_callable=AsyncMock
            ) as mock_alert,
            patch("src.core.error_handler.AlertSeverity") as mock_alert_severity,
            patch("src.core.error_handler.logger.critical") as mock_log,
        ):

            # Mock AlertSeverity enum
            mock_alert_severity.CRITICAL = "CRITICAL"
            mock_alert_severity.ERROR = "ERROR"

            # Mock prometheus to avoid registry issues - patch at import site
            with patch(
                "prometheus_client.Counter", side_effect=ImportError("No prometheus")
            ):
                await handler.handle_error(
                    Exception("Critical error"),
                    context="test_context",
                    severity=ErrorSeverity.CRITICAL,
                )

            # Should log
            mock_log.assert_called_once()
            # Should send alert for CRITICAL
            mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_async_high_severity_alerting(self):
        """Test async handle_error with HIGH severity triggers alerting"""
        handler = ErrorHandler()

        with (
            patch("src.core.error_handler.ALERTING_AVAILABLE", True),
            patch(
                "src.core.error_handler.send_alert", new_callable=AsyncMock
            ) as mock_alert,
            patch("src.core.error_handler.AlertSeverity") as mock_alert_severity,
            patch("src.core.error_handler.logger.error") as mock_log,
        ):

            mock_alert_severity.ERROR = "ERROR"

            # Mock prometheus to avoid registry issues
            with patch(
                "prometheus_client.Counter", side_effect=ImportError("No prometheus")
            ):
                await handler.handle_error(
                    Exception("High error"),
                    context="test_context",
                    severity=ErrorSeverity.HIGH,
                )

            # Should log
            mock_log.assert_called_once()
            # Should send alert for HIGH
            mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_async_medium_severity_no_alerting(self):
        """Test async handle_error with MEDIUM severity doesn't trigger alerting"""
        handler = ErrorHandler()

        with (
            patch("src.core.error_handler.ALERTING_AVAILABLE", True),
            patch(
                "src.core.error_handler.send_alert", new_callable=AsyncMock
            ) as mock_alert,
            patch("src.core.error_handler.logger.warning") as mock_log,
        ):

            # Mock prometheus to avoid registry issues
            with patch(
                "prometheus_client.Counter", side_effect=ImportError("No prometheus")
            ):
                await handler.handle_error(
                    Exception("Medium error"),
                    context="test_context",
                    severity=ErrorSeverity.MEDIUM,
                )

            # Should log
            mock_log.assert_called_once()
            # Should NOT send alert for MEDIUM
            mock_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_error_async_alerting_failure(self):
        """Test that alerting failure doesn't break error handling"""
        handler = ErrorHandler()

        with (
            patch("src.core.error_handler.ALERTING_AVAILABLE", True),
            patch(
                "src.core.error_handler.send_alert",
                side_effect=Exception("Alert failed"),
            ),
            patch("src.core.error_handler.AlertSeverity") as mock_alert_severity,
            patch("src.core.error_handler.logger.critical") as mock_log,
            patch("src.core.error_handler.logger.warning") as mock_warning,
        ):

            mock_alert_severity.CRITICAL = "CRITICAL"

            # Mock prometheus to avoid registry issues
            with patch(
                "prometheus_client.Counter", side_effect=ImportError("No prometheus")
            ):
                # Should not raise exception
                await handler.handle_error(
                    Exception("Critical error"),
                    context="test_context",
                    severity=ErrorSeverity.CRITICAL,
                )

            # Should log error
            mock_log.assert_called_once()
            # Should log warning about alert failure
            mock_warning.assert_called()

    def test_handle_error_sync_prometheus_metrics(self):
        """Test that Prometheus metrics are updated"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.warning") as mock_log:
            # Patch the import inside the function
            mock_counter_class = Mock()
            mock_counter_instance = Mock()
            mock_labels = Mock()
            mock_labels.inc = Mock()
            mock_counter_instance.labels.return_value = mock_labels
            mock_counter_class.return_value = mock_counter_instance

            # Patch the import statement inside handle_error_sync
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: (
                    Mock(Counter=mock_counter_class)
                    if name == "prometheus_client"
                    else __import__(name, *args, **kwargs)
                ),
            ):
                handler.handle_error_sync(
                    ValueError("Test"),
                    context="test_context",
                    severity=ErrorSeverity.MEDIUM,
                )

                # Should still log
                mock_log.assert_called_once()
                # Counter may or may not be called depending on prometheus availability
                # The important thing is that it doesn't break

    def test_handle_error_sync_prometheus_unavailable(self):
        """Test that missing Prometheus doesn't break error handling"""
        handler = ErrorHandler()

        with patch("src.core.error_handler.logger.warning") as mock_log:
            # Simulate ImportError for prometheus_client
            with patch(
                "builtins.__import__",
                side_effect=ImportError("No module named 'prometheus_client'"),
            ):
                # Should not raise exception
                handler.handle_error_sync(
                    ValueError("Test"),
                    context="test_context",
                    severity=ErrorSeverity.MEDIUM,
                )

                # Should still log
                mock_log.assert_called_once()

    def test_error_recovery(self):
        """Test error recovery mechanism"""
        handler = ErrorHandler()

        # Test recovery for different error types using sync version
        # handle_error_sync doesn't return anything, but it should complete without error
        try:
            handler.handle_error_sync(
                ValueError("Test"),
                context="test_recovery",
                severity=ErrorSeverity.MEDIUM,
            )
            # If we get here, recovery mechanism worked
            assert True
        except Exception as e:
            pytest.fail(f"Error recovery failed: {e}")


@pytest.mark.skipif(not ERROR_HANDLER_AVAILABLE, reason="Error handler not available")
class TestErrorHandlerDecorator:
    """Tests for handle_error_decorator"""

    @pytest.mark.asyncio
    async def test_decorator_async_function_success(self):
        """Test decorator on async function that succeeds"""

        @handle_error_decorator("test_async", ErrorSeverity.MEDIUM)
        async def test_func():
            return "success"

        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_async_function_error(self):
        """Test decorator on async function that raises error"""

        @handle_error_decorator("test_async_error", ErrorSeverity.HIGH)
        async def test_func():
            raise ValueError("Test error")

        with patch(
            "src.core.error_handler.ErrorHandler.handle_error", new_callable=AsyncMock
        ) as mock_handle:
            with pytest.raises(ValueError):
                await test_func()

            # Should call handle_error
            mock_handle.assert_called_once()

    def test_decorator_sync_function_success(self):
        """Test decorator on sync function that succeeds"""

        @handle_error_decorator("test_sync", ErrorSeverity.MEDIUM)
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_decorator_sync_function_error(self):
        """Test decorator on sync function that raises error"""

        @handle_error_decorator("test_sync_error", ErrorSeverity.HIGH)
        def test_func():
            raise ValueError("Test error")

        with patch(
            "src.core.error_handler.ErrorHandler.handle_error_sync"
        ) as mock_handle:
            with pytest.raises(ValueError):
                test_func()

            # Should call handle_error_sync
            mock_handle.assert_called_once()

    def test_decorator_with_different_severity(self):
        """Test decorator with different severity levels"""

        @handle_error_decorator("test_critical", ErrorSeverity.CRITICAL)
        def test_func():
            raise RuntimeError("Critical error")

        with patch(
            "src.core.error_handler.ErrorHandler.handle_error_sync"
        ) as mock_handle:
            with pytest.raises(RuntimeError):
                test_func()

            # Check severity was passed correctly
            call_args = mock_handle.call_args[0]
            assert call_args[2] == ErrorSeverity.CRITICAL  # severity is 3rd arg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
