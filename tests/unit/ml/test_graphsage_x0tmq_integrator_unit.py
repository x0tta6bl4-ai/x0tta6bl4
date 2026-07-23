"""Unit tests for GraphSAGE GNN x0tMQ Integrator."""

from __future__ import annotations

import pytest
from src.ml.graphsage_x0tmq_integrator import GraphSAGEX0tMQIntegrator
from src.self_healing.x0tmq_mapek_bridge import X0tMQMAPEKBridge


def test_graphsage_x0tmq_integrator_normal_telemetry():
    sender_bridge = X0tMQMAPEKBridge(spiffe_id="spiffe://x0tta6bl4.mesh/node/edge-node-1")
    telemetry_frame = sender_bridge.pack_mapek_frame(
        recipient_spiffe_id="spiffe://x0tta6bl4.mesh/node/gnn-analyzer",
        payload_type="TELEMETRY",
        payload_data={"latency": 20.0, "packet_loss": 0.0},
    )

    integrator = GraphSAGEX0tMQIntegrator()
    anomaly_detected, report_frame = integrator.evaluate_x0tmq_telemetry(telemetry_frame)

    assert anomaly_detected is False
    assert report_frame.payload_type == "ANOMALY_REPORT"
    assert report_frame.magic == 0x5830544D


def test_graphsage_x0tmq_integrator_high_degradation():
    sender_bridge = X0tMQMAPEKBridge(spiffe_id="spiffe://x0tta6bl4.mesh/node/edge-node-2")
    telemetry_frame = sender_bridge.pack_mapek_frame(
        recipient_spiffe_id="spiffe://x0tta6bl4.mesh/node/gnn-analyzer",
        payload_type="TELEMETRY",
        payload_data={"latency": 450.0, "packet_loss": 50.0},
    )

    integrator = GraphSAGEX0tMQIntegrator()
    anomaly_detected, report_frame = integrator.evaluate_x0tmq_telemetry(telemetry_frame)

    assert anomaly_detected is True
    assert report_frame.payload_type == "ANOMALY_REPORT"
