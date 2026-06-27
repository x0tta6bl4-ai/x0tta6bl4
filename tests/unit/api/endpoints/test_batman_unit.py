"""Unit tests for src/api/maas/endpoints/batman.py."""

import json
import subprocess
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import batman as mod
from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import event_trace_evidence_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER = UserContext(user_id="owner-1", plan="starter")
OTHER_USER = UserContext(user_id="other-1", plan="starter")


def _mock_health_report(
    node_id="node-1",
    status_value="healthy",
    score=95.0,
    checks=None,
    recommendations=None,
    ts=None,
):
    report = MagicMock()
    report.node_id = node_id
    report.overall_status.value = status_value
    report.overall_score = score
    report.checks = checks or []
    report.recommendations = recommendations or []
    report.timestamp = ts or datetime(2026, 2, 23, 12, 0, 0)
    return report


def _mock_snapshot(node_id="node-1"):
    snap = MagicMock()
    snap.timestamp = datetime(2026, 2, 23, 12, 0, 0)
    snap.originators_count = 5
    snap.neighbors_count = 3
    snap.total_links = 8
    snap.avg_link_quality = 0.85
    snap.routing_entries = 12
    snap.gateways_count = 1
    snap.has_gateway = True
    snap.throughput_mbps = 100.0
    snap.latency_ms = 5.0
    snap.packet_loss_percent = 0.1
    snap.interface_up = True
    return snap


class _BatmanEvidenceRequest:
    def __init__(self, bus: EventBus):
        self.state = SimpleNamespace(event_bus=bus)


def _batman_event_payloads(bus: EventBus, source_agent: str) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=20,
        )
    ]


# ---------------------------------------------------------------------------
# _get_action_description
# ---------------------------------------------------------------------------


class TestGetActionDescription:
    def test_known_action_returns_description(self):
        action = MagicMock()
        action.value = "restart_interface"
        desc = mod._get_action_description(action)
        assert "interface" in desc.lower() or "restart" in desc.lower()

    def test_unknown_action_returns_fallback(self):
        action = MagicMock()
        action.value = "does_not_exist_xyz"
        desc = mod._get_action_description(action)
        assert desc == "No description available"

    def test_all_described_actions_have_non_empty_descriptions(self):
        for value in [
            "restart_interface",
            "reselect_gateway",
            "purge_originators",
            "adjust_routing",
            "isolate_node",
            "reconfigure_link",
            "restart_daemon",
            "escalate",
        ]:
            action = MagicMock()
            action.value = value
            assert mod._get_action_description(action)


# ---------------------------------------------------------------------------
# get_batman_health_monitor / get_batman_metrics_collector / get_batman_mapek_loop
# ---------------------------------------------------------------------------


class TestGetOrCreateInstances:
    def setup_method(self):
        # Clear caches before each test
        mod._batman_health_monitors.clear()
        mod._batman_metrics_collectors.clear()
        mod._batman_mapek_loops.clear()

    def test_health_monitor_created_and_cached(self, monkeypatch):
        fake = MagicMock()
        FakeClass = MagicMock(return_value=fake)

        import src.libx0t.network.batman.health_monitor as hm_mod

        monkeypatch.setattr(hm_mod, "BatmanHealthMonitor", FakeClass)
        with patch.dict("sys.modules", {"src.libx0t.network.batman.health_monitor": hm_mod}):
            m1 = mod.get_batman_health_monitor("n1", "bat0")
            m2 = mod.get_batman_health_monitor("n1", "bat0")

        assert m1 is m2
        assert FakeClass.call_count == 1

    def test_health_monitor_different_interfaces_separate_instances(self, monkeypatch):
        import src.libx0t.network.batman.health_monitor as hm_mod

        original_cls = MagicMock(side_effect=lambda **_kw: MagicMock())
        monkeypatch.setattr(hm_mod, "BatmanHealthMonitor", original_cls)
        with patch.dict("sys.modules", {"src.libx0t.network.batman.health_monitor": hm_mod}):
            m1 = mod.get_batman_health_monitor("n1", "bat0")
            m2 = mod.get_batman_health_monitor("n1", "bat1")

        assert m1 is not m2

    def test_metrics_collector_cached(self, monkeypatch):
        import src.libx0t.network.batman.metrics as met_mod

        fake = MagicMock()
        FakeClass = MagicMock(return_value=fake)
        monkeypatch.setattr(met_mod, "BatmanMetricsCollector", FakeClass)
        with patch.dict("sys.modules", {"src.libx0t.network.batman.metrics": met_mod}):
            c1 = mod.get_batman_metrics_collector("n1", "bat0")
            c2 = mod.get_batman_metrics_collector("n1", "bat0")

        assert c1 is c2
        assert FakeClass.call_count == 1

    def test_mapek_loop_cached(self, monkeypatch):
        import src.libx0t.network.batman.mape_k_integration as mk_mod

        fake = MagicMock()
        FakeClass = MagicMock(return_value=fake)
        monkeypatch.setattr(mk_mod, "BatmanMAPEKLoop", FakeClass)
        with patch.dict("sys.modules", {"src.libx0t.network.batman.mape_k_integration": mk_mod}):
            l1 = mod.get_batman_mapek_loop("n1", "bat0")
            l2 = mod.get_batman_mapek_loop("n1", "bat0")

        assert l1 is l2
        assert FakeClass.call_count == 1


# ---------------------------------------------------------------------------
# _get_node_id_from_mesh
# ---------------------------------------------------------------------------


