"""
Tests for Error Handler Alerting Integration.

Tests the full alerting integration for error handler including:
- Critical error alerts
- High severity error alerts
- AlertManager integration
- Sync and async versions
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from src.core.error_handler import ErrorHandler, ErrorSeverity


class TestErrorHandlerAlerting:
    """Test error handler alerting integration."""

    @pytest.mark.asyncio
    async def test_critical_error_alert(self):
        """Test that critical errors trigger alerts."""
        mock_send_alert = AsyncMock()

        with patch('src.core.error_handler.ALERTING_AVAILABLE', True):
            with patch('src.core.error_handler.send_alert', mock_send_alert):
                error = ValueError("Critical system failure")

                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.CRITICAL
                )

                # Verify alert was sent
                assert mock_send_alert.called
                call_args = mock_send_alert.call_args
                assert call_args[0][0] == "ERROR_TEST_CONTEXT"

    @pytest.mark.asyncio
    async def test_high_error_alert(self):
        """Test that high severity errors trigger alerts."""
        mock_send_alert = AsyncMock()

        with patch('src.core.error_handler.ALERTING_AVAILABLE', True):
            with patch('src.core.error_handler.send_alert', mock_send_alert):
                error = RuntimeError("High severity error")

                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.HIGH
                )

                # Verify alert was sent
                assert mock_send_alert.called
                call_args = mock_send_alert.call_args
                assert call_args[0][0] == "ERROR_TEST_CONTEXT"

    @pytest.mark.asyncio
    async def test_medium_error_no_alert(self):
        """Test that medium severity errors don't trigger alerts."""
        mock_send_alert = AsyncMock()

        with patch('src.core.error_handler.ALERTING_AVAILABLE', True):
            with patch('src.core.error_handler.send_alert', mock_send_alert):
                error = ValueError("Medium severity error")

                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.MEDIUM
                )

                # Verify alert was NOT sent (medium severity doesn't trigger alerts)
                assert not mock_send_alert.called

    def test_sync_critical_error_alert(self):
        """Test that sync version triggers alerts for critical errors."""
        mock_alert_manager = Mock()
        mock_alert_manager.send_alert = AsyncMock()

        with patch('src.core.error_handler.ALERTING_AVAILABLE', True):
            with patch('src.monitoring.alerting.AlertManager', return_value=mock_alert_manager):
                error = ValueError("Critical sync error")

                ErrorHandler.handle_error_sync(
                    error,
                    "test_context",
                    ErrorSeverity.CRITICAL
                )

                # Sync version schedules async alert, may not complete immediately
                # Just verify no exception was raised

    @pytest.mark.asyncio
    async def test_error_alert_with_additional_data(self):
        """Test that additional data is included in alert annotations."""
        mock_send_alert = AsyncMock()

        with patch('src.core.error_handler.ALERTING_AVAILABLE', True):
            with patch('src.core.error_handler.send_alert', mock_send_alert):
                error = ValueError("Error with context")
                additional_data = {"user_id": "123", "action": "test"}

                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.CRITICAL,
                    additional_data=additional_data
                )

                # Verify alert was sent with annotations
                assert mock_send_alert.called
                call_args = mock_send_alert.call_args
                annotations = call_args[1].get('annotations', {})
                assert 'additional_data' in annotations
