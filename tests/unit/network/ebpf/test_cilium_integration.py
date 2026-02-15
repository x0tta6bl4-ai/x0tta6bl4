"""
Unit tests for Cilium-like eBPF Integration
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from src.network.ebpf.cilium_integration import (CiliumLikeIntegration,
                                                     FlowDirection, FlowEvent,
                                                     FlowVerdict,
                                                     NetworkPolicy)

    CILIUM_AVAILABLE = True
except ImportError:
    CILIUM_AVAILABLE = False
    CiliumLikeIntegration = None


@pytest.mark.skipif(not CILIUM_AVAILABLE, reason="Cilium integration not available")
class TestCiliumIntegration:
    """Tests for Cilium-like Integration"""

    def test_integration_initialization(self):
        """Test Cilium integration initialization"""
        integration = CiliumLikeIntegration(
            interface="eth0",
            enable_flow_observability=True,
            enable_policy_enforcement=True,
        )

        assert integration.interface == "eth0"
        assert integration.enable_flow_observability == True
        assert integration.enable_policy_enforcement == True

    def test_record_flow(self):
        """Test recording flow event"""
        integration = CiliumLikeIntegration()

        integration.record_flow(
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            source_port=8080,
            destination_port=9090,
            protocol="TCP",
            direction=FlowDirection.INGRESS,
            verdict=FlowVerdict.FORWARDED,
            bytes=1024,
            packets=10,
        )

        assert len(integration.flow_events) > 0
        assert integration.flow_metrics["flows_processed_total"] > 0

    def test_get_flows(self):
        """Test getting flows with filtering"""
        integration = CiliumLikeIntegration()

        # Record some flows
        integration.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            8080,
            9090,
            "TCP",
            FlowDirection.INGRESS,
            FlowVerdict.FORWARDED,
            1024,
            10,
        )
        integration.record_flow(
            "10.0.0.3",
            "10.0.0.4",
            8080,
            9090,
            "UDP",
            FlowDirection.EGRESS,
            FlowVerdict.DROPPED,
            512,
            5,
        )

        # Filter by protocol
        tcp_flows = integration.get_flows(protocol="TCP")
        assert len(tcp_flows) > 0
        assert all(f.protocol == "TCP" for f in tcp_flows)

        # Filter by verdict
        dropped_flows = integration.get_flows(verdict=FlowVerdict.DROPPED)
        assert len(dropped_flows) > 0
        assert all(f.verdict == FlowVerdict.DROPPED for f in dropped_flows)

    def test_get_flow_metrics(self):
        """Test getting flow metrics"""
        integration = CiliumLikeIntegration()

        # Record some flows
        integration.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            8080,
            9090,
            "TCP",
            FlowDirection.INGRESS,
            FlowVerdict.FORWARDED,
            1024,
            10,
        )

        metrics = integration.get_flow_metrics()

        assert "flows_processed_total" in metrics
        assert "flows_per_second" in metrics
        assert "bytes_per_second" in metrics
        assert "drop_rate" in metrics

    def test_add_network_policy(self):
        """Test adding network policy"""
        integration = CiliumLikeIntegration()

        policy = NetworkPolicy(
            name="test-policy", namespace="default", endpoint_selector={"app": "test"}
        )

        success = integration.add_network_policy(policy)
        assert success == True
        assert "test-policy" in integration.network_policies

    def test_evaluate_policy(self):
        """Test policy evaluation"""
        integration = CiliumLikeIntegration()

        allowed, policy_name = integration.evaluate_policy(
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            source_port=8080,
            destination_port=9090,
            protocol="TCP",
            direction=FlowDirection.INGRESS,
        )

        assert isinstance(allowed, bool)
        assert policy_name is None or isinstance(policy_name, str)

    def test_get_hubble_like_flows(self):
        """Test getting flows in Hubble format"""
        integration = CiliumLikeIntegration()

        integration.record_flow(
            "10.0.0.1",
            "10.0.0.2",
            8080,
            9090,
            "TCP",
            FlowDirection.INGRESS,
            FlowVerdict.FORWARDED,
            1024,
            10,
        )

        hubble_flows = integration.get_hubble_like_flows(limit=10)

        assert len(hubble_flows) > 0
        assert all("time" in f for f in hubble_flows)
        assert all("source" in f for f in hubble_flows)
        assert all("destination" in f for f in hubble_flows)
        assert all("Verdict" in f for f in hubble_flows)


@pytest.mark.skipif(not CILIUM_AVAILABLE, reason="Cilium integration not available")
class TestFlowEvent:
    """Tests for FlowEvent"""

    def test_flow_event_creation(self):
        """Test creating flow event"""
        event = FlowEvent(
            timestamp=1234567890.0,
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            source_port=8080,
            destination_port=9090,
            protocol="TCP",
            direction=FlowDirection.INGRESS,
            verdict=FlowVerdict.FORWARDED,
            bytes=1024,
            packets=10,
            duration_ms=100.5,
        )

        assert event.source_ip == "10.0.0.1"
        assert event.destination_ip == "10.0.0.2"
        assert event.protocol == "TCP"
        assert event.direction == FlowDirection.INGRESS
        assert event.verdict == FlowVerdict.FORWARDED
