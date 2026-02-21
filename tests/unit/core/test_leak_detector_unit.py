"""Unit tests for Core Leak Detection Engine."""
import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

# Mock config.settings before importing leak_detector
mock_settings = MagicMock()
mock_settings.detection.expected_exit_ips = {"1.2.3.4"}
mock_settings.detection.expected_dns_servers = {"8.8.8.8"}

with patch.dict("sys.modules", {"config": MagicMock(), "config.settings": MagicMock(settings=mock_settings)}):
    # Also need structlog
    try:
        import structlog
    except ImportError:
        pass

    from src.core.leak_detector import (
        LeakSeverity,
        LeakType,
        LeakEvent,
        DetectionResult,
        IPLeakDetector,
        DNSLeakDetector,
        WebRTCLeakDetector,
        IPv6LeakDetector,
    )


class TestLeakEnums:
    def test_severity_values(self):
        assert LeakSeverity.INFO.value == "info"
        assert LeakSeverity.WARNING.value == "warning"
        assert LeakSeverity.CRITICAL.value == "critical"

    def test_leak_type_values(self):
        assert LeakType.IP_LEAK.value == "ip_leak"
        assert LeakType.DNS_LEAK.value == "dns_leak"
        assert LeakType.WEBRTC_LEAK.value == "webrtc_leak"
        assert LeakType.IPV6_LEAK.value == "ipv6_leak"


class TestLeakEvent:
    def test_create_event(self):
        event = LeakEvent(
            timestamp=datetime.utcnow(),
            leak_type=LeakType.IP_LEAK,
            severity=LeakSeverity.CRITICAL,
            message="IP leak detected",
            detected_value="5.6.7.8",
            expected_value="1.2.3.4",
            source_ip="5.6.7.8",
        )
        assert event.leak_type == LeakType.IP_LEAK
        assert not event.resolved

    def test_to_dict(self):
        event = LeakEvent(
            timestamp=datetime(2026, 1, 1, 12, 0),
            leak_type=LeakType.DNS_LEAK,
            severity=LeakSeverity.WARNING,
            message="DNS leak",
            detected_value="9.9.9.9",
            expected_value="8.8.8.8",
            source_ip=None,
            detected_country="US",
        )
        d = event.to_dict()
        assert d["leak_type"] == "dns_leak"
        assert d["severity"] == "warning"
        assert d["detected_country"] == "US"
        assert d["timestamp"] == "2026-01-01T12:00:00"


class TestDetectionResult:
    def test_create_ok(self):
        result = DetectionResult(
            check_type="ip_leak",
            status="ok",
            response_time_ms=50.0,
        )
        assert result.status == "ok"
        assert result.leaks == []

    def test_create_with_leaks(self):
        leak = LeakEvent(
            timestamp=datetime.utcnow(),
            leak_type=LeakType.IP_LEAK,
            severity=LeakSeverity.CRITICAL,
            message="test",
            detected_value="1.1.1.1",
            expected_value="2.2.2.2",
            source_ip="1.1.1.1",
        )
        result = DetectionResult(
            check_type="ip_leak",
            status="leak_detected",
            response_time_ms=100.0,
            leaks=[leak],
        )
        assert len(result.leaks) == 1


class TestIPLeakDetector:
    def test_init(self):
        detector = IPLeakDetector(expected_exit_ips={"1.2.3.4"})
        assert "1.2.3.4" in detector.expected_exit_ips

    @pytest.mark.asyncio
    async def test_check_no_leak(self):
        detector = IPLeakDetector(expected_exit_ips={"1.2.3.4"})
        mock_session = MagicMock()

        # Mock all servers to return expected IP
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=json.dumps({"ip": "1.2.3.4"}))
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await detector.check(mock_session)
        assert result.check_type == "ip_leak"

    @pytest.mark.asyncio
    async def test_check_single_server_leak(self):
        detector = IPLeakDetector(expected_exit_ips={"1.2.3.4"})
        mock_session = MagicMock()

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=json.dumps({"ip": "5.6.7.8", "country": "US"}))

        # Build proper async context manager
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(return_value=ctx)

        leak = await detector._check_single_server(mock_session, "https://test.com/json", "test")
        assert leak is not None
        assert leak.leak_type == LeakType.IP_LEAK
        assert leak.detected_value == "5.6.7.8"

    @pytest.mark.asyncio
    async def test_check_single_server_no_leak(self):
        detector = IPLeakDetector(expected_exit_ips={"1.2.3.4"})
        mock_session = MagicMock()

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value=json.dumps({"ip": "1.2.3.4"}))
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        leak = await detector._check_single_server(mock_session, "https://test.com/json", "test")
        assert leak is None


class TestDNSLeakDetector:
    def test_init(self):
        detector = DNSLeakDetector(expected_dns_servers={"8.8.8.8"})
        assert "8.8.8.8" in detector.expected_dns_servers


class TestWebRTCLeakDetector:
    def test_init(self):
        detector = WebRTCLeakDetector()
        assert detector.logger is not None


class TestIPv6LeakDetector:
    def test_init(self):
        detector = IPv6LeakDetector()
        assert detector.logger is not None
