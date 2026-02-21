"""
Focused unit tests for src/core/app.py FastAPI endpoints, helper functions,
and middleware.

Covers: health, status, root, mesh/*, security headers; receive_beacon logic;
get_mesh_peers / get_mesh_routes fallback paths; helper reproducibility.
"""

import os
import time
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

try:
    from src.core.app import (BeaconRequest, _beacons, _generate_training_data,
                              _get_simulated_features, _peers, app,
                              get_mesh_peers, get_mesh_routes, get_mesh_status,
                              pqc_verify, receive_beacon)
except ImportError as exc:
    pytest.skip(f"app.py not importable: {exc}", allow_module_level=True)


@pytest_asyncio.fixture
async def client():
    _peers.clear()
    _beacons.clear()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as tc:
        yield tc


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_200_with_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body


class TestStatusEndpoint:
    @pytest.mark.asyncio
    @patch("src.core.app.get_current_status")
    async def test_status_returns_200(self, mock_gcs, client):
        mock_gcs.return_value = {"status": "healthy", "version": "3.2.0", "uptime": 42}
        resp = await client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        mock_gcs.assert_called_once()


class TestRootEndpoint:
    @pytest.mark.asyncio
    async def test_root_has_endpoints_dict(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "x0tta6bl4"
        assert "version" in data
        assert isinstance(data["endpoints"], dict)
        assert "health" in data["endpoints"]
        assert "status" in data["endpoints"]
        assert "mesh/status" in data["endpoints"]
        assert "mesh/peers" in data["endpoints"]
        assert "mesh/routes" in data["endpoints"]


class TestMeshEndpoints:
    @pytest.mark.asyncio
    @patch(
        "src.network.yggdrasil_client.get_yggdrasil_status",
        return_value={"status": "online", "node": {"public_key": "PK"}},
    )
    async def test_mesh_status_endpoint_success(self, _mock, client):
        resp = await client.get("/mesh/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "online"

    @pytest.mark.asyncio
    @patch(
        "src.network.yggdrasil_client.get_yggdrasil_peers",
        return_value={"status": "ok", "peers": [{"addr": "10.0.0.1"}], "count": 1},
    )
    async def test_mesh_peers_endpoint_success(self, _mock, client):
        resp = await client.get("/mesh/peers")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    @pytest.mark.asyncio
    @patch(
        "src.network.yggdrasil_client.get_yggdrasil_routes",
        return_value={"status": "ok", "routing_table_size": 5},
    )
    async def test_mesh_routes_endpoint_success(self, _mock, client):
        resp = await client.get("/mesh/routes")
        assert resp.status_code == 200
        assert resp.json()["routing_table_size"] == 5


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_security_headers_present(self, client):
        resp = await client.get("/health")
        hdrs = resp.headers
        assert hdrs.get("X-Content-Type-Options") == "nosniff"
        assert hdrs.get("X-Frame-Options") == "SAMEORIGIN"
        assert hdrs.get("X-XSS-Protection") == "1; mode=block"
        assert "max-age=" in hdrs.get("Strict-Transport-Security", "")
        assert hdrs.get("Content-Security-Policy") == "default-src 'self'"


class TestStartupCriticalRoutes:
    @pytest.mark.asyncio
    async def test_openapi_contains_critical_routes(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        paths = set(resp.json().get("paths", {}).keys())
        assert "/api/v1/users/register" in paths
        assert "/api/v1/billing/config" in paths
        assert "/api/v1/ledger/status" in paths
        assert any(path.startswith("/api/v3/swarm") for path in paths)


class TestPqcLogging:
    def test_pqc_verify_fail_closed_when_pqc_unavailable(self, monkeypatch):
        import src.core.app as app_module

        monkeypatch.setattr(app_module, "PQC_LIBOQS_AVAILABLE", False)
        monkeypatch.delenv("X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY", raising=False)

        assert pqc_verify(b"data", b"sig", b"pub") is False

    def test_pqc_verify_does_not_log_sensitive_payloads(self, monkeypatch):
        import src.core.app as app_module

        class _DummySig:
            def verify(self, *_args, **_kwargs):
                return True

        raw_data = b"secret-payload"
        signature = b"sig-bytes"
        public_key = b"public-key"

        monkeypatch.setattr(app_module, "PQC_LIBOQS_AVAILABLE", True)
        monkeypatch.setattr(app_module, "_pqc_sig", _DummySig())
        monkeypatch.setattr(app_module, "_pqc_sig_public_key", public_key)

        captured = []

        def _capture_log(message, *args, **kwargs):
            if args:
                message = message % args
            captured.append(str(message))

        monkeypatch.setattr(app_module.logger, "info", _capture_log)

        assert pqc_verify(raw_data, signature, public_key) is True
        joined_logs = " ".join(captured)
        assert raw_data.decode() not in joined_logs
        assert signature.hex() not in joined_logs
        assert public_key.hex() not in joined_logs


class TestReceiveBeacon:
    @pytest.mark.asyncio
    async def test_receive_beacon_valid(self):
        _peers.clear()
        _beacons.clear()
        req = BeaconRequest(
            node_id="node-alpha",
            timestamp=time.time(),
            neighbors=["node-beta", "node-gamma"],
        )
        result = await receive_beacon(req)

        assert result["accepted"] is True
        assert result["peers_count"] == 1
        assert "node-alpha" in _peers
        assert _peers["node-alpha"]["neighbors"] == ["node-beta", "node-gamma"]
        assert len(_beacons) == 1

    @pytest.mark.asyncio
    async def test_receive_beacon_empty_neighbors(self):
        _peers.clear()
        _beacons.clear()
        req = BeaconRequest(node_id="node-solo", timestamp=time.time())
        result = await receive_beacon(req)

        assert result["accepted"] is True
        assert _peers["node-solo"]["neighbors"] == []


class TestGetMeshStatus:
    @pytest.mark.asyncio
    @patch("src.core.app.get_current_status")
    async def test_returns_collector_data(self, mock_gcs):
        mock_gcs.return_value = {"status": "ok", "peers": ["a", "b"], "routes": []}
        data = await get_mesh_status()
        assert data["status"] == "ok"
        assert data["peers"] == ["a", "b"]
        mock_gcs.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.core.app.get_current_status", side_effect=RuntimeError("boom"))
    async def test_falls_back_on_error(self, _mock):
        _peers.clear()
        _peers["fallback-node"] = {"last_seen": time.time(), "neighbors": []}
        data = await get_mesh_status()
        assert data["status"] == "ok"
        assert "fallback-node" in data["peers"]


class TestGetMeshPeers:
    @pytest.mark.asyncio
    @patch(
        "src.network.yggdrasil_client.get_yggdrasil_peers",
        return_value={"peers": ["peer-a", "peer-b"]},
    )
    async def test_returns_yggdrasil_peers(self, _mock):
        result = await get_mesh_peers()
        assert result == ["peer-a", "peer-b"]

    @pytest.mark.asyncio
    @patch(
        "src.network.yggdrasil_client.get_yggdrasil_peers",
        side_effect=Exception("unavailable"),
    )
    async def test_fallback_to_local_peers(self, _mock):
        _peers.clear()
        _peers["local-node"] = {"last_seen": time.time(), "neighbors": []}
        result = await get_mesh_peers()
        assert "local-node" in result


class TestGetMeshRoutes:
    @patch(
        "src.network.yggdrasil_client.get_yggdrasil_routes",
        side_effect=Exception("no routes"),
    )
    def test_fallback_returns_empty_list(self, _mock):
        result = get_mesh_routes()
        assert result == []


class TestGetSimulatedFeatures:
    def test_reproducibility(self):
        assert _get_simulated_features("node-xyz") == _get_simulated_features(
            "node-xyz"
        )

    def test_different_nodes_differ(self):
        assert _get_simulated_features("node-aaa") != _get_simulated_features(
            "node-bbb"
        )

    def test_value_ranges(self):
        features = _get_simulated_features("range-check")
        assert -80 <= features["rssi"] <= -30
        assert 5 <= features["snr"] <= 25
        assert features["loss_rate"] >= 0
        assert 0 <= features["link_age"] <= 86400
        assert 1 <= features["latency"] <= 100
        assert 0 <= features["throughput"] <= 100
        assert 0 <= features["cpu"] <= 1
        assert 0 <= features["memory"] <= 1

    def test_expected_keys(self):
        features = _get_simulated_features("key-check")
        assert set(features.keys()) == {
            "rssi",
            "snr",
            "loss_rate",
            "link_age",
            "latency",
            "throughput",
            "cpu",
            "memory",
        }


class TestGenerateTrainingData:
    def test_correct_structure(self):
        node_features, edge_index = _generate_training_data(
            num_nodes=8, num_edges=10, seed=99
        )
        assert isinstance(node_features, list)
        assert len(node_features) == 8
        for nf in node_features:
            assert isinstance(nf, dict)
            assert "rssi" in nf

        assert isinstance(edge_index, list)
        assert len(edge_index) <= 10
        for src, dst in edge_index:
            assert 0 <= src < 8
            assert 0 <= dst < 8
            assert src != dst

    def test_no_duplicate_edges(self):
        _, edge_index = _generate_training_data(num_nodes=6, num_edges=15, seed=7)
        assert len(edge_index) == len(set(edge_index))

    def test_deterministic_with_seed(self):
        nf1, ei1 = _generate_training_data(num_nodes=5, num_edges=7, seed=123)
        nf2, ei2 = _generate_training_data(num_nodes=5, num_edges=7, seed=123)
        assert nf1 == nf2
        assert ei1 == ei2
