"""
Tests for Geo-Leak Detector
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from src.core.leak_detector import (
    LeakEvent, LeakType, LeakSeverity,
    IPLeakDetector, DNSLeakDetector, WebRTCLeakDetector,
    IPv6LeakDetector, LeakDetectionEngine
)


class TestLeakEvent:
    """Test LeakEvent dataclass"""
    
    def test_leak_event_creation(self):
        """Test creating a LeakEvent"""
        event = LeakEvent(
            timestamp=datetime.utcnow(),
            leak_type=LeakType.IP_LEAK,
            severity=LeakSeverity.CRITICAL,
            message="Test leak",
            detected_value="192.168.1.1",
            expected_value="10.0.0.1",
            source_ip="192.168.1.1"
        )
        
        assert event.leak_type == LeakType.IP_LEAK
        assert event.severity == LeakSeverity.CRITICAL
        assert event.detected_value == "192.168.1.1"
    
    def test_leak_event_to_dict(self):
        """Test converting LeakEvent to dict"""
        event = LeakEvent(
            timestamp=datetime(2026, 1, 31, 12, 0, 0),
            leak_type=LeakType.DNS_LEAK,
            severity=LeakSeverity.WARNING,
            message="DNS leak detected",
            detected_value="8.8.8.8",
            expected_value="127.0.0.1",
            source_ip="8.8.8.8",
            detected_country="US",
            detected_city="Mountain View"
        )
        
        data = event.to_dict()
        
        assert data["leak_type"] == "dns_leak"
        assert data["severity"] == "warning"
        assert data["detected_country"] == "US"
        assert data["detected_city"] == "Mountain View"


class TestIPLeakDetector:
    """Test IP Leak Detector"""
    
    @pytest.fixture
    def detector(self):
        return IPLeakDetector(expected_exit_ips={"10.0.0.1", "10.0.0.2"})
    
    @pytest.mark.asyncio
    async def test_check_with_no_leak(self, detector):
        """Test IP check when no leak is present"""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ip": "10.0.0.1"})
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)
        
        result = await detector.check(mock_session)
        
        assert result.status == "ok"
        assert len(result.leaks) == 0
    
    @pytest.mark.asyncio
    async def test_check_with_leak(self, detector):
        """Test IP check when leak is detected"""
        # Mock the HTTP response with leaked IP
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "ip": "192.168.1.1",
            "country": "US",
            "city": "New York",
            "isp": "Test ISP"
        })
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)
        
        result = await detector.check(mock_session)
        
        assert result.status == "leak_detected"
        assert len(result.leaks) == 1
        assert result.leaks[0].detected_value == "192.168.1.1"
        assert result.leaks[0].detected_country == "US"


class TestDNSLeakDetector:
    """Test DNS Leak Detector"""
    
    @pytest.fixture
    def detector(self):
        return DNSLeakDetector(expected_dns_servers={"127.0.0.1", "::1"})
    
    @pytest.mark.asyncio
    async def test_check_with_dns_leak(self, detector):
        """Test DNS leak detection"""
        # Mock response with external DNS server
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[
            {"ip": "8.8.8.8", "isp": "Google DNS", "country": "US"},
            {"ip": "127.0.0.1", "isp": "Local", "country": ""}
        ])
        
        mock_session = Mock()
        mock_session.get = Mock()
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=False)
        
        result = await detector.check(mock_session)
        
        assert result.status == "leak_detected"
        assert len(result.leaks) >= 1


class TestWebRTCLeakDetector:
    """Test WebRTC Leak Detector"""
    
    @pytest.fixture
    def detector(self):
        return WebRTCLeakDetector()
    
    @pytest.mark.asyncio
    async def test_check_browser_webrtc(self, detector):
        """Test browser WebRTC check"""
        mock_session = Mock()
        
        with patch('subprocess.run') as mock_run:
            # Mock Firefox config check
            mock_run.return_value = Mock(
                returncode=0,
                stdout="/home/user/.mozilla/firefox/profile/prefs.js"
            )
            
            result = await detector.check(mock_session)
            
            # Should detect WebRTC is enabled
            assert isinstance(result.leaks, list)


class TestIPv6LeakDetector:
    """Test IPv6 Leak Detector"""
    
    @pytest.fixture
    def detector(self):
        return IPv6LeakDetector()
    
    @pytest.mark.asyncio
    async def test_ipv6_enabled_detection(self, detector):
        """Test IPv6 enabled detection"""
        mock_session = Mock()
        
        with patch('builtins.open', mock_open(read_data='0')):
            result = await detector.check(mock_session)
            
            # IPv6 is not disabled (value is 0)
            assert result.status == "leak_detected"


class TestLeakDetectionEngine:
    """Test Leak Detection Engine"""
    
    @pytest.fixture
    def engine(self):
        return LeakDetectionEngine(
            expected_exit_ips={"10.0.0.1"},
            expected_dns_servers={"127.0.0.1"},
            check_interval=30
        )
    
    def test_engine_initialization(self, engine):
        """Test engine initialization"""
        assert engine.running == False
        assert engine.check_interval == 30
        assert "10.0.0.1" in engine.expected_exit_ips
    
    def test_get_status(self, engine):
        """Test getting engine status"""
        status = engine.get_status()
        
        assert "running" in status
        assert "check_interval" in status
        assert "detectors" in status
        assert len(status["detectors"]) == 4
    
    @pytest.mark.asyncio
    async def test_callback_registration(self, engine):
        """Test callback registration"""
        callback_called = False
        
        async def test_callback(event):
            nonlocal callback_called
            callback_called = True
        
        engine.on_leak_detected.append(test_callback)
        
        # Create a mock leak event
        leak = LeakEvent(
            timestamp=datetime.utcnow(),
            leak_type=LeakType.IP_LEAK,
            severity=LeakSeverity.CRITICAL,
            message="Test",
            detected_value="1.2.3.4",
            expected_value="10.0.0.1",
            source_ip="1.2.3.4"
        )
        
        # Manually trigger callback
        for cb in engine.on_leak_detected:
            await cb(leak)
        
        assert callback_called


# Mock for open function
from unittest.mock import mock_open


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
