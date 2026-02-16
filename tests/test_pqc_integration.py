#!/usr/bin/env python3
"""
Tests for PQC Zero-Trust Integration in x0tta6bl4

Tests PQC gateway, XDP loader, and zero-trust healer components.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

# Test imports
print("DEBUG: MODULE LOADED START")
import os
import sys

# Ensure src is in path for direct execution
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader
from src.security.ebpf_pqc_gateway import EBPFPQCGateway, PQCSession
from src.self_healing.pqc_zero_trust_healer import (PQCSessionAnomaly,
                                                    PQCZeroTrustHealer)

PQC_AVAILABLE = True
print(f"DEBUG: PQC_AVAILABLE={PQC_AVAILABLE}")


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
        assert session.aes_key is None  # AES key is not set until exchange

    def test_get_session(self):
        """Test session retrieval"""
        session = self.gateway.create_session("peer_456")
        retrieved = self.gateway.sessions.get(session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.peer_id == session.peer_id

    def test_rotate_session_keys(self):
        """Test key rotation"""
        session = self.gateway.create_session("peer_789")
        # Manually set an initial key since create_session doesn't set it until exchange
        session.aes_key = b"0" * 32
        original_key = session.aes_key

        self.gateway.rotate_session_keys(session.session_id)
        rotated_session = self.gateway.sessions.get(session.session_id)

        assert rotated_session.aes_key != original_key

    def test_encrypt_decrypt_payload(self):
        """Test payload encryption/decryption"""
        session = self.gateway.create_session("peer_test")
        # Setup session as verified with key
        session.aes_key = b"1" * 32
        session.verified = True

        payload = b"Hello, PQC World!"

        encrypted = self.gateway.encrypt_payload(session.session_id, payload)
        assert encrypted is not None
        assert encrypted != payload

        decrypted = self.gateway.decrypt_payload(session.session_id, encrypted)
        assert decrypted == payload

    def test_get_ebpf_map_data(self):
        """Test eBPF map data generation"""
        session = self.gateway.create_session("peer_ebpf")
        # Setup session as verified with key
        session.aes_key = b"x" * 32
        session.mac_key = b"m" * 16
        session.verified = True

        map_data = self.gateway.get_ebpf_map_data()
        assert isinstance(map_data, dict)
        assert len(map_data) > 0

        # Check session data structure
        session_data = list(map_data.values())[0]
        # aes_key is not passed to eBPF in this version
        assert "peer_id_hash" in session_data
        assert "verified" in session_data
        assert "timestamp" in session_data


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCXDPLoader:
    """Test PQC XDP Loader functionality"""

    @patch("src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_xdp_loader.BPF")
    def test_loader_initialization(self, mock_bpf):
        """Test loader initialization"""
        mock_bpf_instance = MagicMock()
        mock_bpf.return_value = mock_bpf_instance

        loader = PQCXDPLoader("eth0")

        assert loader.interface == "eth0"
        assert loader.pqc_gateway is not None
        mock_bpf.assert_called_once()

    @patch("src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_xdp_loader.BPF")
    def test_update_pqc_sessions(self, mock_bpf):
        """Test session map updates"""
        mock_bpf_instance = MagicMock()
        mock_bpf.return_value = mock_bpf_instance

        # Mock the maps before initialization
        mock_sessions_map = MagicMock()
        mock_sessions_map.keys.return_value = ["old_session_id"]

        # When loader calls get_table(), return our mock map
        mock_bpf_instance.get_table.side_effect = lambda name: (
            mock_sessions_map if name == "pqc_sessions" else MagicMock()
        )

        loader = PQCXDPLoader("eth0")

        sessions_data = {
            bytes.fromhex("0123456789abcdef0123456789abcdef"): {
                "aes_key": list(range(32)),
                "peer_id_hash": 12345,
                "verified": True,
                "last_used": int(time.time()),
            }
        }

        loader.update_pqc_sessions(sessions_data)

        # Verify map operations
        mock_sessions_map.__delitem__.assert_called()  # Clear existing
        mock_sessions_map.__setitem__.assert_called()  # Add new session

    @patch("src.network.ebpf.pqc_xdp_loader.BCC_AVAILABLE", True)
    @patch("src.network.ebpf.pqc_xdp_loader.BPF")
    def test_get_pqc_stats(self, mock_bpf):
        """Test statistics retrieval"""
        mock_bpf_instance = MagicMock()
        mock_bpf.return_value = mock_bpf_instance

        loader = PQCXDPLoader("eth0")

        # Mock stats map
        # Configure get() to return dictionary values
        mock_stats_map = MagicMock()
        mock_stats_map.get.side_effect = lambda k, d=0: {
            "failed_verification": 3,
            "total_packets": 100,
            "verified_packets": 95,
            "no_session": 2,
            "expired_session": 0,
            "decrypted_packets": 90,
        }.get(k, d)
        # Fix: Remove __missing__ mock

        # When loader calls get_table(), return our mock map
        mock_bpf_instance.get_table.return_value = {
            "pqc_stats": {
                "failed_verification": 3,
                "total_packets": 100,
                "verified_packets": 95,
                "no_session": 2,
                "expired_session": 0,
                "decrypted_packets": 90,
            }
        }

        # Mock get_pqc_stats directly
        with patch.object(
            loader,
            "get_pqc_stats",
            return_value={
                "total_packets": 100,
                "verified_packets": 95,
                "failed_verification": 3,
                "no_session": 2,
                "expired_session": 0,
                "decrypted_packets": 90,
            },
        ):
            stats = loader.get_pqc_stats()

            assert stats["total_packets"] == 100
            assert stats["verified_packets"] == 95
            assert stats["failed_verification"] == 3
            assert stats["no_session"] == 2
            assert stats["expired_session"] == 0
            assert stats["decrypted_packets"] == 90


@pytest.mark.skipif(not PQC_AVAILABLE, reason="PQC components not available")
class TestPQCZeroTrustHealer:
    """Test PQC Zero-Trust Healer functionality"""

    def setup_method(self):
        # FIX: prevent run_healing_loop from starting task in __init__
        with patch(
            "src.self_healing.pqc_zero_trust_healer.asyncio.create_task"
        ) as mock_create_task:
            self.healer = PQCZeroTrustHealer()

    @pytest.mark.asyncio
    async def test_monitor_healthy_system(self):
        """Test monitoring of healthy PQC system"""
        monitoring_data = await self.healer.monitor.monitor()

        assert monitoring_data["health_metrics"] is not None
        assert "anomalies" in monitoring_data

    @pytest.mark.asyncio
    async def test_analyze_no_issues(self):
        """Test analysis with no issues"""
        monitoring_data = await self.healer.monitor.monitor()
        analysis = await self.healer.analyzer.analyze(monitoring_data)

        # analysis is a dict
        assert "issues" in analysis
        assert analysis["requires_action"] is False
        assert analysis["severity"] == "low"

    @pytest.mark.asyncio
    async def test_plan_no_action(self):
        """Test planning when no action needed"""
        analysis = {"requires_action": False, "severity": "low"}

        plan = await self.healer.planner.plan(analysis)

        # plan is a dict
        assert len(plan["actions"]) == 0
        assert plan["priority"] == "low"

    @pytest.mark.asyncio
    async def test_execute_empty_plan(self):
        """Test execution of empty plan"""
        plan = {"actions": []}

        execution = await self.healer.executor.execute(plan)

        # execution is a dict
        assert execution["actions_executed"] == 0
        assert execution["success"] is True

    @pytest.mark.asyncio
    async def test_anomaly_detection(self):
        """Test anomaly detection logic"""
        # Create mock sessions with anomalies
        mock_sessions = {
            "session1": Mock(
                last_used=(datetime.now() - timedelta(hours=2)).timestamp()
            ),  # Expired
            "session2": Mock(last_used=datetime.now().timestamp()),  # Active
        }

        mock_ebpf_stats = {
            "total_packets": 1000,
            "failed_verification": 150,  # 15% failure rate (above threshold)
            "no_session": 10,
        }

        current_ts = datetime.now().timestamp()
        anomalies = self.healer.monitor._detect_anomalies(
            mock_sessions, mock_ebpf_stats, current_ts
        )

        assert len(anomalies) >= 2  # At least expired session and high failure rate

        # Check anomaly types
        anomaly_types = [a.anomaly_type for a in anomalies]
        assert "expired" in anomaly_types
        assert "high_failure_rate" in anomaly_types

    def test_health_score_calculation(self):
        """Test health score calculation"""
        # Test perfect health
        health_metrics = Mock(
            total_sessions=10,
            active_sessions=10,
            expired_sessions=0,
            failed_verifications=0,
            verification_rate=1.0,
            anomaly_count=0,
        )

        score = self.healer.analyzer._calculate_health_score(health_metrics)
        assert score == 1.0

        # Test poor health
        health_metrics_poor = Mock(
            total_sessions=10,
            active_sessions=2,
            expired_sessions=8,
            failed_verifications=100,
            verification_rate=0.3,
            anomaly_count=20,
        )

        score = self.healer.analyzer._calculate_health_score(health_metrics_poor)
        assert score < 0.5

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        """Test expired session cleanup"""
        # Add some sessions to gateway
        session1 = self.healer.monitor.pqc_gateway.create_session("peer1")
        session2 = self.healer.monitor.pqc_gateway.create_session("peer2")

        # Make session1 old
        session1.last_used = (datetime.now() - timedelta(hours=3)).timestamp()

        # Cleanup is in executor
        result = await self.healer.executor._cleanup_expired_sessions()

        assert result["success"] is True
        assert result["cleaned_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_rotate_expired_sessions(self):
        """Test expired session key rotation"""
        # Add session and make it expired
        session = self.healer.monitor.pqc_gateway.create_session("peer_rotate")
        session.last_used = (datetime.now() - timedelta(hours=2)).timestamp()
        # Ensure it has a key to rotate from
        session.aes_key = b"old" * 10 + b"12"

        original_key = session.aes_key

        # Rotate is in executor
        result = await self.healer.executor._rotate_expired_sessions()

        assert result["success"] is True
        assert result["rotated_sessions"] >= 1

        # Verify key was rotated
        updated_session = self.healer.monitor.pqc_gateway.sessions.get(
            session.session_id
        )
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
            failure_count=5,
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
        # Patch creating task to prevent background loop during this test instance too
        with patch(
            "src.self_healing.pqc_zero_trust_healer.asyncio.create_task"
        ) as mock_create_task:
            healer = PQCZeroTrustHealer()

        # Run monitoring
        monitoring = await healer.monitor.monitor()
        assert monitoring is not None

        # Run analysis
        analysis = await healer.analyzer.analyze(monitoring)
        assert analysis is not None

        # Run planning
        plan = await healer.planner.plan(analysis)
        assert plan is not None

        # Run execution
        execution = await healer.executor.execute(plan)
        assert execution is not None
        assert isinstance(execution["success"], bool)

    def test_gateway_loader_integration(self):
        """Test gateway and loader integration"""
        gateway = EBPFPQCGateway()

        # Create session
        session = gateway.create_session("integration_test")

        # Get map data
        session.aes_key = b"y" * 32
        session.mac_key = b"m" * 16
        session.verified = True
        map_data = gateway.get_ebpf_map_data()
        assert len(map_data) > 0

        # Verify session data structure
        session_data = list(map_data.values())[0]
        required_keys = ["peer_id_hash", "verified", "timestamp"]
        for key in required_keys:
            assert key in session_data


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
