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
    assert ok["version"] == "3.0.0"

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

    recs = await mod.get_audit_records(record_type=None, limit=100, audit_trail=audit)
    assert recs["returned"] == 1
    stats = await mod.get_audit_statistics(audit_trail=audit)
    assert stats["total_records"] == 1
