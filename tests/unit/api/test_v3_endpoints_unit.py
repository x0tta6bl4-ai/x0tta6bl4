"""
Unit tests for src/api/v3_endpoints.py
Tests V3 API endpoints: status, graphsage, stego, chaos, audit.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

pytestmark = pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_integration():
    return MagicMock()


@pytest.fixture
def mock_audit_trail():
    return MagicMock()


@pytest.fixture
def v3_app(mock_integration, mock_audit_trail):
    """App with V3_AVAILABLE=True and mocked dependencies."""
    import src.api.v3_endpoints as mod
    original = mod.V3_AVAILABLE

    mod.V3_AVAILABLE = True

    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[mod.get_v3_integration] = lambda: mock_integration
    app.dependency_overrides[mod.get_audit_trail] = lambda: mock_audit_trail

    client = TestClient(app)
    yield client, mock_integration, mock_audit_trail

    mod.V3_AVAILABLE = original
    app.dependency_overrides.clear()


@pytest.fixture
def v3_unavailable_app(mock_integration, mock_audit_trail):
    """App with V3_AVAILABLE=False."""
    import src.api.v3_endpoints as mod
    original = mod.V3_AVAILABLE

    mod.V3_AVAILABLE = False

    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[mod.get_v3_integration] = lambda: mock_integration
    app.dependency_overrides[mod.get_audit_trail] = lambda: mock_audit_trail

    client = TestClient(app)
    yield client, mock_integration, mock_audit_trail

    mod.V3_AVAILABLE = original
    app.dependency_overrides.clear()


# ===========================================================================
# /api/v3/status
# ===========================================================================

class TestV3Status:

    def test_status_ok(self, v3_app):
        client, integration, _ = v3_app
        integration.get_status.return_value = {"graphsage": True, "stego": True}

        resp = client.get("/api/v3/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "operational"
        assert body["version"] == "3.0.0"
        assert "components" in body

    def test_status_unavailable(self, v3_unavailable_app):
        client, _, _ = v3_unavailable_app
        resp = client.get("/api/v3/status")
        assert resp.status_code == 503


# ===========================================================================
# /api/v3/graphsage/analyze
# ===========================================================================

class TestGraphSAGEAnalyze:

    def test_analyze_success(self, v3_app):
        client, integration, _ = v3_app
        mock_result = MagicMock()
        mock_result.failure_type.value = "anomaly"
        mock_result.confidence = 0.95
        mock_result.recommended_action = "isolate"
        mock_result.severity = "high"
        mock_result.affected_nodes = ["node-1"]

        integration.analyze_with_graphsage = AsyncMock(return_value=mock_result)

        resp = client.post("/api/v3/graphsage/analyze", json={
            "node_features": {"node-1": {"cpu": 0.8, "memory": 0.7}}
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["failure_type"] == "anomaly"
        assert body["confidence"] == 0.95

    def test_analyze_returns_none_raises_error(self, v3_app):
        """When analysis returns None, the 503 HTTPException is caught by the generic
        except block and re-raised as 500."""
        client, integration, _ = v3_app
        integration.analyze_with_graphsage = AsyncMock(return_value=None)

        resp = client.post("/api/v3/graphsage/analyze", json={
            "node_features": {"node-1": {"cpu": 0.5}}
        })
        assert resp.status_code == 500

    def test_analyze_unavailable(self, v3_unavailable_app):
        client, _, _ = v3_unavailable_app
        resp = client.post("/api/v3/graphsage/analyze", json={
            "node_features": {}
        })
        assert resp.status_code == 503

    def test_analyze_exception(self, v3_app):
        client, integration, _ = v3_app
        integration.analyze_with_graphsage = AsyncMock(side_effect=RuntimeError("boom"))

        resp = client.post("/api/v3/graphsage/analyze", json={
            "node_features": {"n": {"x": 1.0}}
        })
        assert resp.status_code == 500


# ===========================================================================
# /api/v3/stego/encode
# ===========================================================================

class TestStegoEncode:

    def test_encode_success(self, v3_app):
        import base64
        client, integration, _ = v3_app
        payload = b"secret data"
        encoded = b"encoded_packet_data"
        integration.encode_packet_stego.return_value = encoded

        resp = client.post("/api/v3/stego/encode", json={
            "payload": base64.b64encode(payload).decode(),
            "protocol_mimic": "http"
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["original_size"] == len(payload)
        assert body["encoded_size"] == len(encoded)
        assert body["protocol"] == "http"

    def test_encode_returns_none(self, v3_app):
        """When encoding returns None, the 503 HTTPException is caught by the generic
        except block and re-raised as 500."""
        import base64
        client, integration, _ = v3_app
        integration.encode_packet_stego.return_value = None

        resp = client.post("/api/v3/stego/encode", json={
            "payload": base64.b64encode(b"data").decode()
        })
        assert resp.status_code == 500

    def test_encode_unavailable(self, v3_unavailable_app):
        import base64
        client, _, _ = v3_unavailable_app
        resp = client.post("/api/v3/stego/encode", json={
            "payload": base64.b64encode(b"x").decode()
        })
        assert resp.status_code == 503


# ===========================================================================
# /api/v3/chaos/run
# ===========================================================================

class TestChaosRun:

    def test_chaos_run_success(self, v3_app):
        client, integration, _ = v3_app
        integration.run_chaos_test = AsyncMock(return_value={
            "scenario": "node_down",
            "survived": True
        })

        resp = client.post("/api/v3/chaos/run", json={
            "scenario": "node_down",
            "intensity": 0.5,
            "duration": 30.0
        })
        assert resp.status_code == 200
        assert resp.json()["survived"] is True

    def test_chaos_run_returns_none(self, v3_app):
        """When chaos test returns None, the 503 HTTPException is caught by the generic
        except block and re-raised as 500."""
        client, integration, _ = v3_app
        integration.run_chaos_test = AsyncMock(return_value=None)

        resp = client.post("/api/v3/chaos/run", json={
            "scenario": "ddos"
        })
        assert resp.status_code == 500

    def test_chaos_unavailable(self, v3_unavailable_app):
        client, _, _ = v3_unavailable_app
        resp = client.post("/api/v3/chaos/run", json={"scenario": "ddos"})
        assert resp.status_code == 503


# ===========================================================================
# /api/v3/audit/*
# ===========================================================================

class TestAuditEndpoints:

    def test_add_audit_record(self, v3_app):
        client, _, audit = v3_app
        audit.add_record.return_value = {
            "ipfs_cid": "QmTest",
            "merkle_root": "abc123",
            "timestamp": "2026-01-01T00:00:00"
        }
        audit.records = [{}]  # length 1 → record_id=0

        resp = client.post("/api/v3/audit/add", json={
            "record_type": "security_event",
            "data": {"action": "login"},
            "auditor": "admin"
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["record_id"] == 0
        assert body["ipfs_cid"] == "QmTest"

    def test_add_audit_unavailable(self, v3_unavailable_app):
        client, _, _ = v3_unavailable_app
        resp = client.post("/api/v3/audit/add", json={
            "record_type": "test",
            "data": {}
        })
        assert resp.status_code == 503

    def test_get_audit_records(self, v3_app):
        client, _, audit = v3_app
        audit.get_records.return_value = [{"type": "a"}, {"type": "b"}]
        audit.records = [{}, {}]

        resp = client.get("/api/v3/audit/records")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["returned"] == 2

    def test_get_audit_records_with_type_filter(self, v3_app):
        client, _, audit = v3_app
        audit.get_records.return_value = [{"type": "security"}]
        audit.records = [{}, {}, {}]

        resp = client.get("/api/v3/audit/records", params={"record_type": "security"})
        assert resp.status_code == 200
        assert resp.json()["returned"] == 1

    def test_get_audit_statistics(self, v3_app):
        client, _, audit = v3_app
        audit.get_statistics.return_value = {
            "total_records": 5,
            "types": {"security": 3, "governance": 2}
        }

        resp = client.get("/api/v3/audit/statistics")
        assert resp.status_code == 200
        assert resp.json()["total_records"] == 5

    def test_get_audit_statistics_unavailable(self, v3_unavailable_app):
        client, _, _ = v3_unavailable_app
        resp = client.get("/api/v3/audit/statistics")
        assert resp.status_code == 503
