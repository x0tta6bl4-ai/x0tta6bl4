"""
Tests for Alerting System.

Tests alert generation, notification, and escalation.
"""

from unittest.mock import AsyncMock, patch

import pytest

try:
    from src.monitoring.alerting import AlertSeverity, AlertManager

    ALERTING_AVAILABLE = True
except ImportError:
    ALERTING_AVAILABLE = False
    AlertManager = None
    AlertSeverity = None


@pytest.mark.skipif(not ALERTING_AVAILABLE, reason="Alerting not available")
class TestAlertManager:
    """Tests for AlertManager"""

    def test_alert_manager_initialization(self):
        """Test alert manager initialization"""
        manager = AlertManager()

        assert manager is not None
        assert hasattr(manager, "send_alert")
        assert hasattr(manager, "get_health_status")

    @pytest.mark.asyncio
    async def test_alert_send(self):
        """Test alert sending"""
        manager = AlertManager(
            alertmanager_url="http://localhost:9093",
            telegram_bot_token="test-token",
            telegram_chat_id="test-chat",
        )

        # Mock the internal send methods to avoid external calls
        with patch.object(manager, "_send_to_alertmanager_with_retry", new_callable=AsyncMock) as mock_am:
            with patch.object(manager, "_send_to_telegram_with_retry", new_callable=AsyncMock) as mock_tg:
                # Mock rate limit to allow the alert
                with patch.object(manager, "_check_rate_limit", return_value=True):
                    await manager.send_alert(
                        alert_name="test_alert",
                        severity=AlertSeverity.WARNING,
                        message="Test alert message",
                    )
                    # At least one channel should have been called
                    assert mock_am.called or mock_tg.called

    @pytest.mark.asyncio
    async def test_alert_with_labels(self):
        """Test alert with custom labels"""
        manager = AlertManager(
            alertmanager_url="http://localhost:9093",
            telegram_bot_token="test-token",
            telegram_chat_id="test-chat",
        )

        with patch.object(manager, "_send_to_alertmanager_with_retry", new_callable=AsyncMock):
            with patch.object(manager, "_send_to_telegram_with_retry", new_callable=AsyncMock):
                with patch.object(manager, "_check_rate_limit", return_value=True):
                    await manager.send_alert(
                        alert_name="test_with_labels",
                        severity=AlertSeverity.INFO,
                        message="Alert with labels",
                        labels={"env": "test", "service": "x0tta6bl4"},
                    )
                    # Should not raise

    def test_health_status(self):
        """Test health status check"""
        manager = AlertManager()
        status = manager.get_health_status()
        assert isinstance(status, dict)


@pytest.mark.skipif(not ALERTING_AVAILABLE, reason="Alerting not available")
class TestAlertSeverity:
    """Tests for AlertSeverity enum"""

    def test_severity_values(self):
        """Test that severity levels exist"""
        assert hasattr(AlertSeverity, "CRITICAL")
        assert hasattr(AlertSeverity, "WARNING")
        assert hasattr(AlertSeverity, "INFO")

    def test_severity_comparison(self):
        """Test severity ordering"""
        # AlertSeverity is an enum, check values exist
        assert AlertSeverity.CRITICAL is not None
        assert AlertSeverity.WARNING is not None
        assert AlertSeverity.INFO is not None
        # Check they are different values
        assert AlertSeverity.CRITICAL != AlertSeverity.WARNING
        assert AlertSeverity.WARNING != AlertSeverity.INFO


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
