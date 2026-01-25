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
    
    @pytest.fixture
    def mock_alert_manager(self):
        """Create a mock AlertManager."""
        manager = Mock()
        manager.send_alert = AsyncMock()
        return manager
    
    @pytest.mark.asyncio
    async def test_critical_error_alert(self, mock_alert_manager):
        """Test that critical errors trigger alerts."""
        with patch('src.core.error_handler.AlertManager', return_value=mock_alert_manager):
            with patch('src.core.error_handler.ErrorHandler.handle_error._alert_manager', mock_alert_manager):
                error = ValueError("Critical system failure")
                
                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.CRITICAL
                )
                
                # Verify alert was sent
                assert mock_alert_manager.send_alert.called
                call_args = mock_alert_manager.send_alert.call_args
                assert call_args[0][0] == "ERROR_TEST_CONTEXT"
                assert call_args[0][1].value == "CRITICAL"
    
    @pytest.mark.asyncio
    async def test_high_error_alert(self, mock_alert_manager):
        """Test that high severity errors trigger alerts."""
        with patch('src.core.error_handler.AlertManager', return_value=mock_alert_manager):
            with patch('src.core.error_handler.ErrorHandler.handle_error._alert_manager', mock_alert_manager):
                error = RuntimeError("High severity error")
                
                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.HIGH
                )
                
                # Verify alert was sent
                assert mock_alert_manager.send_alert.called
                call_args = mock_alert_manager.send_alert.call_args
                assert call_args[0][0] == "ERROR_TEST_CONTEXT"
                assert call_args[0][1].value == "ERROR"
    
    @pytest.mark.asyncio
    async def test_medium_error_no_alert(self, mock_alert_manager):
        """Test that medium severity errors don't trigger alerts."""
        with patch('src.core.error_handler.AlertManager', return_value=mock_alert_manager):
            with patch('src.core.error_handler.ErrorHandler.handle_error._alert_manager', mock_alert_manager):
                error = ValueError("Medium severity error")
                
                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.MEDIUM
                )
                
                # Verify alert was NOT sent
                assert not mock_alert_manager.send_alert.called
    
    def test_sync_critical_error_alert(self, mock_alert_manager):
        """Test that sync version triggers alerts for critical errors."""
        with patch('src.core.error_handler.AlertManager', return_value=mock_alert_manager):
            with patch('src.core.error_handler.ErrorHandler.handle_error_sync._alert_manager', mock_alert_manager):
                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.is_running.return_value = False
                    mock_loop.return_value.run_until_complete = asyncio.run
                    
                    error = ValueError("Critical sync error")
                    
                    ErrorHandler.handle_error_sync(
                        error,
                        "test_context",
                        ErrorSeverity.CRITICAL
                    )
                    
                    # Give async task time to complete
                    asyncio.run(asyncio.sleep(0.1))
                    
                    # Verify alert was sent
                    assert mock_alert_manager.send_alert.called
                    call_args = mock_alert_manager.send_alert.call_args
                    assert call_args[0][0] == "ERROR_TEST_CONTEXT"
                    assert call_args[0][1].value == "CRITICAL"
    
    @pytest.mark.asyncio
    async def test_error_alert_with_additional_data(self, mock_alert_manager):
        """Test that additional data is included in alert annotations."""
        with patch('src.core.error_handler.AlertManager', return_value=mock_alert_manager):
            with patch('src.core.error_handler.ErrorHandler.handle_error._alert_manager', mock_alert_manager):
                error = ValueError("Error with context")
                additional_data = {"user_id": "123", "action": "test"}
                
                await ErrorHandler.handle_error(
                    error,
                    "test_context",
                    ErrorSeverity.CRITICAL,
                    additional_data=additional_data
                )
                
                # Verify alert was sent with annotations
                assert mock_alert_manager.send_alert.called
                call_args = mock_alert_manager.send_alert.call_args
                annotations = call_args[1].get('annotations', {})
                assert 'additional_data' in annotations


