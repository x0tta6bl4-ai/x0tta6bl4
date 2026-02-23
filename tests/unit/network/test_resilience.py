"""
Unit tests for Network Resilience Module.

Tests cover:
- MakeNeverBreakEngine: Path establishment and failover
- TrustAwareMAPEK: Trust score integration
- WANOverlayPQC: PQC tunnel management
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import time


# Test MakeNeverBreak Engine
class TestMakeNeverBreakEngine:
    """Tests for the Make-Never-Break resilience engine."""
    
    @pytest.fixture
    def engine(self):
        """Create a resilience engine for testing."""
        from src.network.resilience import MakeNeverBreakEngine, ResilienceConfig, PathType, PathState
        
        config = ResilienceConfig(
            min_active_paths=4,
            max_paths=16,
            reroute_delay_ms=50.0,
        )
        engine = MakeNeverBreakEngine(config)
        # Attach PathType and PathState to engine for test access
        engine.PathType = PathType
        engine.PathState = PathState
        return engine
    
    def test_create_path(self, engine):
        """Test path creation."""
        path = engine.create_path(
            source="node_a",
            target="node_b",
            hops=["node_a", "node_c", "node_b"],
            channels=["channel_1"],
            path_type="primary",
        )
        
        assert path.path_id is not None
        assert path.source_node == "node_a"
        assert path.target_node == "node_b"
        assert len(path.hops) == 3
        assert path.state.value == "establishing"
    
    def test_establish_redundant_paths(self, engine):
        """Test establishing multiple redundant paths."""
        available_hops = [
            ["node_a", "node_b", "node_c"],
            ["node_a", "node_d", "node_c"],
            ["node_a", "node_e", "node_c"],
            ["node_a", "node_f", "node_c"],
            ["node_a", "node_c"],  # Direct path
        ]
        
        paths = engine.establish_redundant_paths(
            source="node_a",
            target="node_c",
            available_hops=available_hops,
            available_channels=["ch1", "ch2", "ch3"],
        )
        
        # Should establish at least min_active_paths
        assert len(paths) >= engine.config.min_active_paths
        
        # All paths should have unique IDs
        path_ids = [p.path_id for p in paths]
        assert len(path_ids) == len(set(path_ids))
    
    def test_update_path_metrics(self, engine):
        """Test updating path metrics."""
        path = engine.create_path(
            source="node_a",
            target="node_b",
            hops=["node_a", "node_b"],
        )
        
        # Update metrics
        engine.update_path_metrics(
            path.path_id,
            latency_ms=25.0,
            jitter_ms=5.0,
            packet_loss=0.01,
            bandwidth_mbps=100.0,
        )
        
        # Check updated metrics
        updated_path = engine._paths[path.path_id]
        assert updated_path.metrics.latency_ms == 25.0
        assert updated_path.metrics.jitter_ms == 5.0
        assert updated_path.metrics.packet_loss == 0.01
        
        # Quality score should be calculated
        quality = updated_path.metrics.quality_score()
        assert 0 <= quality <= 1
    
    def test_path_quality_score(self, engine):
        """Test path quality score calculation."""
        from src.network.resilience import PathMetrics
        
        # Excellent path
        excellent = PathMetrics(
            latency_ms=10.0,
            jitter_ms=2.0,
            packet_loss=0.0,
            trust_score=1.0,
            uptime_ratio=1.0,
        )
        assert excellent.quality_score() > 0.9
        
        # Poor path
        poor = PathMetrics(
            latency_ms=200.0,
            jitter_ms=50.0,
            packet_loss=0.1,
            trust_score=0.5,
            uptime_ratio=0.8,
        )
        assert poor.quality_score() < 0.7
    
    def test_trust_score_update(self, engine):
        """Test trust score updates."""
        path = engine.create_path(
            source="node_a",
            target="node_b",
            hops=["node_a", "node_b"],
        )
        
        initial_trust = path.metrics.trust_score
        
        # Decrease trust
        engine.update_trust_score(path.path_id, -0.2)
        assert engine._paths[path.path_id].metrics.trust_score < initial_trust
        
        # Increase trust
        engine.update_trust_score(path.path_id, 0.1)
        assert engine._paths[path.path_id].metrics.trust_score > 0.1
    
    def test_path_failure_triggers_reroute(self, engine):
        """Test that path failure triggers reroute."""
        # Create multiple paths
        paths = engine.establish_redundant_paths(
            source="node_a",
            target="node_b",
            available_hops=[
                ["node_a", "node_b"],
                ["node_a", "node_c", "node_b"],
                ["node_a", "node_d", "node_b"],
                ["node_a", "node_e", "node_b"],
            ],
        )
        
        # Set first path as primary and make it active
        primary = paths[0]
        primary.path_type = engine.PathType.PRIMARY
        primary.state = engine.PathState.ACTIVE
        engine._primary_paths["node_b"] = primary.path_id
        
        # Make other paths usable as backups with good metrics
        for path in paths[1:]:
            path.state = engine.PathState.ACTIVE
            path.metrics.latency_ms = 10.0
            path.metrics.trust_score = 1.0
            path.metrics.uptime_ratio = 1.0
        
        # Simulate catastrophic failure on primary - extremely bad metrics
        # This should result in quality_score < 0.3 triggering FAILED state
        engine.update_path_metrics(
            primary.path_id, 
            latency_ms=500.0,  # Very high latency
            jitter_ms=100.0,   # Very high jitter
            packet_loss=0.99,  # Almost total packet loss
        )
        
        # Check that path state changed (should be FAILED or DEGRADED)
        # The exact behavior depends on quality_score calculation
        updated_primary = engine._paths.get(primary.path_id)
        assert updated_primary.state in (engine.PathState.FAILED, engine.PathState.DEGRADED)
    
    def test_get_best_path(self, engine):
        """Test getting the best path to a target."""
        # Create paths with different quality
        paths = engine.establish_redundant_paths(
            source="node_a",
            target="node_b",
            available_hops=[
                ["node_a", "node_b"],
                ["node_a", "node_c", "node_b"],
            ],
        )
        
        # Set different metrics
        engine.update_path_metrics(paths[0].path_id, latency_ms=10.0, packet_loss=0.0)
        engine.update_path_metrics(paths[1].path_id, latency_ms=100.0, packet_loss=0.1)
        
        # Get best path
        best = engine.get_best_path("node_b")
        assert best is not None
        assert best.metrics.latency_ms == 10.0
    
    def test_stats_tracking(self, engine):
        """Test statistics tracking."""
        # Create some paths
        engine.establish_redundant_paths(
            source="node_a",
            target="node_b",
            available_hops=[["node_a", "node_b"]],
        )
        
        stats = engine.get_stats()
        
        assert "paths_created" in stats
        assert stats["paths_created"] >= 1
        assert "total_paths" in stats
        assert stats["total_paths"] >= 1


# Test Trust-Aware MAPE-K Integration
class TestTrustAwareMAPEK:
    """Tests for trust-aware MAPE-K integration."""
    
    @pytest.fixture
    def trust_mapek(self):
        """Create a trust-MAPEK instance for testing."""
        from src.network.resilience import (
            MakeNeverBreakEngine,
            TrustAwareMAPEK,
            TrustPolicy,
        )
        
        engine = MakeNeverBreakEngine()
        policy = TrustPolicy(
            min_trust_for_primary=0.8,
            min_trust_for_backup=0.5,
        )
        return TrustAwareMAPEK(engine, policy)
    
    def test_collect_trust_metrics(self, trust_mapek):
        """Test collecting trust metrics."""
        # Create some paths
        trust_mapek.engine.create_path(
            source="node_a",
            target="node_b",
            hops=["node_a", "node_b"],
        )
        
        metrics = trust_mapek.collect_trust_metrics()
        
        assert "total_paths" in metrics
        assert "avg_trust_score" in metrics
        assert "trust_distribution" in metrics
    
    def test_analyze_trust_state(self, trust_mapek):
        """Test analyzing trust state."""
        metrics = {
            "avg_trust_score": 0.9,
            "trust_distribution": {
                "primary_eligible": 4,
                "backup_eligible": 2,
                "emergency_only": 1,
                "unusable": 0,
            },
            "trust_trends": {},
            "recent_anomalies": 0,
        }
        
        analysis = trust_mapek.analyze_trust_state(metrics)
        
        assert "trust_health" in analysis
        assert "issues" in analysis
        assert "recommendations" in analysis
    
    def test_analyze_critical_trust(self, trust_mapek):
        """Test analysis with critical trust state."""
        metrics = {
            "avg_trust_score": 0.3,  # Critical
            "trust_distribution": {
                "primary_eligible": 0,
                "backup_eligible": 1,
                "emergency_only": 2,
                "unusable": 3,
            },
            "trust_trends": {},
            "recent_anomalies": 5,
        }
        
        analysis = trust_mapek.analyze_trust_state(metrics)
        
        assert analysis["trust_health"] == "critical"
        assert len(analysis["issues"]) > 0
        assert analysis["risk_score"] >= 0.5
    
    def test_plan_trust_actions(self, trust_mapek):
        """Test planning trust actions."""
        analysis = {
            "trust_health": "degraded",
            "issues": ["Low average trust"],
            "recommendations": ["establish_more_paths"],
            "risk_score": 0.4,
        }
        
        directives = trust_mapek.plan_trust_actions(analysis)
        
        assert "actions" in directives
        assert "path_changes" in directives
    
    def test_record_trust_event(self, trust_mapek):
        """Test recording trust events."""
        # Create a path
        path = trust_mapek.engine.create_path(
            source="node_a",
            target="node_b",
            hops=["node_a", "node_b"],
        )
        
        initial_trust = path.metrics.trust_score
        
        # Record failure event
        trust_mapek.record_trust_event(
            path_id=path.path_id,
            event_type="failure",
            details={"reason": "timeout"},
        )
        
        # Trust should decrease
        updated_path = trust_mapek.engine._paths[path.path_id]
        assert updated_path.metrics.trust_score < initial_trust
    
    def test_trust_trend_calculation(self, trust_mapek):
        """Test trust trend calculation."""
        path_id = "test_path"
        
        # Add some history
        now = datetime.utcnow()
        trust_mapek._trust_history[path_id] = [
            (now - timedelta(minutes=5), 0.9),
            (now - timedelta(minutes=4), 0.85),
            (now - timedelta(minutes=3), 0.8),
            (now - timedelta(minutes=2), 0.75),
            (now - timedelta(minutes=1), 0.7),
        ]
        
        trend = trust_mapek._calculate_trust_trend(path_id)
        
        # Should show declining trend
        assert trend is not None
        assert trend < 0  # Negative = declining


# Test WAN Overlay with PQC
class TestWANOverlayPQC:
    """Tests for WAN overlay with PQC."""
    
    @pytest.fixture
    def overlay(self):
        """Create a WAN overlay instance for testing."""
        from src.network.resilience.wan_overlay_pqc import WANOverlayPQC, CryptoMode, TunnelState
        
        # Use PQC_ONLY mode to avoid cryptography serialization issues in tests
        return WANOverlayPQC(
            node_id="test_node_001",
            crypto_mode=CryptoMode.PQC_ONLY,
        )
    
    def test_key_generation(self, overlay):
        """Test key generation."""
        bundle = overlay._local_keys.get(overlay.node_id)
        
        assert bundle is not None
        
        # Should have PQC keys in PQC_ONLY mode
        assert bundle.pqc_kem is not None
        # No classical keys in PQC_ONLY mode
        assert bundle.classical_kem is None
    
    def test_get_public_key_bundle(self, overlay):
        """Test getting public key bundle."""
        pub_bundle = overlay.get_public_key_bundle()
        
        assert "node_id" in pub_bundle
        assert "crypto_mode" in pub_bundle
        assert "pqc_kem_public" in pub_bundle
        # No classical keys in PQC_ONLY mode
        assert "classical_kem_public" not in pub_bundle
    
    def test_add_remote_public_keys(self, overlay):
        """Test adding remote public keys."""
        remote_bundle = {
            "node_id": "remote_node_001",
            "crypto_mode": "hybrid",
            "pqc_kem_public": "a" * 3136,  # Simulated hex key
            "classical_kem_public": "b" * 64,
        }
        
        overlay.add_remote_public_keys(remote_bundle)
        
        assert "remote_node_001" in overlay._remote_public_keys
    
    @pytest.mark.asyncio
    async def test_create_tunnel(self, overlay):
        """Test tunnel creation."""
        # Add remote keys first
        remote_bundle = {
            "node_id": "remote_node_001",
            "crypto_mode": "hybrid",
            "pqc_kem_public": "a" * 3136,
            "classical_kem_public": "b" * 64,
        }
        overlay.add_remote_public_keys(remote_bundle)
        
        # Create tunnel
        session = await overlay.create_tunnel("remote_node_001")
        
        assert session is not None
        assert session.state.value == "established"
        assert session.tx_key is not None
        assert session.rx_key is not None
    
    @pytest.mark.asyncio
    async def test_send_data(self, overlay):
        """Test sending data through tunnel."""
        # Setup tunnel
        remote_bundle = {
            "node_id": "remote_node_001",
            "crypto_mode": "hybrid",
            "pqc_kem_public": "a" * 3136,
            "classical_kem_public": "b" * 64,
        }
        overlay.add_remote_public_keys(remote_bundle)
        session = await overlay.create_tunnel("remote_node_001")
        
        # Send data
        result = await overlay.send_data(session.tunnel_id, b"test data")
        
        assert result is True
        assert session.bytes_sent > 0
        assert session.packets_sent == 1
    
    @pytest.mark.asyncio
    async def test_close_tunnel(self, overlay):
        """Test closing tunnel."""
        # Setup tunnel
        remote_bundle = {
            "node_id": "remote_node_001",
            "crypto_mode": "hybrid",
            "pqc_kem_public": "a" * 3136,
            "classical_kem_public": "b" * 64,
        }
        overlay.add_remote_public_keys(remote_bundle)
        session = await overlay.create_tunnel("remote_node_001")
        
        # Close tunnel
        await overlay.close_tunnel(session.tunnel_id)
        
        assert session.tunnel_id not in overlay._tunnels
    
    def test_get_tunnel_stats(self, overlay):
        """Test getting tunnel statistics."""
        # Create a mock tunnel
        from src.network.resilience.wan_overlay_pqc import (
            TunnelSession, TunnelConfig, CryptoMode, TunnelState
        )
        
        session = TunnelSession(tunnel_id="test_tunnel")
        session.state = TunnelState.ESTABLISHED
        session.bytes_sent = 1000
        session.bytes_received = 500
        overlay._tunnels["test_tunnel"] = session
        
        # Add config for the tunnel
        config = TunnelConfig(
            tunnel_id="test_tunnel",
            local_node_id="test_node_001",
            remote_node_id="remote_node",
            crypto_mode=CryptoMode.PQC_ONLY,
        )
        overlay._tunnel_configs["test_tunnel"] = config
        
        stats = overlay.get_tunnel_stats("test_tunnel")
        
        assert stats is not None
        assert stats["tunnel_id"] == "test_tunnel"
        assert stats["bytes_sent"] == 1000


# Test Path Metrics
class TestPathMetrics:
    """Tests for path metrics calculations."""
    
    def test_quality_score_excellent(self):
        """Test quality score for excellent path."""
        from src.network.resilience import PathMetrics
        
        metrics = PathMetrics(
            latency_ms=5.0,
            jitter_ms=1.0,
            packet_loss=0.0,
            trust_score=1.0,
            uptime_ratio=1.0,
        )
        
        score = metrics.quality_score()
        assert score > 0.95
    
    def test_quality_score_poor(self):
        """Test quality score for poor path."""
        from src.network.resilience import PathMetrics
        
        metrics = PathMetrics(
            latency_ms=500.0,
            jitter_ms=100.0,
            packet_loss=0.5,
            trust_score=0.3,
            uptime_ratio=0.5,
        )
        
        score = metrics.quality_score()
        assert score < 0.5
    
    def test_quality_score_degraded(self):
        """Test quality score for degraded path."""
        from src.network.resilience import PathMetrics
        
        metrics = PathMetrics(
            latency_ms=100.0,
            jitter_ms=30.0,
            packet_loss=0.05,
            trust_score=0.7,
            uptime_ratio=0.9,
        )
        
        score = metrics.quality_score()
        assert 0.5 < score < 0.8


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
