"""
Comprehensive unit tests for src.network.batman.node_manager
Covers: NodeMetrics, NodeManager, HealthMonitor, create_incident_workflow_for_node_manager
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.network.batman.node_manager import (
    AttestationStrategy,
    HealthMonitor,
    NodeManager,
    NodeMetrics,
    create_incident_workflow_for_node_manager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manager(mesh_id="mesh1", node_id="node-local", **kwargs):
    """Create a NodeManager with optimizations and DAO disabled for isolation."""
    defaults = dict(enable_optimizations=False)
    defaults.update(kwargs)
    with patch("src.network.batman.node_manager.DAO_AVAILABLE", False):
        mgr = NodeManager(mesh_id=mesh_id, local_node_id=node_id, **defaults)
    return mgr


def _register_node(mgr, node_id="node-1", mac="aa:bb:cc:dd:ee:01",
                    ip="10.0.0.1", spiffe_id="spiffe://mesh/node-1", **kwargs):
    """Register a node with SPIFFE attestation."""
    return mgr.register_node(
        node_id=node_id,
        mac_address=mac,
        ip_address=ip,
        spiffe_id=spiffe_id,
        **kwargs,
    )


# ===========================================================================
# NodeMetrics
# ===========================================================================

class TestNodeMetrics:
    def test_healthy_metrics(self):
        m = NodeMetrics(
            cpu_percent=50, memory_percent=60,
            network_sent_bytes=1000, network_recv_bytes=2000,
            packet_loss_percent=0.5, latency_to_gateway_ms=100,
        )
        assert m.is_healthy() is True

    def test_unhealthy_high_cpu(self):
        m = NodeMetrics(cpu_percent=95, memory_percent=50,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=0, latency_to_gateway_ms=10)
        assert m.is_healthy() is False

    def test_unhealthy_high_memory(self):
        m = NodeMetrics(cpu_percent=10, memory_percent=90,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=0, latency_to_gateway_ms=10)
        assert m.is_healthy() is False

    def test_unhealthy_high_packet_loss(self):
        m = NodeMetrics(cpu_percent=10, memory_percent=10,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=6, latency_to_gateway_ms=10)
        assert m.is_healthy() is False

    def test_unhealthy_high_latency(self):
        m = NodeMetrics(cpu_percent=10, memory_percent=10,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=0, latency_to_gateway_ms=600)
        assert m.is_healthy() is False

    def test_boundary_values_healthy(self):
        """Values just below thresholds are healthy."""
        m = NodeMetrics(cpu_percent=89.9, memory_percent=84.9,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=4.9, latency_to_gateway_ms=499)
        assert m.is_healthy() is True

    def test_boundary_values_unhealthy(self):
        """Exact threshold values: cpu>=90, mem>=85, loss>=5, lat>=500 are NOT healthy."""
        m = NodeMetrics(cpu_percent=90, memory_percent=85,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=5, latency_to_gateway_ms=500)
        assert m.is_healthy() is False

    def test_default_timestamp_is_none(self):
        m = NodeMetrics(cpu_percent=0, memory_percent=0,
                        network_sent_bytes=0, network_recv_bytes=0,
                        packet_loss_percent=0, latency_to_gateway_ms=0)
        assert m.timestamp is None


# ===========================================================================
# NodeManager - Initialization
# ===========================================================================

class TestNodeManagerInit:
    def test_basic_init(self):
        mgr = _make_manager()
        assert mgr.mesh_id == "mesh1"
        assert mgr.local_node_id == "node-local"
        assert mgr.attestation_strategy == AttestationStrategy.SPIFFE
        assert mgr.nodes == {}
        assert mgr.optimizations is None
        assert mgr.traffic_shaper is None
        assert mgr.governance is None
        assert mgr.token is None
        assert mgr._relay_count == 0

    def test_init_with_obfuscation_transport(self):
        transport = MagicMock()
        mgr = _make_manager(obfuscation_transport=transport)
        assert mgr.obfuscation_transport is transport

    @patch("src.network.batman.node_manager.BATMAN_OPTIMIZATIONS_AVAILABLE", True)
    @patch("src.network.batman.node_manager.BatmanAdvConfig")
    @patch("src.network.batman.node_manager.BatmanAdvOptimizations")
    def test_init_with_optimizations(self, mock_opt_cls, mock_cfg_cls):
        mock_opt_cls.return_value = MagicMock()
        mock_cfg_cls.return_value = MagicMock()
        with patch("src.network.batman.node_manager.DAO_AVAILABLE", False):
            mgr = NodeManager("mesh1", "n1", enable_optimizations=True)
        assert mgr.optimizations is not None

    @patch("src.network.batman.node_manager.BATMAN_OPTIMIZATIONS_AVAILABLE", True)
    @patch("src.network.batman.node_manager.BatmanAdvConfig", side_effect=Exception("boom"))
    def test_init_optimizations_failure(self, mock_cfg):
        with patch("src.network.batman.node_manager.DAO_AVAILABLE", False):
            mgr = NodeManager("mesh1", "n1", enable_optimizations=True)
        assert mgr.optimizations is None

    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_init_with_dao(self, mock_gov_cls):
        mock_gov_cls.return_value = MagicMock()
        mgr = NodeManager("mesh1", "n1", enable_optimizations=False)
        assert mgr.governance is not None

    @patch("src.network.batman.node_manager.TRAFFIC_SHAPING_AVAILABLE", True)
    @patch("src.network.batman.node_manager.TrafficShaper")
    @patch("src.network.batman.node_manager.TrafficProfile")
    def test_init_with_traffic_shaping(self, mock_profile, mock_shaper):
        mock_profile.return_value = "web"
        mock_shaper.return_value = MagicMock()
        mgr = _make_manager(traffic_profile="web")
        assert mgr.traffic_shaper is not None

    @patch("src.network.batman.node_manager.TRAFFIC_SHAPING_AVAILABLE", True)
    @patch("src.network.batman.node_manager.TrafficProfile", side_effect=ValueError("bad"))
    def test_init_traffic_shaping_invalid_profile(self, mock_profile):
        mgr = _make_manager(traffic_profile="invalid_profile")
        assert mgr.traffic_shaper is None


# ===========================================================================
# NodeManager - Registration & Attestation
# ===========================================================================

class TestNodeRegistration:
    def test_register_node_spiffe(self):
        mgr = _make_manager()
        result = _register_node(mgr)
        assert result is True
        assert "node-1" in mgr.nodes
        assert mgr.nodes["node-1"]["ip_address"] == "10.0.0.1"
        assert mgr.nodes["node-1"]["status"] == "online"

    def test_register_duplicate_node(self):
        mgr = _make_manager()
        _register_node(mgr)
        result = _register_node(mgr)
        assert result is False

    def test_register_node_no_spiffe_id(self):
        mgr = _make_manager()
        result = mgr.register_node("n1", "aa:bb:cc:dd:ee:01", "10.0.0.1")
        assert result is False

    def test_register_node_invalid_spiffe_id(self):
        mgr = _make_manager()
        result = mgr.register_node("n1", "aa:bb:cc:dd:ee:01", "10.0.0.1",
                                    spiffe_id="not-a-spiffe-uri")
        assert result is False

    def test_register_node_token_based_strategy(self):
        mgr = _make_manager()
        mgr.attestation_strategy = AttestationStrategy.TOKEN_BASED
        result = mgr.register_node("n1", "mac", "1.2.3.4",
                                    join_token="abcdefghijklmnopqrst")
        assert result is True

    def test_register_node_token_based_no_token(self):
        mgr = _make_manager()
        mgr.attestation_strategy = AttestationStrategy.TOKEN_BASED
        result = mgr.register_node("n1", "mac", "1.2.3.4")
        assert result is False

    def test_register_node_self_signed_strategy(self):
        """SELF_SIGNED strategy always passes attestation."""
        mgr = _make_manager()
        mgr.attestation_strategy = AttestationStrategy.SELF_SIGNED
        result = mgr.register_node("n1", "mac", "1.2.3.4")
        assert result is True

    def test_register_node_challenge_response_strategy(self):
        """CHALLENGE_RESPONSE strategy falls through to return True."""
        mgr = _make_manager()
        mgr.attestation_strategy = AttestationStrategy.CHALLENGE_RESPONSE
        result = mgr.register_node("n1", "mac", "1.2.3.4")
        assert result is True

    @patch("src.network.batman.node_manager.SPIFFE_AVAILABLE", True)
    @patch("src.network.batman.node_manager.WorkloadAPIClient")
    @patch("src.network.batman.node_manager.X509SVID")
    def test_register_node_spiffe_with_cert_validation_success(self, mock_svid, mock_client_cls):
        mock_client = MagicMock()
        mock_client.validate_peer_svid.return_value = True
        mock_client_cls.return_value = mock_client
        mock_svid.return_value = MagicMock()

        mgr = _make_manager()
        result = mgr.register_node(
            "n1", "mac", "1.2.3.4",
            spiffe_id="spiffe://mesh/n1",
            cert_pem=b"-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----",
        )
        assert result is True

    @patch("src.network.batman.node_manager.SPIFFE_AVAILABLE", True)
    @patch("src.network.batman.node_manager.WorkloadAPIClient")
    @patch("src.network.batman.node_manager.X509SVID")
    def test_register_node_spiffe_cert_validation_failure(self, mock_svid, mock_client_cls):
        mock_client = MagicMock()
        mock_client.validate_peer_svid.return_value = False
        mock_client_cls.return_value = mock_client
        mock_svid.return_value = MagicMock()

        mgr = _make_manager()
        result = mgr.register_node(
            "n1", "mac", "1.2.3.4",
            spiffe_id="spiffe://mesh/n1",
            cert_pem=b"fake-cert",
        )
        assert result is False

    @patch("src.network.batman.node_manager.SPIFFE_AVAILABLE", True)
    @patch("src.network.batman.node_manager.WorkloadAPIClient", side_effect=Exception("boom"))
    @patch("src.network.batman.node_manager.X509SVID")
    def test_register_node_spiffe_cert_exception(self, mock_svid, mock_client_cls):
        mgr = _make_manager()
        result = mgr.register_node(
            "n1", "mac", "1.2.3.4",
            spiffe_id="spiffe://mesh/n1",
            cert_pem=b"fake-cert",
        )
        assert result is False

    @patch("src.network.batman.node_manager.TOKEN_AVAILABLE", True)
    def test_register_node_with_token_reward(self):
        mgr = _make_manager()
        mock_token = MagicMock()
        mgr.token = mock_token
        result = _register_node(mgr, node_id="n1")
        assert result is True
        mock_token.reward_deployment.assert_called_once()

    @patch("src.network.batman.node_manager.TOKEN_AVAILABLE", True)
    def test_register_node_with_token_reward_type_error_fallback(self):
        mgr = _make_manager()
        mock_token = MagicMock()
        # First call with referrer_id raises TypeError, second call without it succeeds
        mock_token.reward_deployment.side_effect = [TypeError("unexpected kwarg"), None]
        mgr.token = mock_token
        result = _register_node(mgr, node_id="n1", referrer_id="ref1")
        assert result is True
        assert mock_token.reward_deployment.call_count == 2


# ===========================================================================
# NodeManager - Heartbeat, Metrics, Deregister, Status
# ===========================================================================

class TestNodeLifecycle:
    def test_update_heartbeat_existing_node(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        old_hb = mgr.nodes["n1"]["last_heartbeat"]
        result = mgr.update_heartbeat("n1")
        assert result is True
        assert mgr.nodes["n1"]["last_heartbeat"] >= old_hb

    def test_update_heartbeat_unknown_node(self):
        mgr = _make_manager()
        assert mgr.update_heartbeat("nonexistent") is False

    def test_update_metrics_healthy(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        metrics = NodeMetrics(50, 50, 100, 100, 1, 50)
        result = mgr.update_metrics("n1", metrics)
        assert result is True
        assert mgr.nodes["n1"]["status"] == "online"
        assert mgr.nodes["n1"]["metrics"] is metrics

    def test_update_metrics_degraded(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        metrics = NodeMetrics(95, 90, 100, 100, 10, 600)
        result = mgr.update_metrics("n1", metrics)
        assert result is True
        assert mgr.nodes["n1"]["status"] == "degraded"

    def test_update_metrics_unknown_node(self):
        mgr = _make_manager()
        metrics = NodeMetrics(50, 50, 100, 100, 1, 50)
        assert mgr.update_metrics("nope", metrics) is False

    def test_deregister_node(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        result = mgr.deregister_node("n1", reason="test")
        assert result is True
        assert "n1" not in mgr.nodes

    def test_deregister_unknown_node(self):
        mgr = _make_manager()
        assert mgr.deregister_node("nope") is False

    def test_get_node_status(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        status = mgr.get_node_status("n1")
        assert status is not None
        assert status["ip_address"] == "10.0.0.1"

    def test_get_node_status_unknown(self):
        mgr = _make_manager()
        assert mgr.get_node_status("nope") is None

    def test_get_all_nodes(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        _register_node(mgr, node_id="n2", mac="bb:cc:dd:ee:ff:02",
                        ip="10.0.0.2", spiffe_id="spiffe://mesh/n2")
        all_nodes = mgr.get_all_nodes()
        assert len(all_nodes) == 2
        # Verify it returns a copy
        all_nodes["n1"]["status"] = "modified"
        assert mgr.nodes["n1"]["status"] == "online"

    def test_get_online_nodes(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        _register_node(mgr, node_id="n2", mac="bb", ip="10.0.0.2",
                        spiffe_id="spiffe://mesh/n2")
        # Set n2 to degraded
        mgr.nodes["n2"]["status"] = "degraded"
        online = mgr.get_online_nodes()
        assert online == ["n1"]

    def test_get_online_nodes_empty(self):
        mgr = _make_manager()
        assert mgr.get_online_nodes() == []


# ===========================================================================
# NodeManager - Heartbeat sending
# ===========================================================================

class TestSendHeartbeat:
    def test_send_heartbeat_basic(self):
        mgr = _make_manager()
        assert mgr.send_heartbeat("target-node") is True

    def test_send_heartbeat_with_obfuscation(self):
        transport = MagicMock()
        transport.obfuscate.return_value = b"obfuscated-data"
        mgr = _make_manager(obfuscation_transport=transport)
        assert mgr.send_heartbeat("target") is True
        transport.obfuscate.assert_called_once()

    def test_send_heartbeat_obfuscation_failure(self):
        transport = MagicMock()
        transport.obfuscate.side_effect = Exception("obf error")
        mgr = _make_manager(obfuscation_transport=transport)
        assert mgr.send_heartbeat("target") is False

    @patch("src.network.batman.node_manager.HYBRID_TLS_AVAILABLE", True)
    @patch("src.network.batman.node_manager.hybrid_encrypt")
    def test_send_heartbeat_with_pqc_encryption(self, mock_encrypt):
        mock_encrypt.return_value = b"encrypted-data"
        mgr = _make_manager()
        mgr._hybrid_tls_session_key = b"session-key"
        assert mgr.send_heartbeat("target") is True
        mock_encrypt.assert_called_once()

    @patch("src.network.batman.node_manager.HYBRID_TLS_AVAILABLE", True)
    @patch("src.network.batman.node_manager.hybrid_encrypt", side_effect=Exception("enc fail"))
    def test_send_heartbeat_pqc_encryption_failure(self, mock_encrypt):
        mgr = _make_manager()
        mgr._hybrid_tls_session_key = b"session-key"
        assert mgr.send_heartbeat("target") is False

    def test_send_heartbeat_with_traffic_shaper(self):
        mgr = _make_manager()
        shaper = MagicMock()
        shaper.shape_packet.return_value = b"shaped"
        shaper.get_send_delay.return_value = 0.01
        shaper.profile.value = "web"
        mgr.traffic_shaper = shaper
        assert mgr.send_heartbeat("target") is True
        shaper.shape_packet.assert_called_once()


# ===========================================================================
# NodeManager - Topology Update
# ===========================================================================

class TestSendTopologyUpdate:
    def test_send_topology_update_basic(self):
        mgr = _make_manager()
        assert mgr.send_topology_update("target", {"nodes": 5}) is True

    def test_send_topology_update_with_obfuscation(self):
        transport = MagicMock()
        transport.obfuscate.return_value = b"obf"
        mgr = _make_manager(obfuscation_transport=transport)
        assert mgr.send_topology_update("target", {}) is True
        transport.obfuscate.assert_called_once()

    def test_send_topology_update_obfuscation_failure(self):
        transport = MagicMock()
        transport.obfuscate.side_effect = Exception("fail")
        mgr = _make_manager(obfuscation_transport=transport)
        assert mgr.send_topology_update("target", {}) is False

    def test_send_topology_update_with_traffic_shaper(self):
        mgr = _make_manager()
        shaper = MagicMock()
        shaper.shape_packet.return_value = b"shaped"
        shaper.get_send_delay.return_value = 0.0
        shaper.profile.value = "video"
        mgr.traffic_shaper = shaper
        assert mgr.send_topology_update("target", {"k": "v"}) is True
        shaper.shape_packet.assert_called_once()


# ===========================================================================
# NodeManager - Relay & Token Economics
# ===========================================================================

class TestRelayAndTokens:
    def test_relay_packet_basic(self):
        mgr = _make_manager()
        assert mgr.relay_packet("src", "dst") is True
        assert mgr.get_relay_count() == 1

    def test_relay_packet_multiple(self):
        mgr = _make_manager()
        for _ in range(5):
            mgr.relay_packet("src", "dst")
        assert mgr.get_relay_count() == 5

    def test_relay_to_self(self):
        mgr = _make_manager(node_id="node-local")
        assert mgr.relay_packet("src", "node-local") is True

    def test_relay_to_registered_node(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="dest")
        assert mgr.relay_packet("src", "dest") is True

    def test_relay_to_unknown_external(self):
        """Relaying to unknown dest still succeeds (just logs debug)."""
        mgr = _make_manager()
        assert mgr.relay_packet("src", "unknown-dest") is True

    @patch("src.network.batman.node_manager.TOKEN_AVAILABLE", True)
    def test_relay_with_token_payment(self):
        mgr = _make_manager()
        mock_token = MagicMock()
        mock_token.pay_for_resource.return_value = True
        mgr.token = mock_token
        mgr.relay_packet("src", "dst", packet_size_bytes=2048)
        mock_token.pay_for_resource.assert_called_once()

    def test_get_relay_earnings_no_token(self):
        mgr = _make_manager()
        mgr._relay_count = 10
        assert mgr.get_relay_earnings() == 0.0

    def test_get_relay_earnings_with_token(self):
        mgr = _make_manager()
        mock_token = MagicMock()
        mock_token.PRICE_PER_RELAY = 0.0001
        mgr.token = mock_token
        mgr._relay_count = 100
        assert mgr.get_relay_earnings() == pytest.approx(0.01)

    def test_set_token(self):
        mgr = _make_manager()
        mock_token = MagicMock()
        mgr.set_token(mock_token)
        assert mgr.token is mock_token


# ===========================================================================
# NodeManager - Governance
# ===========================================================================

class TestGovernance:
    def test_propose_network_update_no_governance(self):
        mgr = _make_manager()
        assert mgr.propose_network_update("title", {"key": "val"}) is None

    def test_propose_network_update_with_governance(self):
        mgr = _make_manager()
        mock_gov = MagicMock()
        mock_proposal = MagicMock()
        mock_proposal.id = "prop-123"
        mock_gov.create_proposal.return_value = mock_proposal
        mgr.governance = mock_gov

        result = mgr.propose_network_update("upgrade routing", {"type": "upgrade"})
        assert result == "prop-123"
        mock_gov.create_proposal.assert_called_once()

    def test_vote_on_proposal_no_governance(self):
        mgr = _make_manager()
        assert mgr.vote_on_proposal("prop-1", "yes") is False

    def test_vote_on_proposal_success(self):
        mgr = _make_manager()
        mock_gov = MagicMock()
        mock_gov.cast_vote.return_value = True
        mgr.governance = mock_gov

        with patch("src.network.batman.node_manager.VoteType") as mock_vt:
            mock_vt.__getitem__ = MagicMock(return_value="YES")
            result = mgr.vote_on_proposal("prop-1", "yes")
        assert result is True

    def test_vote_on_proposal_invalid_vote_type(self):
        mgr = _make_manager()
        mock_gov = MagicMock()
        mgr.governance = mock_gov

        with patch("src.network.batman.node_manager.VoteType", new=dict()):
            # dict doesn't have KeyError-raising __getitem__ for missing keys the same way
            # but the code uses VoteType[vote_str.upper()] which raises KeyError
            result = mgr.vote_on_proposal("prop-1", "invalid_vote")
        # When VoteType is a dict, VoteType["INVALID_VOTE"] raises KeyError
        assert result is False

    def test_check_governance_with_governance(self):
        mgr = _make_manager()
        mock_gov = MagicMock()
        mgr.governance = mock_gov
        mgr.check_governance()
        mock_gov.check_proposals.assert_called_once()

    def test_check_governance_no_governance(self):
        mgr = _make_manager()
        # Should not raise
        mgr.check_governance()


# ===========================================================================
# HealthMonitor
# ===========================================================================

class TestHealthMonitor:
    def test_init(self):
        hm = HealthMonitor(check_interval=60)
        assert hm.check_interval == 60
        assert hm.running is False
        assert hm.health_checks == {}
        assert hm.alert_handlers == []
        assert hm.incident_workflow is None

    def test_register_health_check(self):
        hm = HealthMonitor()
        fn = MagicMock()
        hm.register_health_check("cpu_check", fn)
        assert "cpu_check" in hm.health_checks
        assert hm.health_checks["cpu_check"] is fn

    def test_register_alert_handler(self):
        hm = HealthMonitor()
        handler = MagicMock()
        hm.register_alert_handler(handler)
        assert handler in hm.alert_handlers

    def test_stop_monitoring(self):
        hm = HealthMonitor()
        hm.running = True
        hm.stop_monitoring()
        assert hm.running is False

    def test_check_node_heartbeats_no_dead(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        hm = HealthMonitor()
        dead = hm._check_node_heartbeats(mgr, timeout=120)
        assert dead == []

    def test_check_node_heartbeats_with_dead(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        # Set heartbeat to long ago
        mgr.nodes["n1"]["last_heartbeat"] = datetime.now() - timedelta(seconds=300)
        hm = HealthMonitor()
        dead = hm._check_node_heartbeats(mgr, timeout=120)
        assert dead == ["n1"]

    def test_check_link_quality(self):
        hm = HealthMonitor()
        # Mock topology
        mock_link_good = MagicMock()
        mock_link_good.quality.value = 5
        mock_link_bad = MagicMock()
        mock_link_bad.quality.value = 2
        mock_link_bad.quality.name = "POOR"

        topology = MagicMock()
        topology.links = {
            ("a", "b"): mock_link_good,
            ("c", "d"): mock_link_bad,
        }
        degraded = hm._check_link_quality(topology)
        assert len(degraded) == 1
        assert degraded[0]["source"] == "c"
        assert degraded[0]["destination"] == "d"

    @pytest.mark.asyncio
    async def test_handle_alert_calls_sync_handlers(self):
        hm = HealthMonitor()
        handler = MagicMock()
        hm.register_alert_handler(handler)
        await hm._handle_alert("test_alert", {"key": "val"})
        handler.assert_called_once_with("test_alert", {"key": "val"})

    @pytest.mark.asyncio
    async def test_handle_alert_calls_async_handlers(self):
        hm = HealthMonitor()
        handler = AsyncMock()
        hm.register_alert_handler(handler)
        await hm._handle_alert("test_alert", {"data": 1})
        handler.assert_called_once_with("test_alert", {"data": 1})

    @pytest.mark.asyncio
    async def test_handle_alert_handler_exception(self):
        hm = HealthMonitor()
        handler = MagicMock(side_effect=Exception("handler error"))
        hm.register_alert_handler(handler)
        # Should not raise
        await hm._handle_alert("test_alert", {})

    @pytest.mark.asyncio
    async def test_handle_alert_dead_nodes_with_incident_workflow(self):
        mock_workflow = MagicMock()
        mock_proposal = MagicMock()
        mock_proposal.id = "prop-1"
        mock_workflow.create_proposal_from_incident.return_value = mock_proposal
        mock_workflow.governance.node_id = "local"

        hm = HealthMonitor(incident_workflow=mock_workflow)

        with patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True), \
             patch("src.network.batman.node_manager.Incident") as mock_incident_cls, \
             patch("src.network.batman.node_manager.IncidentSeverity") as mock_sev, \
             patch("src.network.batman.node_manager.VoteType") as mock_vt:
            mock_incident_cls.return_value = MagicMock()
            mock_sev.CRITICAL = "CRITICAL"
            mock_vt.YES = "YES"
            await hm._handle_alert("dead_nodes", {"nodes": ["n1"]})

        mock_workflow.create_proposal_from_incident.assert_called_once()
        mock_workflow.auto_vote_and_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_health_checks_with_dead_nodes(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        mgr.nodes["n1"]["last_heartbeat"] = datetime.now() - timedelta(seconds=300)

        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor()
        hm._handle_alert = AsyncMock()

        await hm._perform_health_checks(mgr, topology)
        hm._handle_alert.assert_any_call("dead_nodes", {"nodes": ["n1"]})

    @pytest.mark.asyncio
    async def test_perform_health_checks_with_degraded_links(self):
        mgr = _make_manager()

        mock_link = MagicMock()
        mock_link.quality.value = 1
        mock_link.quality.name = "BAD"
        topology = MagicMock()
        topology.links = {("a", "b"): mock_link}

        hm = HealthMonitor()
        hm._handle_alert = AsyncMock()

        await hm._perform_health_checks(mgr, topology)
        hm._handle_alert.assert_any_call(
            "degraded_links",
            {"links": [{"source": "a", "destination": "b", "quality": "BAD"}]}
        )

    @pytest.mark.asyncio
    async def test_perform_health_checks_custom_sync_check_passes(self):
        mgr = _make_manager()
        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor()
        hm._handle_alert = AsyncMock()
        hm.register_health_check("always_ok", lambda: True)

        await hm._perform_health_checks(mgr, topology)
        # No alert for passing check
        for call in hm._handle_alert.call_args_list:
            assert call[0][0] != "check_failed"

    @pytest.mark.asyncio
    async def test_perform_health_checks_custom_sync_check_fails(self):
        mgr = _make_manager()
        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor()
        hm._handle_alert = AsyncMock()
        hm.register_health_check("always_fail", lambda: False)

        await hm._perform_health_checks(mgr, topology)
        hm._handle_alert.assert_any_call("check_failed", {"check": "always_fail"})

    @pytest.mark.asyncio
    async def test_perform_health_checks_custom_async_check(self):
        mgr = _make_manager()
        topology = MagicMock()
        topology.links = {}

        async def async_check():
            return False

        hm = HealthMonitor()
        hm._handle_alert = AsyncMock()
        hm.register_health_check("async_fail", async_check)

        await hm._perform_health_checks(mgr, topology)
        hm._handle_alert.assert_any_call("check_failed", {"check": "async_fail"})

    @pytest.mark.asyncio
    async def test_perform_health_checks_custom_check_exception(self):
        mgr = _make_manager()
        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor()
        hm._handle_alert = AsyncMock()
        hm.register_health_check("bad_check", MagicMock(side_effect=Exception("err")))

        # Should not raise
        await hm._perform_health_checks(mgr, topology)

    @pytest.mark.asyncio
    async def test_start_monitoring_loop(self):
        mgr = _make_manager()
        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor(check_interval=0.01)

        call_count = 0

        async def fake_checks(nm, topo):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                hm.stop_monitoring()

        hm._perform_health_checks = fake_checks
        await hm.start_monitoring(mgr, topology)
        assert call_count >= 2

    @pytest.mark.asyncio
    @patch("src.network.batman.node_manager.TOKEN_AVAILABLE", True)
    async def test_start_monitoring_distributes_epoch_rewards(self):
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")
        mock_token = MagicMock()
        mgr.token = mock_token

        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor(check_interval=0.01)

        call_count = 0

        async def fake_checks(nm, topo):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                hm.stop_monitoring()

        hm._perform_health_checks = fake_checks
        await hm.start_monitoring(mgr, topology)
        mock_token.distribute_epoch_rewards.assert_called()

    @pytest.mark.asyncio
    async def test_start_monitoring_handles_exception(self):
        mgr = _make_manager()
        topology = MagicMock()
        topology.links = {}

        hm = HealthMonitor(check_interval=0.01)
        call_count = 0

        async def failing_checks(nm, topo):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("check error")
            hm.stop_monitoring()

        hm._perform_health_checks = failing_checks
        await hm.start_monitoring(mgr, topology)
        assert call_count >= 2


# ===========================================================================
# create_incident_workflow_for_node_manager
# ===========================================================================

class TestCreateIncidentWorkflow:
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", False)
    def test_returns_none_when_dao_unavailable(self):
        mgr = _make_manager()
        result = create_incident_workflow_for_node_manager(mgr)
        assert result is None

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", False)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    def test_returns_none_when_incident_workflow_unavailable(self):
        mgr = _make_manager()
        result = create_incident_workflow_for_node_manager(mgr)
        assert result is None

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.IncidentDAOWorkflow")
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_creates_workflow(self, mock_gov_cls, mock_workflow_cls):
        mock_gov_cls.return_value = MagicMock()
        mock_workflow_cls.return_value = MagicMock()

        mgr = _make_manager()
        result = create_incident_workflow_for_node_manager(mgr)
        assert result is not None
        mock_workflow_cls.assert_called_once()

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.IncidentDAOWorkflow")
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_executor_deregisters_dead_node(self, mock_gov_cls, mock_workflow_cls):
        mock_gov_cls.return_value = MagicMock()

        mgr = _make_manager()
        _register_node(mgr, node_id="dead-node")
        assert "dead-node" in mgr.nodes

        # Capture the executor function passed to IncidentDAOWorkflow
        captured_executor = None

        def capture_workflow(governance, executor):
            nonlocal captured_executor
            captured_executor = executor
            return MagicMock()

        mock_workflow_cls.side_effect = capture_workflow

        create_incident_workflow_for_node_manager(mgr)
        assert captured_executor is not None

        # Execute with incident_response action
        captured_executor({
            "type": "incident_response",
            "metadata": {"node_id": "dead-node"},
            "incident_type": "node_down",
            "severity": "CRITICAL",
        })
        assert "dead-node" not in mgr.nodes

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.IncidentDAOWorkflow")
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_executor_ignores_non_incident_response(self, mock_gov_cls, mock_workflow_cls):
        mock_gov_cls.return_value = MagicMock()

        mgr = _make_manager()
        _register_node(mgr, node_id="n1")

        captured_executor = None

        def capture_workflow(governance, executor):
            nonlocal captured_executor
            captured_executor = executor
            return MagicMock()

        mock_workflow_cls.side_effect = capture_workflow
        create_incident_workflow_for_node_manager(mgr)

        # Non-incident action should be ignored
        captured_executor({"type": "other_action"})
        assert "n1" in mgr.nodes

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.IncidentDAOWorkflow")
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_executor_no_node_id_in_metadata(self, mock_gov_cls, mock_workflow_cls):
        mock_gov_cls.return_value = MagicMock()
        mgr = _make_manager()
        _register_node(mgr, node_id="n1")

        captured_executor = None

        def capture_workflow(governance, executor):
            nonlocal captured_executor
            captured_executor = executor
            return MagicMock()

        mock_workflow_cls.side_effect = capture_workflow
        create_incident_workflow_for_node_manager(mgr)

        # No node_id in metadata - should not deregister
        captured_executor({"type": "incident_response", "metadata": {}})
        assert "n1" in mgr.nodes

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.IncidentDAOWorkflow")
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_executor_node_not_in_mesh(self, mock_gov_cls, mock_workflow_cls):
        mock_gov_cls.return_value = MagicMock()
        mgr = _make_manager()

        captured_executor = None

        def capture_workflow(governance, executor):
            nonlocal captured_executor
            captured_executor = executor
            return MagicMock()

        mock_workflow_cls.side_effect = capture_workflow
        create_incident_workflow_for_node_manager(mgr)

        # Node not in mesh - should not raise
        captured_executor({
            "type": "incident_response",
            "metadata": {"node_id": "nonexistent"},
        })

    @patch("src.network.batman.node_manager.INCIDENT_WORKFLOW_AVAILABLE", True)
    @patch("src.network.batman.node_manager.DAO_AVAILABLE", True)
    @patch("src.network.batman.node_manager.IncidentDAOWorkflow")
    @patch("src.network.batman.node_manager.GovernanceEngine")
    def test_executor_none_metadata(self, mock_gov_cls, mock_workflow_cls):
        mock_gov_cls.return_value = MagicMock()
        mgr = _make_manager()

        captured_executor = None

        def capture_workflow(governance, executor):
            nonlocal captured_executor
            captured_executor = executor
            return MagicMock()

        mock_workflow_cls.side_effect = capture_workflow
        create_incident_workflow_for_node_manager(mgr)

        # metadata is None
        captured_executor({"type": "incident_response", "metadata": None})


# ===========================================================================
# AttestationStrategy enum
# ===========================================================================

class TestAttestationStrategy:
    def test_enum_values(self):
        assert AttestationStrategy.SELF_SIGNED.value == "self_signed"
        assert AttestationStrategy.SPIFFE.value == "spiffe"
        assert AttestationStrategy.TOKEN_BASED.value == "token_based"
        assert AttestationStrategy.CHALLENGE_RESPONSE.value == "challenge_response"


# ===========================================================================
# Metrics recording (private methods)
# ===========================================================================

class TestMetricsRecording:
    def test_record_traffic_profile_active_import_error(self):
        """Should not raise when metrics module unavailable."""
        mgr = _make_manager()
        mgr._record_traffic_profile_active("web")

    def test_record_traffic_shaping_metrics_import_error(self):
        """Should not raise when metrics module unavailable."""
        mgr = _make_manager()
        mgr._record_traffic_shaping_metrics(100, 150, 0.01, "web")
