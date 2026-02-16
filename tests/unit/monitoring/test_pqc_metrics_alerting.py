"""
Tests for PQC Metrics Alerting Integration.

Tests the full alerting integration for PQC metrics including:
- Handshake success/failure alerts
- SLO violation alerts
- Fallback enabled/expired alerts
- Key rotation failure alerts
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.monitoring.pqc_metrics import (FALLBACK_TTL,
                                        PQC_HANDSHAKE_P95_LATENCY_SLO,
                                        check_fallback_ttl, disable_fallback,
                                        enable_fallback,
                                        record_handshake_failure,
                                        record_handshake_success,
                                        record_key_rotation_failure)


class TestPQCAlertingIntegration:
    """Test PQC metrics alerting integration."""

    @pytest.fixture
    def mock_alert_manager(self):
        """Create a mock AlertManager."""
        manager = Mock()
        manager.send_alert = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_handshake_success_slo_violation_alert(self, mock_alert_manager):
        """Test that SLO violation triggers alert."""
        # Set high latency that violates SLO
        high_latency = PQC_HANDSHAKE_P95_LATENCY_SLO + 0.05  # 150ms > 100ms

        with patch("src.monitoring.alerting.send_alert_sync") as mock_send_alert:
            record_handshake_success(high_latency)

            # Verify alert was sent
            assert mock_send_alert.called
            call_args = mock_send_alert.call_args
            assert call_args[0][0] == "PQC_HANDSHAKE_SLO_VIOLATION"

    @pytest.mark.asyncio
    async def test_handshake_failure_alert(self, mock_alert_manager):
        """Test that handshake failure triggers critical alert."""
        with patch("src.monitoring.alerting.send_alert_sync") as mock_send_alert:
            record_handshake_failure("timeout")

            # Verify alert was sent
            assert mock_send_alert.called
            call_args = mock_send_alert.call_args
            assert call_args[0][0] == "PQC_HANDSHAKE_FAILURE"
            assert call_args[0][1].value == "critical"

    @pytest.mark.asyncio
    async def test_fallback_enabled_alert(self, mock_alert_manager):
        """Test that fallback enabled triggers critical alert."""
        with patch(
            "src.monitoring.alerting.AlertManager",
            side_effect=lambda: mock_alert_manager,
        ):
            enable_fallback("liboqs_error")

            # Give async task time to complete
            await asyncio.sleep(0.1)

            # Verify alert was sent
            assert mock_alert_manager.send_alert.called
            call_args = mock_alert_manager.send_alert.call_args
            assert call_args[0][0] == "PQC_FALLBACK_ENABLED"
            assert call_args[0][1].value == "critical"

            # Cleanup
            disable_fallback()

    @pytest.mark.asyncio
    async def test_fallback_ttl_expired_alert(self, mock_alert_manager):
        """Test that fallback TTL expiration triggers critical alert."""
        with patch(
            "src.monitoring.alerting.AlertManager",
            side_effect=lambda: mock_alert_manager,
        ):
            with patch("src.monitoring.pqc_metrics.time.time") as mock_time:
                # Use real numerical values for time
                current_time = 1000.0
                mock_time.return_value = current_time

                # Enable fallback
                enable_fallback("test")

                # Fast forward time beyond TTL
                mock_time.return_value = current_time + FALLBACK_TTL + 1

                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.is_running.return_value = False
                    mock_loop.return_value.run_until_complete = asyncio.run

                    expired = check_fallback_ttl()

                    # Give async task time to complete
                    await asyncio.sleep(0.1)

                    # Verify TTL expired
                    assert expired is True

                    # Verify alert was sent
                    assert mock_alert_manager.send_alert.called
                    call_args = mock_alert_manager.send_alert.call_args
                    assert call_args[0][0] == "PQC_FALLBACK_TTL_EXPIRED"
                    assert call_args[0][1].value == "critical"

    @pytest.mark.asyncio
    async def test_key_rotation_failure_alert(self, mock_alert_manager):
        """Test that key rotation failure triggers high severity alert."""
        with patch(
            "src.monitoring.alerting.AlertManager",
            side_effect=lambda: mock_alert_manager,
        ):
            record_key_rotation_failure("key_generation_failed")

            # Give async task time to complete
            await asyncio.sleep(0.1)

            # Verify alert was sent
            assert mock_alert_manager.send_alert.called
            call_args = mock_alert_manager.send_alert.call_args
            assert call_args[0][0] == "PQC_KEY_ROTATION_FAILURE"
            assert call_args[0][1].value == "error"

    def test_handshake_success_no_alert_on_normal_latency(self):
        """Test that normal latency doesn't trigger alert."""
        normal_latency = PQC_HANDSHAKE_P95_LATENCY_SLO - 0.01  # 90ms < 100ms

        with patch("src.monitoring.alerting.send_alert_sync") as mock_send_alert:
            record_handshake_success(normal_latency)

            # Verify alert was not sent
            assert not mock_send_alert.called
