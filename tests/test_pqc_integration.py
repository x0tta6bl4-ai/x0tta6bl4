#!/usr/bin/env python3
"""
Tests for PQC Zero-Trust Integration in x0tta6bl4

Tests PQC gateway, XDP loader, and zero-trust healer components.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Test imports
try:
    from src.security.ebpf_pqc_gateway import EBPFPQCGateway, PQCSession
    from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader
    from src.self_healing.pqc_zero_trust_healer import PQCZeroTrustHealer, PQCSessionAnomaly
    PQC_AVAILABLE = True
except ImportError as e:
    PQC_AVAILABLE = False
    print(f"PQC components not available: {e}")

@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestEBPFPQCGateway:
    """Test PQC Gateway functionality"""

    def setup_method(self):
        self.gateway = EBPFPQCGateway()

    def test_create_session(self):
        """Test session creation"""
        session = self.gateway.create_session("peer_123")

        assert session.session_id is not None
        assert session.peer_id == "peer_123"
        assert session.verified is False
        assert session.aes_key is not None
        assert len(session.aes_key) == 32

    def test_get_session(self):
        """Test session retrieval"""
        session = self.gateway.create_session("peer_456")
        retrieved = self.gateway.get_session(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.peer_id == session.peer_id

    def test_rotate_session_keys(self):
        """Test key rotation"""
        session = self.gateway.create_session("peer_789")
        original_key = session.aes_key.copy()

        self.gateway.rotate_session_keys(session.session_id)
        rotated_session = self.gateway.get_session(session.session_id)

        assert rotated_session.aes_key != original_key

    def test_encrypt_decrypt_payload(self):
        """Test payload encryption/decryption"""
        session = self.gateway.create_session("peer_test")
        payload = b"Hello, PQC World!"

        encrypted = self.gateway.encrypt_payload(session.session_id, payload)
        assert encrypted is not None
        assert encrypted != payload

        decrypted = self.gateway.decrypt_payload(session.session_id, encrypted)
        assert decrypted == payload

    def test_get_ebpf_map_data(self):
        """Test eBPF map data generation"""
        session = self.gateway.create_session("peer_ebpf")

        map_data = self.gateway.get_ebpf_map_data()
        assert isinstance(map_data, dict)
        assert len(map_data) > 0

        # Check session data structure
        session_data = list(map_data.values())[0]
        assert 'aes_key' in session_data
        assert 'peer_id_hash' in session_data
        assert 'verified' in session_data
        assert 'timestamp' in session_data

@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCXDPLoader:
    """Test PQC XDP Loader functionality"""

    @patch('src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE', True)
    @patch('src.network.ebpf.pqc_xdp_loader.BPF')
    def test_loader_initialization(self, mock_bpf):
        """Test loader initialization"""
        mock_bpf_instance = MagicMock()
        mock_bpf.return_value = mock_bpf_instance

        loader = PQCXDPLoader("eth0")

        assert loader.interface == "eth0"
        assert loader.pqc_gateway is not None
        mock_bpf.assert_called_once()

    @patch('src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE', True)
    @patch('src.network.ebpf.pqc_xdp_loader.BPF')
    def test_update_pqc_sessions(self, mock_bpf):
        """Test session map updates"""
        mock_bpf_instance = MagicMock()
        mock_bpf.return_value = mock_bpf_instance

        loader = PQCXDPLoader("eth0")

        # Mock the maps
        mock_sessions_map = MagicMock()
        mock_bpf_instance.get_table.return_value = mock_sessions_map

        sessions_data = {
            "0123456789abcdef0123456789abcdef": {
                'aes_key': list(range(32)),
                'peer_id_hash': 12345,
                'verified': True,
                'last_used': int(time.time())
            }
        }

        loader.update_pqc_sessions(sessions_data)

        # Verify map operations
        mock_sessions_map.__delitem__.assert_called()  # Clear existing
        mock_sessions_map.__setitem__.assert_called()  # Add new session

    @patch('src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE', True)
    @patch('src.network.ebpf.pqc_xdp_loader.BPF')
    def test_get_pqc_stats(self, mock_bpf):
        """Test statistics retrieval"""
        mock_bpf_instance = MagicMock()
        mock_bpf.return_value = mock_bpf_instance

        loader = PQCXDPLoader("eth0")

        # Mock stats map
        mock_stats_map = MagicMock()
        mock_stats_map.__getitem__.side_effect = lambda k: [100, 95, 3, 2, 0, 90][k]
        mock_bpf_instance.get_table.return_value = mock_stats_map

        stats = loader.get_pqc_stats()

        assert stats['total_packets'] == 100
        assert stats['verified_packets'] == 95
        assert stats['failed_verification'] == 3
        assert stats['no_session'] == 2
        assert stats['expired_session'] == 0
        assert stats['decrypted_packets'] == 90

@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCZeroTrustHealer:
    """Test PQC Zero-Trust Healer functionality"""

    def setup_method(self):
        self.healer = PQCZeroTrustHealer()

    @pytest.mark.asyncio
    async def test_monitor_healthy_system(self):
        """Test monitoring of healthy PQC system"""
        monitoring_data = await self.healer.monitor()

        assert monitoring_data.component == "PQC Zero-Trust"
        assert 'health_metrics' in monitoring_data.metrics
        assert 'anomalies' in monitoring_data.metrics
        assert isinstance(monitoring_data.health_score, float)

    @pytest.mark.asyncio
    async def test_analyze_no_issues(self):
        """Test analysis with no issues"""
        monitoring_data = await self.healer.monitor()
        analysis = await self.healer.analyze(monitoring_data)

        assert analysis.component == "PQC Zero-Trust"
        assert analysis.requires_action is False
        assert analysis.severity == "low"

    @pytest.mark.asyncio
    async def test_plan_no_action(self):
        """Test planning when no action needed"""
        analysis = Mock()
        analysis.requires_action = False
        analysis.severity = "low"

        plan = await self.healer.plan(analysis)

        assert plan.component == "PQC Zero-Trust"
        assert len(plan.actions) == 0
        assert plan.priority == "low"

    @pytest.mark.asyncio
    async def test_execute_empty_plan(self):
        """Test execution of empty plan"""
        plan = Mock()
        plan.actions = []

        execution = await self.healer.execute(plan)

        assert execution.component == "PQC Zero-Trust"
        assert execution.actions_executed == 0
        assert execution.success is True

    @pytest.mark.asyncio
    async def test_anomaly_detection(self):
        """Test anomaly detection logic"""
        # Create mock sessions with anomalies
        mock_sessions = {
            'session1': Mock(last_used=datetime.now() - timedelta(hours=2)),  # Expired
            'session2': Mock(last_used=datetime.now())  # Active
        }

        mock_ebpf_stats = {
            'total_packets': 1000,
            'failed_verification': 150,  # 15% failure rate (above threshold)
            'no_session': 10
        }

        current_time = datetime.now()
        anomalies = self.healer._detect_anomalies(mock_sessions, mock_ebpf_stats, current_time)

        assert len(anomalies) >= 2  # At least expired session and high failure rate

        # Check anomaly types
        anomaly_types = [a.anomaly_type for a in anomalies]
        assert 'expired' in anomaly_types
        assert 'high_failure_rate' in anomaly_types

    def test_health_score_calculation(self):
        """Test health score calculation"""
        # Test perfect health
        self.healer.health_metrics = Mock(
            total_sessions=10,
            active_sessions=10,
            expired_sessions=0,
            failed_verifications=0,
            verification_rate=1.0,
            anomaly_count=0
        )

        score = self.healer._calculate_health_score()
        assert score == 1.0

        # Test poor health
        self.healer.health_metrics = Mock(
            total_sessions=10,
            active_sessions=2,
            expired_sessions=8,
            failed_verifications=100,
            verification_rate=0.3,
            anomaly_count=20
        )

        score = self.healer._calculate_health_score()
        assert score < 0.5

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        """Test expired session cleanup"""
        # Add some sessions
        session1 = self.healer.pqc_gateway.create_session("peer1")
        session2 = self.healer.pqc_gateway.create_session("peer2")

        # Make session1 old
        session1.last_used = datetime.now() - timedelta(hours=3)

        result = await self.healer._cleanup_expired_sessions()

        assert result['success'] is True
        assert result['cleaned_sessions'] >= 1

    @pytest.mark.asyncio
    async def test_rotate_expired_sessions(self):
        """Test expired session key rotation"""
        # Add session and make it expired
        session = self.healer.pqc_gateway.create_session("peer_rotate")
        session.last_used = datetime.now() - timedelta(hours=2)

        original_key = session.aes_key.copy()

        result = await self.healer._rotate_expired_sessions()

        assert result['success'] is True
        assert result['rotated_sessions'] >= 1

        # Verify key was rotated
        updated_session = self.healer.pqc_gateway.get_session(session.session_id)
        assert updated_session.aes_key != original_key

class TestPQCSessionAnomaly:
    """Test PQC Session Anomaly dataclass"""

    def test_anomaly_creation(self):
        """Test anomaly object creation"""
        anomaly = PQCSessionAnomaly(
            session_id="test_session",
            anomaly_type="expired",
            severity="medium",
            description="Test anomaly",
            timestamp=datetime.now(),
            peer_id="peer123",
            failure_count=5
        )

        assert anomaly.session_id == "test_session"
        assert anomaly.anomaly_type == "expired"
        assert anomaly.severity == "medium"
        assert anomaly.peer_id == "peer123"
        assert anomaly.failure_count == 5

@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestIntegration:
    """Integration tests for PQC components"""

    @pytest.mark.asyncio
    async def test_full_healing_cycle(self):
        """Test complete MAPE-K healing cycle"""
        healer = PQCZeroTrustHealer()

        # Run monitoring
        monitoring = await healer.monitor()
        assert monitoring is not None

        # Run analysis
        analysis = await healer.analyze(monitoring)
        assert analysis is not None

        # Run planning
        plan = await healer.plan(analysis)
        assert plan is not None

        # Run execution
        execution = await healer.execute(plan)
        assert execution is not None
        assert isinstance(execution.success, bool)

    def test_gateway_loader_integration(self):
        """Test gateway and loader integration"""
        gateway = EBPFPQCGateway()

        # Create session
        session = gateway.create_session("integration_test")

        # Get map data
        map_data = gateway.get_ebpf_map_data()
        assert len(map_data) > 0

        # Verify session data structure
        session_data = list(map_data.values())[0]
        required_keys = ['aes_key', 'peer_id_hash', 'verified', 'timestamp']
        for key in required_keys:
            assert key in session_data

if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])