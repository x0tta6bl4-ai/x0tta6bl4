"""Unit tests for eBPF to x0tMQ PQC MAPE-K Bridge."""

from __future__ import annotations

import pytest
from src.network.ebpf.ebpf_to_x0tmq_bridge import EBPFToX0tMQBridge


def test_ebpf_to_x0tmq_bridge_pipeline():
    bridge = EBPFToX0tMQBridge(interface="eth0", node_id="test-edge-1")
    telemetry_event = {
        "packet_loss": 0.0,
        "latency": 25.4,
        "rst_drops": 0,
    }

    res = bridge.process_ebpf_telemetry_event(telemetry_event)

    assert res["interface"] == "eth0"
    assert res["spiffe_verified"] is True
    assert res["x0tmq_magic"] == "0x5830544d"
    assert res["processed"] is True
    assert "mapek_cycle_status" in res
