"""Unit tests for x0tMQ + PQC + SPIRE + MAPE-K Bridge."""

from __future__ import annotations

import pytest
from src.self_healing.x0tmq_mapek_bridge import (
    X0tMQMAPEKBridge,
    process_x0tmq_mapek_cycle,
    X0TMQ_MAPE_K_MAGIC,
)


def test_x0tmq_mapek_bridge_pack_and_unpack():
    bridge = X0tMQMAPEKBridge(spiffe_id="spiffe://x0tta6bl4.mesh/node/test-node-1")
    telemetry = {"latency": 15.2, "packet_loss": 0.0, "status": "OK"}

    frame = bridge.pack_mapek_frame(
        recipient_spiffe_id="spiffe://x0tta6bl4.mesh/node/nl-hub",
        payload_type="TELEMETRY",
        payload_data=telemetry,
    )

    assert frame.magic == X0TMQ_MAPE_K_MAGIC
    assert frame.sender_spiffe_id == "spiffe://x0tta6bl4.mesh/node/test-node-1"
    assert frame.recipient_spiffe_id == "spiffe://x0tta6bl4.mesh/node/nl-hub"
    assert frame.pqc_signature_b64 != ""
    assert frame.svid_signature != ""

    valid, data = bridge.unpack_and_verify_frame(frame)
    assert valid is True
    assert data["latency"] == 15.2
    assert data["status"] == "OK"


def test_process_x0tmq_mapek_cycle_e2e():
    res = process_x0tmq_mapek_cycle("node-alpha")
    assert res["node_id"] == "node-alpha"
    assert res["x0tmq_magic_valid"] is True
    assert res["spiffe_verified"] is True
    assert res["unpacked_data"]["cpu_load"] == 12.5