class TestGetNodeIdFromMesh:
    @pytest.mark.asyncio
    async def test_raises_404_when_mesh_not_found(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: None)
        with pytest.raises(HTTPException) as exc:
            await mod._get_node_id_from_mesh("mesh-x", USER)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_first_node_id_for_owner(self, monkeypatch):
        instance = SimpleNamespace(
            owner_id="owner-1",
            node_instances={"node-a": object(), "node-b": object()},
        )
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        node_id = await mod._get_node_id_from_mesh("mesh-1", USER)
        assert node_id in ("node-a", "node-b")

    @pytest.mark.asyncio
    async def test_raises_404_when_no_nodes(self, monkeypatch):
        instance = SimpleNamespace(owner_id="owner-1", node_instances={})
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        with pytest.raises(HTTPException) as exc:
            await mod._get_node_id_from_mesh("mesh-1", USER)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_calls_require_access_for_non_owner(self, monkeypatch):
        instance = SimpleNamespace(
            owner_id="owner-1",
            node_instances={"node-a": object()},
        )
        called = {"require": 0}

        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        async def _require(_mid, _user):
            called["require"] += 1

        monkeypatch.setattr(mod, "require_mesh_access", _require)

        node_id = await mod._get_node_id_from_mesh("mesh-1", OTHER_USER)
        assert node_id == "node-a"
        assert called["require"] == 1


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


