"""
Unit tests for src/api/v3_endpoints.py using direct function calls.
Avoids HTTP client wrappers that can hang in CI/threaded anyio environments.
"""

import base64
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import src.api.v3_endpoints as mod

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


@pytest.mark.asyncio
async def test_status_ok_and_unavailable(monkeypatch):
    integration = SimpleNamespace(get_status=lambda: {"graphsage": True})
    monkeypatch.setattr(mod, "V3_AVAILABLE", True)
    ok = await mod.get_v3_status(integration=integration)
    assert ok["status"] == "operational"
    assert ok["version"] == "3.5.0"
    assert ok["local_component_status_claim_allowed"] is True
    assert ok["dataplane_confirmed"] is False
    assert ok["customer_traffic_confirmed"] is False
    assert ok["external_dpi_bypass_confirmed"] is False
    assert ok["trust_finality_confirmed"] is False
    assert ok["settlement_finality_confirmed"] is False
    assert ok["production_readiness_claim_allowed"] is False
    assert ok["cross_plane_claim_gate"]["allowed"] is False
    assert ok["cross_plane_claim_gate"]["requested_claim_ids"] == [
        "production_readiness",
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "dpi_bypass",
        "trust_finality",
        "settlement_finality",
    ]
    assert "status=operational does not prove production readiness" in (
        ok["claim_boundary"]
    )

    monkeypatch.setattr(mod, "V3_AVAILABLE", False)
    with pytest.raises(HTTPException) as exc:
        await mod.get_v3_status(integration=integration)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_graphsage_paths(monkeypatch):
    monkeypatch.setattr(mod, "V3_AVAILABLE", True)
    analysis = SimpleNamespace(
        failure_type=SimpleNamespace(value="anomaly"),
        confidence=0.9,
        recommended_action="isolate",
        severity="high",
        affected_nodes=["n1"],
    )
    integration = SimpleNamespace(
        analyze_with_graphsage=AsyncMock(return_value=analysis)
    )
    req = mod.GraphSAGEAnalysisRequest(node_features={"n1": {"cpu": 0.8}})
    out = await mod.analyze_with_graphsage(req, integration=integration)
    assert out["failure_type"] == "anomaly"
    assert out["local_model_analysis_claim_allowed"] is True
    assert out["control_action_applied"] is False
    assert out["dataplane_confirmed"] is False
    assert out["customer_traffic_confirmed"] is False
    assert out["production_readiness_claim_allowed"] is False
    assert out["graphsage_claim_gate"]["allowed_claim_ids"] == [
        "local_model_analysis"
    ]
    assert "dataplane_delivery" in out["graphsage_claim_gate"]["blocked_claim_ids"]
    assert out["cross_plane_claim_gate"]["allowed"] is False
    assert "local model inference" in out["claim_boundary"]

    integration_none = SimpleNamespace(
        analyze_with_graphsage=AsyncMock(return_value=None)
    )
    with pytest.raises(HTTPException) as exc_none:
        await mod.analyze_with_graphsage(req, integration=integration_none)
    assert exc_none.value.status_code == 500


@pytest.mark.asyncio
async def test_stego_encode_paths(monkeypatch):
    monkeypatch.setattr(mod, "V3_AVAILABLE", True)
    payload = b"hello"
    req = mod.StegoMeshEncodeRequest(
        payload=base64.b64encode(payload).decode(), protocol_mimic="http"
    )
    integration = SimpleNamespace(encode_packet_stego=lambda p, proto: b"enc")
    out = await mod.encode_stego_packet(req, integration=integration)
    assert out["original_size"] == len(payload)
    assert out["encoded_size"] == 3
    assert out["local_transform_claim_allowed"] is True
    assert out["dataplane_confirmed"] is False
    assert out["external_dpi_bypass_confirmed"] is False
    assert out["production_readiness_claim_allowed"] is False
    assert out["stego_claim_gate"]["allowed_claim_ids"] == [
        "local_stego_encode_transform"
    ]
    assert "external_dpi_bypass" in out["stego_claim_gate"]["blocked_claim_ids"]
    assert "dpi_bypass" in out["cross_plane_claim_gate"]["requested_claim_ids"]
    assert out["cross_plane_claim_gate"]["allowed"] is False
    assert "local encode/decode transform results only" in out["claim_boundary"]

    decode_integration = SimpleNamespace(decode_packet_stego=lambda p: payload)
    decoded = await mod.decode_stego_packet(
        base64.b64encode(b"enc").decode(), integration=decode_integration
    )
    assert decoded["decoded_payload"] == base64.b64encode(payload).decode()
    assert decoded["local_transform_claim_allowed"] is True
    assert decoded["external_dpi_bypass_confirmed"] is False
    assert decoded["stego_claim_gate"]["allowed_claim_ids"] == [
        "local_stego_decode_transform"
    ]
    assert decoded["cross_plane_claim_gate"]["allowed"] is False

    integration_none = SimpleNamespace(encode_packet_stego=lambda p, proto: None)
    with pytest.raises(HTTPException) as exc_none:
        await mod.encode_stego_packet(req, integration=integration_none)
    assert exc_none.value.status_code == 500


