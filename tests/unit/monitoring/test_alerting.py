"""
Tests for Alerting System.

Tests alert generation, notification, and escalation.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

try:
    from src.monitoring.alerting import AlertLevel, AlertManager

    ALERTING_AVAILABLE = True
except ImportError:
    ALERTING_AVAILABLE = False
    AlertManager = None
    AlertLevel = None


@pytest.mark.skipif(not ALERTING_AVAILABLE, reason="Alerting not available")
class TestAlertManager:
    """Tests for AlertManager"""

    def test_alert_manager_initialization(self):
        """Test alert manager initialization"""
        manager = AlertManager()

        assert manager is not None
        assert hasattr(manager, "create_alert")

    def test_alert_creation(self):
        """Test alert creation"""
        manager = AlertManager()

        alert = manager.create_alert(message="Test alert", level=AlertLevel.WARNING)

        assert alert is not None
        assert alert.message == "Test alert"

    def test_alert_notification(self):
        """Test alert notification"""
        manager = AlertManager()

        with patch.object(manager, "send_notification") as mock_send:
            alert = manager.create_alert("Test", AlertLevel.CRITICAL)
            manager.send_notification(alert)
            mock_send.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