class TestGetBatmanHealth:
    @pytest.mark.asyncio
    async def test_returns_health_response(self, monkeypatch):
        report = _mock_health_report()
        monitor = AsyncMock()
        monitor.run_health_checks = AsyncMock(return_value=report)
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        resp = await mod.get_batman_health("node-1", interface="bat0", user=USER)

        assert resp.node_id == "node-1"
        assert resp.overall_status == "healthy"
        assert resp.overall_score == 95.0
        assert resp.checks == []
        assert resp.recommendations == []
        assert (
            resp.batman_health_claim_gate[
                "local_batman_health_observation_claim_allowed"
            ]
            is True
        )
        assert (
            resp.batman_health_claim_gate["production_readiness_claim_allowed"]
            is False
        )
        assert resp.batman_health_claim_gate["production_slo_claim_allowed"] is False
        assert (
            resp.batman_health_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert (
            resp.batman_health_claim_gate["physical_link_health_claim_allowed"]
            is False
        )
        assert (
            resp.batman_health_claim_gate[
                "kernel_forwarding_correctness_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.health"
        assert resp.cross_plane_claim_gate["allowed"] is False
        assert "2026" in resp.timestamp

    @pytest.mark.asyncio
    async def test_health_checks_serialised(self, monkeypatch):
        check = MagicMock()
        check.check_type.value = "connectivity"
        check.status.value = "ok"
        check.score = 1.0
        check.message = "all good"
        check.details = {"ping": True}

        report = _mock_health_report(checks=[check])
        monitor = AsyncMock()
        monitor.run_health_checks = AsyncMock(return_value=report)
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        resp = await mod.get_batman_health("node-1", user=USER)
        assert len(resp.checks) == 1
        assert resp.checks[0]["type"] == "connectivity"
        assert resp.checks[0]["details"] == {"ping": True}


class TestGetBatmanHealthHistory:
    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, monkeypatch):
        r1 = MagicMock()
        r1.to_dict.return_value = {"score": 90}
        r2 = MagicMock()
        r2.to_dict.return_value = {"score": 85}

        monitor = MagicMock()
        monitor.get_health_history.return_value = [r1, r2]
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        result = await mod.get_batman_health_history("node-1", limit=5, user=USER)
        assert result == [{"score": 90}, {"score": 85}]
        monitor.get_health_history.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_history_sets_claim_boundary_headers(self, monkeypatch):
        response = SimpleNamespace(headers={})
        monitor = MagicMock()
        monitor.get_health_history.return_value = []
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        await mod.get_batman_health_history(
            "node-1",
            limit=5,
            user=USER,
            http_response=response,
        )

        assert (
            response.headers[
                "X-X0TTA6BL4-Local-Batman-Health-Observation-Claim-Allowed"
            ]
            == "true"
        )
        assert response.headers["X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed"] == "false"
        assert (
            response.headers[
                "X-X0TTA6BL4-Physical-Link-Health-Claim-Allowed"
            ]
            == "false"
        )

    @pytest.mark.asyncio
    async def test_empty_history_returns_empty_list(self, monkeypatch):
        monitor = MagicMock()
        monitor.get_health_history.return_value = []
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        result = await mod.get_batman_health_history("node-1", limit=10, user=USER)
        assert result == []


class TestGetBatmanHealthTrend:
    @pytest.mark.asyncio
    async def test_returns_trend_dict(self, monkeypatch):
        trend_data = {"direction": "improving", "delta": 5.0}
        monitor = MagicMock()
        monitor.get_health_trend.return_value = trend_data
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        result = await mod.get_batman_health_trend("node-1", window=10, user=USER)
        assert result == trend_data
        monitor.get_health_trend.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_trend_sets_claim_boundary_headers(self, monkeypatch):
        response = SimpleNamespace(headers={})
        monitor = MagicMock()
        monitor.get_health_trend.return_value = {"direction": "stable"}
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

        await mod.get_batman_health_trend(
            "node-1",
            window=10,
            user=USER,
            http_response=response,
        )

        assert (
            response.headers[
                "X-X0TTA6BL4-Kernel-Forwarding-Correctness-Claim-Allowed"
            ]
            == "false"
        )


# ---------------------------------------------------------------------------
# Metrics endpoints
# ---------------------------------------------------------------------------


class TestGetBatmanMetrics:
    @pytest.mark.asyncio
    async def test_returns_metrics_response(self, monkeypatch):
        snap = _mock_snapshot()
        collector = AsyncMock()
        collector.collect = AsyncMock(return_value=snap)
        monkeypatch.setattr(mod, "get_batman_metrics_collector", lambda _n, _i: collector)

        resp = await mod.get_batman_metrics("node-1", interface="bat0", user=USER)

        assert resp.node_id == "node-1"
        assert resp.originators_count == 5
        assert resp.neighbors_count == 3
        assert resp.total_links == 8
        assert resp.has_gateway is True
        assert resp.interface_up is True
        assert (
            resp.batman_metrics_claim_gate[
                "local_batman_metrics_observation_claim_allowed"
            ]
            is True
        )
        assert (
            resp.batman_metrics_claim_gate["production_readiness_claim_allowed"]
            is False
        )
        assert (
            resp.batman_metrics_claim_gate["production_slo_claim_allowed"] is False
        )
        assert (
            resp.batman_metrics_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert (
            resp.batman_metrics_claim_gate["external_dpi_bypass_claim_allowed"]
            is False
        )
        assert (
            resp.batman_metrics_claim_gate["settlement_finality_claim_allowed"]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.metrics"
        assert resp.cross_plane_claim_gate["allowed"] is False

    @pytest.mark.asyncio
    async def test_collect_is_called(self, monkeypatch):
        snap = _mock_snapshot()
        collector = AsyncMock()
        collector.collect = AsyncMock(return_value=snap)
        monkeypatch.setattr(mod, "get_batman_metrics_collector", lambda _n, _i: collector)

        await mod.get_batman_metrics("node-1", user=USER)
        collector.collect.assert_awaited_once()


class TestGetBatmanMetricsPrometheus:
    @pytest.mark.asyncio
    async def test_returns_prometheus_string(self, monkeypatch):
        collector = MagicMock()
        collector.collect = AsyncMock(return_value=MagicMock())
        collector.get_metrics_output = MagicMock(return_value="# HELP batman_up\nbatman_up 1\n")
        monkeypatch.setattr(mod, "get_batman_metrics_collector", lambda _n, _i: collector)

        result = await mod.get_batman_metrics_prometheus("node-1", user=USER)
        assert "x0tta6bl4_claim_gate_schema" in result
        assert "x0tta6bl4_dataplane_delivery_claim_allowed false" in result
        assert "batman_up" in result

    @pytest.mark.asyncio
    async def test_collect_called_before_output(self, monkeypatch):
        call_order = []

        async def _collect():
            call_order.append("collect")
            return MagicMock()

        def _output():
            call_order.append("output")
            return ""

        collector = MagicMock()
        collector.collect = _collect
        collector.get_metrics_output = _output
        monkeypatch.setattr(mod, "get_batman_metrics_collector", lambda _n, _i: collector)

        await mod.get_batman_metrics_prometheus("node-1", user=USER)
        assert call_order == ["collect", "output"]


class TestGetBatmanMetricsHistory:
    @pytest.mark.asyncio
    async def test_returns_list_of_snapshot_dicts(self, monkeypatch):
        s1 = MagicMock()
        s1.to_dict.return_value = {"throughput": 50.0}
        s2 = MagicMock()
        s2.to_dict.return_value = {"throughput": 60.0}

        collector = MagicMock()
        collector.get_snapshots.return_value = [s1, s2]
        monkeypatch.setattr(mod, "get_batman_metrics_collector", lambda _n, _i: collector)

        result = await mod.get_batman_metrics_history("node-1", limit=5, user=USER)
        assert result == [{"throughput": 50.0}, {"throughput": 60.0}]
        collector.get_snapshots.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_history_sets_claim_boundary_headers(self, monkeypatch):
        response = SimpleNamespace(headers={})
        collector = MagicMock()
        collector.get_snapshots.return_value = []
        monkeypatch.setattr(mod, "get_batman_metrics_collector", lambda _n, _i: collector)

        await mod.get_batman_metrics_history(
            "node-1",
            limit=5,
            user=USER,
            http_response=response,
        )

        assert (
            response.headers[
                "X-X0TTA6BL4-Local-Batman-Metrics-Observation-Claim-Allowed"
            ]
            == "true"
        )
        assert response.headers["X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed"] == "false"
        assert response.headers["X-X0TTA6BL4-Production-SLO-Claim-Allowed"] == "false"


# ---------------------------------------------------------------------------
# Topology endpoint
# ---------------------------------------------------------------------------


class TestGetBatmanTopology:
    @pytest.mark.asyncio
    async def test_raises_503_when_import_fails(self, monkeypatch):
        """If src.libx0t.network.batman.topology is missing, return 503."""

        def _bad_import(name, *args, **kwargs):
            if "topology" in name:
                raise ImportError("no module")
            return original_import(name, *args, **kwargs)

        import builtins

        original_import = builtins.__import__
        monkeypatch.setattr(builtins, "__import__", _bad_import)

        with pytest.raises(HTTPException) as exc:
            await mod.get_batman_topology("node-1", user=USER)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_returns_topology_response(self, monkeypatch):
        topo = MagicMock()
        topo.nodes = {}
        topo.links = {}
        topo.routing_table = {"10.0.0.2": "aa:bb:cc:dd:ee:ff"}
        topo.get_topology_stats.return_value = {
            "mesh_id": "default",
            "local_node_id": "node-1",
            "total_nodes": 0,
            "total_links": 0,
            "mesh_diameter": 3,
        }
        FakeMeshTopology = MagicMock(return_value=topo)

        fake_mod = MagicMock()
        fake_mod.MeshTopology = FakeMeshTopology
        fake_mod.MeshNode = MagicMock()
        fake_mod.MeshLink = MagicMock()
        fake_mod.LinkQuality = MagicMock()

        with patch.dict("sys.modules", {"src.libx0t.network.batman.topology": fake_mod}):
            resp = await mod.get_batman_topology("node-1", user=USER)

        assert resp.mesh_id == "default"
        assert resp.local_node_id == "node-1"
        assert resp.routing_table == {"10.0.0.2": "aa:bb:cc:dd:ee:ff"}
        assert resp.mesh_diameter == 3
        assert (
            resp.batman_topology_claim_gate[
                "local_batman_topology_observation_claim_allowed"
            ]
            is True
        )
        assert (
            resp.batman_topology_claim_gate["production_readiness_claim_allowed"]
            is False
        )
        assert (
            resp.batman_topology_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert (
            resp.batman_topology_claim_gate[
                "routing_convergence_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.topology"
        assert resp.cross_plane_claim_gate["allowed"] is False
        summary = mod._topology_response_summary(resp)
        assert summary["batman_topology_claim_gate_present"] is True
        assert summary["cross_plane_claim_gate_present"] is True
        assert summary["routing_convergence_claim_allowed"] is False


# ---------------------------------------------------------------------------
# Originators endpoint
# ---------------------------------------------------------------------------


class TestGetBatmanOriginators:
    @pytest.mark.asyncio
    async def test_raises_503_when_batctl_not_found(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise FileNotFoundError("batctl")

        monkeypatch.setattr(subprocess, "run", _raise)
        with pytest.raises(HTTPException) as exc:
            await mod.get_batman_originators("node-1", user=USER)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_raises_504_on_timeout(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise subprocess.TimeoutExpired(["batctl"], 5)

        monkeypatch.setattr(subprocess, "run", _raise)
        with pytest.raises(HTTPException) as exc:
            await mod.get_batman_originators("node-1", user=USER)
        assert exc.value.status_code == 504

    @pytest.mark.asyncio
    async def test_returns_empty_originators_on_batctl_error(self, monkeypatch):
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

        resp = await mod.get_batman_originators("node-1", interface="bat0", user=USER)
        assert resp.originators == []
        assert resp.count == 0
        assert resp.node_id == "node-1"

    @pytest.mark.asyncio
    async def test_parses_originator_output(self, monkeypatch):
        # Two header lines + two data lines
        stdout = (
            "B.A.T.M.A.N. adv 2022.3\n"
            "Originator    last-seen  next-hop    outgoing-interface  Potential nexthops ...\n"
            "aa:bb:cc:dd:ee:01 0.160s aa:bb:cc:dd:ee:01  bat0 [ aa:bb:cc:dd:ee:01 (255)]\n"
            "aa:bb:cc:dd:ee:02 0.320s aa:bb:cc:dd:ee:02  bat0 [ aa:bb:cc:dd:ee:02 (200)]\n"
        )
        result = MagicMock()
        result.returncode = 0
        result.stdout = stdout
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

        resp = await mod.get_batman_originators("node-1", interface="bat0", user=USER)
        assert resp.count == 2
        assert resp.originators[0]["mac"] == "aa:bb:cc:dd:ee:01"
        assert resp.interface == "bat0"
        assert (
            resp.batman_topology_claim_gate[
                "local_batctl_observation_claim_allowed"
            ]
            is True
        )
        assert resp.batman_topology_claim_gate["surface"] == "maas_batman.originators"
        assert (
            resp.batman_topology_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert (
            resp.batman_topology_claim_gate[
                "routing_convergence_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.originators"
        assert resp.cross_plane_claim_gate["allowed"] is False


# ---------------------------------------------------------------------------
# Gateways endpoint
# ---------------------------------------------------------------------------


class TestGetBatmanGateways:
    @pytest.mark.asyncio
    async def test_raises_503_when_batctl_not_found(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise FileNotFoundError("batctl")

        monkeypatch.setattr(subprocess, "run", _raise)
        with pytest.raises(HTTPException) as exc:
            await mod.get_batman_gateways("node-1", user=USER)
        assert exc.value.status_code == 503

    @pytest.mark.asyncio
    async def test_raises_504_on_timeout(self, monkeypatch):
        call_count = {"n": 0}

        def _raise(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise subprocess.TimeoutExpired(["batctl"], 5)

        monkeypatch.setattr(subprocess, "run", _raise)
        with pytest.raises(HTTPException) as exc:
            await mod.get_batman_gateways("node-1", user=USER)
        assert exc.value.status_code == 504

    @pytest.mark.asyncio
    async def test_no_gateways_returns_empty(self, monkeypatch):
        call_count = {"n": 0}

        def _run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            call_count["n"] += 1
            if call_count["n"] == 1:
                result.stdout = "No gateways in range ...\n"
            else:
                result.stdout = "client"
            return result

        monkeypatch.setattr(subprocess, "run", _run)

        resp = await mod.get_batman_gateways("node-1", interface="bat0", user=USER)
        assert resp.gateways == []
        assert resp.has_selected is False
        assert resp.gateway_mode == "client"

    @pytest.mark.asyncio
    async def test_selected_gateway_detected(self, monkeypatch):
        call_count = {"n": 0}

        def _run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            call_count["n"] += 1
            if call_count["n"] == 1:
                result.stdout = "=> aa:bb:cc:dd:ee:01 (100) bat0\naa:bb:cc:dd:ee:02 (80) bat0\n"
            else:
                result.stdout = "server"
            return result

        monkeypatch.setattr(subprocess, "run", _run)

        resp = await mod.get_batman_gateways("node-1", interface="bat0", user=USER)
        assert resp.has_selected is True
        assert resp.gateway_mode == "server"
        assert resp.count >= 1
        assert (
            resp.batman_topology_claim_gate[
                "local_batctl_observation_claim_allowed"
            ]
            is True
        )
        assert resp.batman_topology_claim_gate["surface"] == "maas_batman.gateways"
        assert (
            resp.batman_topology_claim_gate["dataplane_delivery_claim_allowed"]
            is False
        )
        assert (
            resp.batman_topology_claim_gate[
                "routing_convergence_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.gateways"
        assert resp.cross_plane_claim_gate["allowed"] is False


# ---------------------------------------------------------------------------
# MAPE-K endpoints
# ---------------------------------------------------------------------------


class TestGetBatmanMAPEKStatus:
    @pytest.mark.asyncio
    async def test_returns_status_response(self, monkeypatch):
        status_data = {
            "node_id": "node-1",
            "interface": "bat0",
            "running": True,
            "cycle_count": 42,
            "auto_heal": True,
            "last_health_report": None,
            "knowledge_stats": {"entries": 10},
        }
        loop = MagicMock()
        loop.get_status.return_value = status_data
        monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

        resp = await mod.get_batman_mapek_status("node-1", user=USER)
        assert resp.node_id == "node-1"
        assert resp.running is True
        assert resp.cycle_count == 42
        assert resp.knowledge_stats == {"entries": 10}
        assert (
            resp.batman_control_claim_gate[
                "local_batman_mapek_control_claim_allowed"
            ]
            is True
        )
        assert (
            resp.batman_control_claim_gate[
                "restored_dataplane_claim_allowed"
            ]
            is False
        )
        assert (
            resp.batman_control_claim_gate[
                "autonomous_remediation_completion_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.mapek.status"
        assert resp.cross_plane_claim_gate["allowed"] is False


class TestRunBatmanMAPEKCycle:
    @pytest.mark.asyncio
    async def test_runs_cycle_and_returns_result(self, monkeypatch):
        cycle_result = {
            "cycle_id": 7,
            "node_id": "node-1",
            "started_at": "2026-02-23T12:00:00",
            "completed_at": "2026-02-23T12:00:01",
            "duration_seconds": 1.0,
            "success": True,
            "anomalies_count": 0,
            "anomalies": [],
            "plan": None,
            "execution": None,
        }
        loop = AsyncMock()
        loop.run_cycle = AsyncMock(return_value=cycle_result)
        monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

        resp = await mod.run_batman_mapek_cycle("node-1", auto_heal=True, user=USER)
        assert resp.cycle_id == 7
        assert resp.success is True
        assert resp.anomalies_count == 0
        assert (
            resp.batman_control_claim_gate[
                "local_batman_mapek_control_claim_allowed"
            ]
            is True
        )
        assert (
            resp.batman_control_claim_gate[
                "restored_dataplane_claim_allowed"
            ]
            is False
        )
        assert (
            resp.batman_control_claim_gate[
                "production_route_mutation_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.mapek.cycle"
        assert resp.cross_plane_claim_gate["allowed"] is False

    @pytest.mark.asyncio
    async def test_auto_heal_flag_set_on_loop(self, monkeypatch):
        cycle_result = {
            "cycle_id": 1,
            "node_id": "node-1",
            "started_at": "2026-02-23T12:00:00",
            "completed_at": "2026-02-23T12:00:01",
            "duration_seconds": 0.5,
            "success": True,
        }
        loop = AsyncMock()
        loop.run_cycle = AsyncMock(return_value=cycle_result)
        loop.auto_heal = True
        monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

        await mod.run_batman_mapek_cycle("node-1", auto_heal=False, user=USER)
        assert loop.auto_heal is False


class TestStartBatmanMAPEKLoop:
    @pytest.mark.asyncio
    async def test_with_background_tasks_adds_task(self, monkeypatch):
        loop = MagicMock()
        loop.start = AsyncMock()
        monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

        background_tasks = MagicMock()
        resp = await mod.start_batman_mapek_loop(
            "node-1", background_tasks=background_tasks, user=USER
        )
        assert resp["status"] == "started"
        assert resp["node_id"] == "node-1"
        assert (
            resp["batman_control_claim_gate"][
                "restored_dataplane_claim_allowed"
            ]
            is False
        )
        assert resp["cross_plane_claim_gate"]["surface"] == "maas_batman.mapek.start"
        background_tasks.add_task.assert_called_once_with(loop.start)

    @pytest.mark.asyncio
    async def test_auto_heal_flag_propagated(self, monkeypatch):
        loop = MagicMock()
        loop.auto_heal = True
        monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

        background_tasks = MagicMock()
        await mod.start_batman_mapek_loop(
            "node-1", auto_heal=False, background_tasks=background_tasks, user=USER
        )
        assert loop.auto_heal is False


class TestStopBatmanMAPEKLoop:
    @pytest.mark.asyncio
    async def test_calls_stop_and_returns_status(self, monkeypatch):
        loop = MagicMock()
        monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

        resp = await mod.stop_batman_mapek_loop("node-1", user=USER)
        assert resp["status"] == "stopped"
        assert resp["node_id"] == "node-1"
        assert (
            resp["batman_control_claim_gate"][
                "restored_dataplane_claim_allowed"
            ]
            is False
        )
        assert resp["cross_plane_claim_gate"]["surface"] == "maas_batman.mapek.stop"
        loop.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Healing endpoints
# ---------------------------------------------------------------------------


class TestTriggerBatmanHealing:
    @pytest.mark.asyncio
    async def test_invalid_action_raises_400(self, monkeypatch):
        import src.libx0t.network.batman.mape_k_integration as mk_mod

        # Make BatmanRecoveryAction raise ValueError on unknown value
        real_class = MagicMock(side_effect=ValueError("bad action"))
        monkeypatch.setattr(mk_mod, "BatmanRecoveryAction", real_class)

        real_enum = MagicMock()
        real_enum.__iter__ = MagicMock(return_value=iter([]))
        with patch.dict("sys.modules", {"src.libx0t.network.batman.mape_k_integration": mk_mod}):
            request = mod.BatmanHealingRequest(action="bad_action")
            with pytest.raises(HTTPException) as exc:
                await mod.trigger_batman_healing("node-1", request=request, user=USER)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_successful_heal_returns_response(self, monkeypatch):
        import src.libx0t.network.batman.mape_k_integration as mk_mod

        fake_action = MagicMock()
        fake_action.value = "restart_interface"
        BatmanRecoveryAction = MagicMock(return_value=fake_action)

        fake_executor = AsyncMock()
        fake_executor._execute_action = AsyncMock(
            return_value={"status": "success", "message": "done"}
        )
        BatmanMAPEKExecutor = MagicMock(return_value=fake_executor)

        monkeypatch.setattr(mk_mod, "BatmanRecoveryAction", BatmanRecoveryAction)
        monkeypatch.setattr(mk_mod, "BatmanMAPEKExecutor", BatmanMAPEKExecutor)

        with patch.dict("sys.modules", {"src.libx0t.network.batman.mape_k_integration": mk_mod}):
            request = mod.BatmanHealingRequest(action="restart_interface")
            resp = await mod.trigger_batman_healing("node-1", request=request, user=USER)

        assert resp.success is True
        assert resp.message == "done"
        assert resp.action == "restart_interface"
        assert (
            resp.batman_control_claim_gate[
                "local_batman_healing_control_claim_allowed"
            ]
            is True
        )
        assert (
            resp.batman_control_claim_gate[
                "restored_dataplane_claim_allowed"
            ]
            is False
        )
        assert (
            resp.batman_control_claim_gate[
                "production_route_mutation_claim_allowed"
            ]
            is False
        )
        assert resp.cross_plane_claim_gate["surface"] == "maas_batman.healing"
        assert resp.cross_plane_claim_gate["allowed"] is False

    @pytest.mark.asyncio
    async def test_executor_exception_returns_failure(self, monkeypatch):
        import src.libx0t.network.batman.mape_k_integration as mk_mod

        fake_action = MagicMock()
        BatmanRecoveryAction = MagicMock(return_value=fake_action)

        fake_executor = AsyncMock()
        fake_executor._execute_action = AsyncMock(side_effect=RuntimeError("boom"))
        BatmanMAPEKExecutor = MagicMock(return_value=fake_executor)

        monkeypatch.setattr(mk_mod, "BatmanRecoveryAction", BatmanRecoveryAction)
        monkeypatch.setattr(mk_mod, "BatmanMAPEKExecutor", BatmanMAPEKExecutor)

        with patch.dict("sys.modules", {"src.libx0t.network.batman.mape_k_integration": mk_mod}):
            request = mod.BatmanHealingRequest(action="restart_interface")
            resp = await mod.trigger_batman_healing("node-1", request=request, user=USER)

        assert resp.success is False
        assert "boom" in resp.message
        assert (
            resp.batman_control_claim_gate[
                "restored_dataplane_claim_allowed"
            ]
            is False
        )


class TestGetBatmanHealingActions:
    @pytest.mark.asyncio
    async def test_returns_list_of_actions(self, monkeypatch):
        import src.libx0t.network.batman.mape_k_integration as mk_mod

        a1 = MagicMock()
        a1.value = "restart_interface"
        a2 = MagicMock()
        a2.value = "escalate"

        class FakeEnum:
            def __iter__(self):
                return iter([a1, a2])

        monkeypatch.setattr(mk_mod, "BatmanRecoveryAction", FakeEnum())

        with patch.dict("sys.modules", {"src.libx0t.network.batman.mape_k_integration": mk_mod}):
            http_response = SimpleNamespace(headers={})
            result = await mod.get_batman_healing_actions(
                "node-1", user=USER, http_response=http_response
            )

        assert len(result) == 2
        assert (
            http_response.headers[
                "X-X0TTA6BL4-Restored-Dataplane-Claim-Allowed"
            ]
            == "false"
        )
        values = [r["action"] for r in result]
        assert "restart_interface" in values
        assert "escalate" in values
        for entry in result:
            assert "description" in entry


# ---------------------------------------------------------------------------
# Mesh integration endpoint
# ---------------------------------------------------------------------------


class TestGetMeshBatmanStatus:
    @pytest.mark.asyncio
    async def test_raises_404_when_mesh_not_found(self, monkeypatch):
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: None)
        with pytest.raises(HTTPException) as exc:
            await mod.get_mesh_batman_status("mesh-x", user=USER)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_owner_skips_require_access(self, monkeypatch):
        instance = SimpleNamespace(owner_id="owner-1", node_instances={})
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        called = {"require": 0}

        async def _require(_m, _u):
            called["require"] += 1

        monkeypatch.setattr(mod, "require_mesh_access", _require)

        http_response = SimpleNamespace(headers={})
        resp = await mod.get_mesh_batman_status(
            "mesh-1", user=USER, http_response=http_response
        )
        assert resp["mesh_id"] == "mesh-1"
        assert (
            resp["batman_mesh_status_claim_gate"][
                "local_batman_mesh_status_observation_claim_allowed"
            ]
            is True
        )
        assert (
            resp["batman_mesh_status_claim_gate"][
                "dataplane_delivery_claim_allowed"
            ]
            is False
        )
        assert (
            resp["batman_mesh_status_claim_gate"][
                "routing_convergence_claim_allowed"
            ]
            is False
        )
        assert resp["cross_plane_claim_gate"]["surface"] == "maas_batman.mesh.status"
        assert resp["cross_plane_claim_gate"]["allowed"] is False
        assert (
            http_response.headers[
                "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed"
            ]
            == "false"
        )
        summary = mod._mesh_batman_status_summary(resp)
        assert summary["batman_mesh_status_claim_gate_present"] is True
        assert summary["cross_plane_claim_gate_present"] is True
        assert summary["dataplane_delivery_claim_allowed"] is False
        assert called["require"] == 0

    @pytest.mark.asyncio
    async def test_non_owner_calls_require_access(self, monkeypatch):
        instance = SimpleNamespace(owner_id="owner-1", node_instances={})
        called = {"require": 0}

        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        async def _require(_m, _u):
            called["require"] += 1

        monkeypatch.setattr(mod, "require_mesh_access", _require)

        await mod.get_mesh_batman_status("mesh-1", user=OTHER_USER)
        assert called["require"] == 1

    @pytest.mark.asyncio
    async def test_returns_unknown_status_for_nodes_without_report(self, monkeypatch):
        instance = SimpleNamespace(
            owner_id="owner-1",
            node_instances={"node-a": MagicMock(), "node-b": MagicMock()},
        )
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        monitor = MagicMock()
        monitor.get_last_report.return_value = None
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n: monitor)

        resp = await mod.get_mesh_batman_status("mesh-1", user=USER)
        assert resp["mesh_id"] == "mesh-1"
        for node_status in resp["nodes"]:
            assert node_status["health_status"] == "unknown"
            assert node_status["health_score"] == 0.0

    @pytest.mark.asyncio
    async def test_returns_actual_status_when_report_present(self, monkeypatch):
        instance = SimpleNamespace(
            owner_id="owner-1",
            node_instances={"node-a": MagicMock()},
        )
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        report = MagicMock()
        report.overall_status.value = "degraded"
        report.overall_score = 60.0

        monitor = MagicMock()
        monitor.get_last_report.return_value = report
        monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n: monitor)

        resp = await mod.get_mesh_batman_status("mesh-1", user=USER)
        assert resp["nodes"][0]["health_status"] == "degraded"
        assert resp["nodes"][0]["health_score"] == 60.0
        assert (
            resp["batman_mesh_status_claim_gate"][
                "physical_link_health_claim_allowed"
            ]
            is False
        )

    @pytest.mark.asyncio
    async def test_response_contains_timestamp(self, monkeypatch):
        instance = SimpleNamespace(owner_id="owner-1", node_instances={})
        monkeypatch.setattr(mod, "get_mesh", lambda _mid: instance)

        resp = await mod.get_mesh_batman_status("mesh-1", user=USER)
        assert "timestamp" in resp
        assert "2026" in resp["timestamp"] or len(resp["timestamp"]) > 10


@pytest.mark.asyncio
async def test_batman_health_and_metrics_publish_redacted_observed_state_evidence(
    monkeypatch,
    tmp_path,
):
    node_id = "node-batman-health-secret"
    interface = "bat-secret-health"
    bus = EventBus(str(tmp_path))
    http_request = _BatmanEvidenceRequest(bus)

    report = _mock_health_report(node_id=node_id)
    health_monitor = AsyncMock()
    health_monitor.run_health_checks = AsyncMock(return_value=report)
    monkeypatch.setattr(
        mod,
        "get_batman_health_monitor",
        lambda _node_id, _interface: health_monitor,
    )

    snap = _mock_snapshot(node_id=node_id)
    collector = AsyncMock()
    collector.collect = AsyncMock(return_value=snap)
    monkeypatch.setattr(
        mod,
        "get_batman_metrics_collector",
        lambda _node_id, _interface: collector,
    )

    health = await mod.get_batman_health(
        node_id,
        interface=interface,
        user=USER,
        http_request=http_request,
    )
    metrics = await mod.get_batman_metrics(
        node_id,
        interface=interface,
        user=USER,
        http_request=http_request,
    )

    assert health.node_id == node_id
    assert metrics.node_id == node_id

    health_payloads = _batman_event_payloads(
        bus,
        mod._MODULAR_BATMAN_HEALTH_SOURCE_AGENT,
    )
    metrics_payloads = _batman_event_payloads(
        bus,
        mod._MODULAR_BATMAN_METRICS_SOURCE_AGENT,
    )
    assert len(health_payloads) == 1
    assert len(metrics_payloads) == 1

    health_payload = health_payloads[0]
    metrics_payload = metrics_payloads[0]
    assert health_payload["operation"] == "get_batman_health"
    assert health_payload["source_quality"] == "local_batman_health_observed_state"
    assert health_payload["node_id_hash"]
    assert health_payload["interface_hash"]
    assert health_payload["interface_bucket"] == "other"
    assert health_payload["batman_endpoint_evidence"]["dataplane_confirmed"] is False
    assert health_payload["batman_endpoint_evidence"][
        "kernel_forwarding_confirmed"
    ] is False
    assert health_payload["result_summary"]["batman_health_claim_gate_present"] is True
    assert health_payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        health_payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
    assert (
        health_payload["result_summary"]["dataplane_delivery_claim_allowed"]
        is False
    )
    assert (
        health_payload["result_summary"]["physical_link_health_claim_allowed"]
        is False
    )
    assert metrics_payload["operation"] == "get_batman_metrics"
    assert metrics_payload["source_quality"] == "local_batman_metrics_observed_state"
    assert metrics_payload["result_summary"]["originators_count"] == 5
    assert metrics_payload["result_summary"]["interface_up"] is True
    assert metrics_payload["result_summary"]["batman_metrics_claim_gate_present"] is True
    assert metrics_payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        metrics_payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
    assert (
        metrics_payload["result_summary"]["dataplane_delivery_claim_allowed"]
        is False
    )
    assert (
        metrics_payload["result_summary"]["external_dpi_bypass_claim_allowed"]
        is False
    )

    trace_summary = event_trace_evidence_summary(health_payload)
    assert "batman_endpoint_evidence" in trace_summary["runtime_evidence"][
        "evidence_blocks_present"
    ]

    serialized = json.dumps(health_payloads + metrics_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (node_id, interface):
        assert raw_value not in serialized
        assert raw_value not in raw_log


@pytest.mark.asyncio
async def test_batman_batctl_reads_publish_returncode_and_redacted_output(
    monkeypatch,
    tmp_path,
):
    node_id = "node-batctl-secret"
    interface = "batctl-secret-iface"
    raw_mac = "aa:bb:cc:dd:ee:99"
    stdout = (
        "B.A.T.M.A.N. adv 2022.3\n"
        "Originator    last-seen  next-hop    outgoing-interface\n"
        f"{raw_mac} 0.160s {raw_mac}  {interface}\n"
    )
    result = MagicMock()
    result.returncode = 0
    result.stdout = stdout
    result.stderr = "stderr-secret-value"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)

    bus = EventBus(str(tmp_path))
    http_request = _BatmanEvidenceRequest(bus)

    response = await mod.get_batman_originators(
        node_id,
        interface=interface,
        user=USER,
        http_request=http_request,
    )

    assert response.count == 1
    assert response.originators[0]["mac"] == raw_mac

    payloads = _batman_event_payloads(
        bus,
        mod._MODULAR_BATMAN_TOPOLOGY_SOURCE_AGENT,
    )
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "get_batman_originators"
    assert payload["source_quality"] == "local_batman_topology_observed_state"
    assert payload["batman_endpoint_evidence"]["batctl_evidence"] == {
        "attempted": True,
        "payloads_redacted": True,
    }
    assert payload["result_summary"]["batctl"]["return_code"] == 0
    assert payload["result_summary"]["batctl"]["stdout"]["sha256"]
    assert payload["result_summary"]["batctl"]["stderr"]["sha256"]
    assert payload["result_summary"]["batman_topology_claim_gate_present"] is True
    assert payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        payload["result_summary"]["production_readiness_claim_allowed"]
        is False
    )
    assert (
        payload["result_summary"]["dataplane_delivery_claim_allowed"]
        is False
    )
    assert (
        payload["result_summary"]["routing_convergence_claim_allowed"]
        is False
    )

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (node_id, interface, raw_mac, "stderr-secret-value"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


@pytest.mark.asyncio
async def test_batman_mapek_and_healing_publish_redacted_control_evidence(
    monkeypatch,
    tmp_path,
):
    node_id = "node-mapek-heal-secret"
    target_node = "target-mapek-heal-secret"
    interface = "bat-mapek-secret"
    bus = EventBus(str(tmp_path))
    http_request = _BatmanEvidenceRequest(bus)

    cycle_result = {
        "cycle_id": 7,
        "node_id": node_id,
        "started_at": "2026-02-23T12:00:00",
        "completed_at": "2026-02-23T12:00:01",
        "duration_seconds": 1.0,
        "success": True,
        "anomalies_count": 1,
        "anomalies": [{"node_id": target_node, "reason": "secret-anomaly"}],
        "plan": {"action": "restart_interface", "target": target_node},
        "execution": {"message": "execution-secret"},
    }
    loop = AsyncMock()
    loop.run_cycle = AsyncMock(return_value=cycle_result)
    loop.auto_heal = True
    monkeypatch.setattr(mod, "get_batman_mapek_loop", lambda _n, _i: loop)

    import src.libx0t.network.batman.mape_k_integration as mk_mod

    fake_action = MagicMock()
    fake_action.value = "restart_interface"
    monkeypatch.setattr(mk_mod, "BatmanRecoveryAction", MagicMock(return_value=fake_action))

    fake_executor = AsyncMock()
    fake_executor._execute_action = AsyncMock(
        return_value={"status": "success", "message": "healing-secret-message"}
    )
    monkeypatch.setattr(
        mk_mod,
        "BatmanMAPEKExecutor",
        MagicMock(return_value=fake_executor),
    )

    with patch.dict("sys.modules", {"src.libx0t.network.batman.mape_k_integration": mk_mod}):
        cycle = await mod.run_batman_mapek_cycle(
            node_id,
            interface=interface,
            auto_heal=True,
            user=USER,
            http_request=http_request,
        )
        healing = await mod.trigger_batman_healing(
            node_id,
            request=mod.BatmanHealingRequest(
                action="restart_interface",
                target_node=target_node,
                force=True,
            ),
            interface=interface,
            user=USER,
            http_request=http_request,
        )

    assert cycle.success is True
    assert healing.success is True
    assert (
        cycle.batman_control_claim_gate[
            "autonomous_remediation_completion_claim_allowed"
        ]
        is False
    )
    assert (
        cycle.batman_control_claim_gate["restored_dataplane_claim_allowed"]
        is False
    )
    assert (
        healing.batman_control_claim_gate["production_route_mutation_claim_allowed"]
        is False
    )
    assert (
        healing.batman_control_claim_gate["restored_dataplane_claim_allowed"]
        is False
    )

    mapek_payloads = _batman_event_payloads(
        bus,
        mod._MODULAR_BATMAN_MAPEK_SOURCE_AGENT,
    )
    healing_payloads = _batman_event_payloads(
        bus,
        mod._MODULAR_BATMAN_HEALING_SOURCE_AGENT,
    )
    assert len(mapek_payloads) == 1
    assert len(healing_payloads) == 1

    mapek_payload = mapek_payloads[0]
    healing_payload = healing_payloads[0]
    assert mapek_payload["operation"] == "run_batman_mapek_cycle"
    assert mapek_payload["control_action"] is True
    assert mapek_payload["batman_endpoint_evidence"]["mapek_evidence"] == {
        "attempted": True,
        "payloads_redacted": True,
    }
    assert mapek_payload["batman_endpoint_evidence"][
        "autonomous_remediation_confirmed"
    ] is False
    assert mapek_payload["result_summary"]["batman_control_claim_gate_present"] is True
    assert mapek_payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        mapek_payload["result_summary"][
            "autonomous_remediation_completion_claim_allowed"
        ]
        is False
    )
    assert (
        mapek_payload["result_summary"]["restored_dataplane_claim_allowed"]
        is False
    )
    assert healing_payload["operation"] == "trigger_batman_healing"
    assert healing_payload["action"] == "restart_interface"
    assert healing_payload["target_node_hash"]
    assert healing_payload["batman_endpoint_evidence"]["healing_evidence"] == {
        "attempted": True,
        "payloads_redacted": True,
    }
    assert healing_payload["batman_endpoint_evidence"][
        "production_route_mutation_confirmed"
    ] is False
    assert (
        healing_payload["result_summary"]["batman_control_claim_gate_present"]
        is True
    )
    assert (
        healing_payload["result_summary"]["production_route_mutation_claim_allowed"]
        is False
    )
    assert (
        healing_payload["result_summary"]["restored_dataplane_claim_allowed"]
        is False
    )

    serialized = json.dumps(mapek_payloads + healing_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        node_id,
        target_node,
        interface,
        "secret-anomaly",
        "execution-secret",
        "healing-secret-message",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestBatmanHealingRequest:
    def test_default_force_is_false(self):
        req = mod.BatmanHealingRequest(action="restart_interface")
        assert req.force is False
        assert req.target_node is None

    def test_force_can_be_set(self):
        req = mod.BatmanHealingRequest(action="restart_interface", force=True, target_node="n1")
        assert req.force is True
        assert req.target_node == "n1"