@pytest.mark.asyncio
async def test_chaos_paths(monkeypatch):
    monkeypatch.setattr(mod, "V3_AVAILABLE", True)
    req = mod.ChaosTestRequest(scenario="node_down", intensity=0.5, duration=10.0)
    integration = SimpleNamespace(
        run_chaos_test=AsyncMock(return_value={"survived": True})
    )
    out = await mod.run_chaos_test(req, integration=integration)
    assert out["survived"] is True
    assert out["local_simulation_claim_allowed"] is True
    assert out["control_action_applied"] is False
    assert out["dataplane_confirmed"] is False
    assert out["production_slo_confirmed"] is False
    assert out["production_readiness_claim_allowed"] is False
    assert out["chaos_claim_gate"]["allowed_claim_ids"] == [
        "local_digital_twin_simulation"
    ]
    assert "live_failover" in out["chaos_claim_gate"]["blocked_claim_ids"]
    assert out["cross_plane_claim_gate"]["allowed"] is False

    integration_none = SimpleNamespace(run_chaos_test=AsyncMock(return_value=None))
    with pytest.raises(HTTPException) as exc_none:
        await mod.run_chaos_test(req, integration=integration_none)
    assert exc_none.value.status_code == 500


@pytest.mark.asyncio
async def test_audit_endpoints(monkeypatch):
    monkeypatch.setattr(mod, "V3_AVAILABLE", True)
    audit = SimpleNamespace(
        records=[{}],
        add_record=lambda **kwargs: {
            "ipfs_cid": "Qm",
            "merkle_root": "abc",
            "timestamp": "t",
        },
        get_records=lambda record_type=None: [{"type": "x"}],
        get_statistics=lambda: {"total_records": 1},
    )
    add_req = mod.AuditRecordRequest(record_type="security", data={"a": 1}, auditor="u")
    added = await mod.add_audit_record(add_req, audit_trail=audit)
    assert added["ipfs_cid"] == "Qm"
    assert added["local_audit_record_claim_allowed"] is True
    assert added["external_storage_finality_confirmed"] is False
    assert added["trust_finality_confirmed"] is False
    assert added["production_readiness_claim_allowed"] is False
    assert added["audit_claim_gate"]["allowed_claim_ids"] == [
        "local_audit_record_write"
    ]
    assert "trust_finality" in added["audit_claim_gate"]["blocked_claim_ids"]
    assert added["cross_plane_claim_gate"]["allowed"] is False

    recs = await mod.get_audit_records(record_type=None, limit=100, audit_trail=audit)
    assert recs["returned"] == 1
    assert recs["local_audit_record_claim_allowed"] is True
    assert recs["trust_finality_confirmed"] is False
    assert recs["audit_claim_gate"]["allowed_claim_ids"] == [
        "local_audit_record_read"
    ]
    stats = await mod.get_audit_statistics(audit_trail=audit)
    assert stats["total_records"] == 1
    assert stats["local_audit_record_claim_allowed"] is True
    assert stats["trust_finality_confirmed"] is False
    assert stats["audit_claim_gate"]["allowed_claim_ids"] == [
        "local_audit_statistics_read"
    ]
