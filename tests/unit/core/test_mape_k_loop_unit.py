"""Unit tests for src/core/mape_k_loop.py — MAPE-K autonomic loop."""

from dataclasses import dataclass
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.coordination.events import EventBus, EventType
from src.mesh.metric_evidence_policy import build_mesh_metric_evidence_policy
from src.network.yggdrasil_client import YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
from src.services.service_event_trace import service_event_trace_history


# Mock consciousness types before importing the module
class _FakeState(Enum):
    AWAKENED = "AWAKENED"
    CONTEMPLATIVE = "CONTEMPLATIVE"
    EUPHORIC = "EUPHORIC"
    MYSTICAL = "MYSTICAL"


@dataclass
class _FakeMetrics:
    state: _FakeState = _FakeState.AWAKENED
    phi_ratio: float = 0.618

    def to_prometheus_format(self):
        return {"phi_ratio": self.phi_ratio, "state_value": 1.0}


# Patch heavy imports before loading the module under test
_PATCHES = {
    "src.core.consciousness.ConsciousnessEngine": MagicMock,
    "src.core.consciousness.ConsciousnessMetrics": _FakeMetrics,
    "src.monitoring.prometheus_client.PrometheusExporter": MagicMock,
    "src.mesh.network_manager.MeshNetworkManager": MagicMock,
    "src.security.zero_trust.ZeroTrustValidator": MagicMock,
    "src.dao.ipfs_logger.DAOAuditLogger": MagicMock,
}


def _latest_core_mapek_event(bus: EventBus, *, operation: str | None = None):
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="core-mapek-loop",
        limit=50,
    )
    if operation is not None:
        events = [event for event in events if event.data.get("operation") == operation]
    assert events
    return events[-1]


def _mesh_metric_policy(
    *,
    decision_basis: str = "dataplane_confirmed",
    allows_high_risk_mesh_actions: bool = True,
) -> dict:
    raw = {
        "mesh_metric_source_available": 1.0,
        "mesh_metric_dataplane_samples": 0.0,
        "mesh_metric_estimated_samples": 0.0,
        "mesh_metric_fallback_samples": 0.0,
    }
    if decision_basis == "dataplane_confirmed":
        raw["mesh_metric_dataplane_samples"] = 1.0
    elif decision_basis == "estimate_or_fallback_based":
        raw["mesh_metric_estimated_samples"] = 1.0
    elif decision_basis == "metric_source_missing":
        raw["mesh_metric_source_available"] = 0.0

    policy = build_mesh_metric_evidence_policy(raw)
    policy["allows_high_risk_mesh_actions"] = allows_high_risk_mesh_actions
    return policy


@pytest.fixture
def loop(tmp_path):
    """Create a MAPEKLoop with all dependencies mocked."""
    with patch.dict("sys.modules", {}):  # don't pollute
        pass

    with (
        patch("src.core.mape_k_loop.ConsciousnessEngine"),
        patch("src.core.mape_k_loop.MeshNetworkManager"),
        patch("src.core.mape_k_loop.PrometheusExporter"),
        patch("src.core.mape_k_loop.ZeroTrustValidator"),
        patch("src.core.mape_k_loop.DAOAuditLogger"),
    ):
        from src.core.mape_k_loop import MAPEKLoop

    consciousness = MagicMock()
    mesh = MagicMock()
    prometheus = MagicMock()
    zero_trust = MagicMock()
    dao_logger = AsyncMock()

    # Default mock returns
    mesh.get_statistics = AsyncMock(
        return_value={
            "active_peers": 5,
            "avg_latency_ms": 50,
            "packet_loss_percent": 0.01,
            "mttr_minutes": 3.0,
        }
    )
    mesh.set_route_preference = AsyncMock(return_value=True)
    mesh.trigger_aggressive_healing = AsyncMock(return_value=3)
    mesh.trigger_preemptive_checks = AsyncMock()
    zero_trust.get_validation_stats.return_value = {"success_rate": 0.98}

    consciousness.get_consciousness_metrics.return_value = _FakeMetrics()
    consciousness.get_operational_directive.return_value = {
        "route_preference": "balanced",
        "monitoring_interval_sec": 30,
        "message": "All good",
    }
    consciousness.get_trend_analysis.return_value = {"trend": "stable"}

    mk = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        dao_logger=dao_logger,
        event_bus=EventBus(project_root=str(tmp_path)),
    )
    return mk


class TestInit:
    def test_default_attributes(self, loop):
        assert loop.running is False
        assert loop.loop_interval == 60
        assert loop.state_history == []
        assert loop.action_dispatcher is None

    def test_action_dispatcher_param(self, loop):
        from src.dao.governance import ActionDispatcher

        loop2_dispatcher = ActionDispatcher()

        with (
            patch("src.core.mape_k_loop.ConsciousnessEngine"),
            patch("src.core.mape_k_loop.MeshNetworkManager"),
            patch("src.core.mape_k_loop.PrometheusExporter"),
            patch("src.core.mape_k_loop.ZeroTrustValidator"),
        ):
            from src.core.mape_k_loop import MAPEKLoop

            mk = MAPEKLoop(
                consciousness_engine=MagicMock(),
                mesh_manager=MagicMock(),
                prometheus=MagicMock(),
                zero_trust=MagicMock(),
                action_dispatcher=loop2_dispatcher,
            )
        assert mk.action_dispatcher is loop2_dispatcher


class TestMonitorPhase:
    @pytest.mark.asyncio
    async def test_monitor_returns_metrics(self, loop):
        metrics = await loop._monitor()
        assert "cpu_percent" in metrics
        assert "latency_ms" in metrics
        assert "mesh_connectivity" in metrics
        assert "zero_trust_success_rate" in metrics
        assert metrics["mesh_connectivity"] == 5

    @pytest.mark.asyncio
    async def test_monitor_psutil_fallback(self, loop):
        """When psutil is missing, fallback values are used."""
        with patch.dict("sys.modules", {"psutil": None}):
            metrics = await loop._monitor()
        assert metrics["cpu_percent"] == 50.0
        assert metrics["memory_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_monitor_publishes_redacted_mesh_evidence_link(self, loop):
        async def _get_statistics():
            loop.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "get_statistics",
                    "observed_state": True,
                    "peer": "10.0.0.1",
                },
            )
            return {
                "active_peers": 7,
                "avg_latency_ms": 42.0,
                "packet_loss_percent": 1.5,
                "mttr_minutes": 2.0,
            }

        loop.mesh.get_statistics = AsyncMock(side_effect=_get_statistics)

        metrics = await loop._monitor()
        event = _latest_core_mapek_event(loop.event_bus, operation="monitor")
        data = event.data
        event_text = str(data)

        assert metrics["mesh_connectivity"] == 7
        assert data["resource"] == "core:mapek:monitor"
        assert data["service_name"] == "core-mapek-loop"
        assert data["layer"] == "core_mapek_control_spine"
        assert data["read_only"] is True
        assert data["observed_state"] is True
        assert data["control_action"] is False
        assert data["metrics"]["mesh_connectivity"] == 7.0
        assert data["downstream_evidence"]["events_total"] == 1
        assert data["downstream_evidence"]["source_agents"] == ["mesh-network-manager"]
        assert "10.0.0.1" not in event_text

    @pytest.mark.asyncio
    async def test_monitor_links_transitive_yggdrasil_evidence(self, loop):
        async def _get_statistics():
            ygg_event = loop.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "yggdrasil-client",
                {
                    "operation": "get_peers",
                    "observed_state": True,
                    "remote": "200:dead:beef::1",
                },
            )
            loop.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "get_statistics",
                    "observed_state": True,
                    "downstream_evidence": {
                        "source_agents": ["yggdrasil-client"],
                        "event_ids": [ygg_event.event_id],
                        "events_total": 1,
                        "claim_boundaries": [
                            YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
                        ],
                        "claim_boundaries_total": 1,
                        "redacted": True,
                    },
                },
            )
            return {
                "active_peers": 3,
                "avg_latency_ms": 35.0,
                "packet_loss_percent": 0.5,
                "mttr_minutes": 4.0,
            }

        loop.mesh.get_statistics = AsyncMock(side_effect=_get_statistics)

        await loop._monitor()
        event = _latest_core_mapek_event(loop.event_bus, operation="monitor")
        downstream = event.data["downstream_evidence"]
        event_text = str(event.data)

        assert downstream["source_agents"] == [
            "mesh-network-manager",
            "yggdrasil-client",
        ]
        assert downstream["events_total"] == 1
        assert downstream["claim_boundaries"] == [
            YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
        ]
        assert downstream["claim_boundaries_total"] == 1
        assert downstream["transitive"]["yggdrasil-client"]["events_total"] == 1
        assert downstream["transitive"]["yggdrasil-client"]["event_ids"]
        assert downstream["transitive"]["yggdrasil-client"]["claim_boundaries"] == [
            YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
        ]
        assert (
            downstream["transitive"]["yggdrasil-client"]["claim_boundaries_total"]
            == 1
        )
        assert "200:dead:beef" not in event_text

    @pytest.mark.asyncio
    async def test_monitor_carries_metric_source_evidence_without_peer_values(
        self,
        loop,
    ):
        telemetry_event = loop.event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            "mesh-telemetry-collector",
            {
                "operation": "collect_once",
                "observed_state": True,
                "peer": "tls://10.0.0.1:9000",
                "optimizer": {
                    "metric_sources": {
                        "latency_ms": {
                            "source_counts": {
                                "dataplane_probe": 1,
                                "admin_estimate": 0,
                                "default_baseline": 0,
                            },
                            "observed": 0,
                            "probed": 1,
                            "estimated": 0,
                            "fallback_default": 0,
                            "fields": ["ping_avg_rtt_ms"],
                        },
                        "packet_loss_percent": {
                            "source_counts": {"dataplane_probe": 1},
                            "observed": 0,
                            "probed": 1,
                            "estimated": 0,
                            "fallback_default": 0,
                            "fields": ["ping_packet_loss_percent"],
                        },
                    },
                    "dataplane_probe": {
                        "status": "success",
                        "source": "icmp_ping",
                        "attempts": 1,
                        "successes": 1,
                        "matched_peer_count": 1,
                        "events_total": 1,
                        "values_redacted": True,
                    },
                    "metric_enrichment": {
                        "status": "success",
                        "source": "yggdrasil_admin_api",
                        "admin_peer_count": 1,
                        "estimated_peer_count": 1,
                        "matched_peer_count": 1,
                        "events_total": 1,
                        "values_redacted": True,
                    },
                },
            },
        )

        async def _get_statistics():
            loop.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "get_statistics",
                    "observed_state": True,
                },
            )
            return {
                "active_peers": 2,
                "avg_latency_ms": 12.5,
                "packet_loss_percent": 2.5,
                "mttr_minutes": 1.5,
            }

        loop.mesh.get_statistics = AsyncMock(side_effect=_get_statistics)

        metrics = await loop._monitor()
        event = _latest_core_mapek_event(loop.event_bus, operation="monitor")
        downstream = event.data["downstream_evidence"]
        metric_evidence = downstream["metric_source_evidence"]
        event_text = str(event.data)

        assert metrics["mesh_metric_dataplane_samples"] == 1.0
        assert metrics["mesh_metric_estimated_samples"] == 0.0
        assert metrics["mesh_metric_fallback_samples"] == 0.0
        assert metrics["mesh_metric_source_available"] == 1.0
        assert "mesh-telemetry-collector" in downstream["source_agents"]
        assert metric_evidence["status"] == "available"
        assert metric_evidence["event_ids"] == [telemetry_event.event_id]
        assert (
            metric_evidence["metric_sources"]["latency_ms"]["source_counts"]
            == {
                "admin_estimate": 0,
                "dataplane_probe": 1,
                "default_baseline": 0,
            }
        )
        assert metric_evidence["metric_sources"]["latency_ms"]["probed"] == 1
        assert metric_evidence["dataplane_probe"]["status"] == "success"
        assert metric_evidence["dataplane_probe"]["attempts"] == 1
        assert metric_evidence["metric_enrichment"]["source"] == (
            "yggdrasil_admin_api"
        )
        assert "10.0.0.1" not in event_text


class TestAnalyzePhase:
    @pytest.mark.asyncio
    async def test_analyze_calls_consciousness(self, loop):
        raw = {"cpu_percent": 80.0}
        result = await loop._analyze(raw)
        loop.consciousness.get_consciousness_metrics.assert_called_once_with(
            raw, swarm_risk_penalty=0.0
        )
        assert isinstance(result, _FakeMetrics)
        assert result.raw_metrics == raw


class TestPlanPhase:
    def test_plan_returns_directives(self, loop):
        metrics = _FakeMetrics()
        directives = loop._plan(metrics)
        assert "route_preference" in directives
        assert "trend" in directives

    def test_plan_preemptive_on_degrading(self, loop):
        metrics = _FakeMetrics(state=_FakeState.CONTEMPLATIVE)
        metrics.raw_metrics = {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 1.0,
            "mesh_metric_estimated_samples": 0.0,
            "mesh_metric_fallback_samples": 0.0,
        }
        loop.consciousness.get_trend_analysis.return_value = {"trend": "degrading"}
        directives = loop._plan(metrics)
        assert directives.get("preemptive_healing") is True
        assert (
            directives["mesh_metric_evidence_policy"]["decision_basis"]
            == "dataplane_confirmed"
        )

    def test_plan_blocks_estimate_or_fallback_based_high_risk_decision(self, loop):
        metrics = _FakeMetrics(state=_FakeState.AWAKENED)
        metrics.raw_metrics = {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 0.0,
            "mesh_metric_estimated_samples": 1.0,
            "mesh_metric_fallback_samples": 1.0,
        }
        loop.consciousness.get_operational_directive.return_value = {
            "route_preference": "reliability",
            "enable_aggressive_healing": True,
            "monitoring_interval_sec": 30,
        }

        directives = loop._plan(metrics)
        policy = directives["mesh_metric_evidence_policy"]

        assert directives["enable_aggressive_healing"] is False
        assert directives["mesh_high_risk_actions_blocked"] is True
        assert directives["blocked_high_risk_mesh_actions"] == ["aggressive_healing"]
        assert policy["decision_basis"] == "estimate_or_fallback_based"
        assert policy["estimate_or_fallback_based"] is True
        assert policy["allows_high_risk_mesh_actions"] is False

    def test_plan_blocks_high_risk_without_metric_source_evidence(self, loop):
        metrics = _FakeMetrics(state=_FakeState.CONTEMPLATIVE)
        metrics.raw_metrics = {
            "mesh_metric_source_available": 0.0,
            "mesh_metric_dataplane_samples": 0.0,
            "mesh_metric_estimated_samples": 0.0,
            "mesh_metric_fallback_samples": 0.0,
        }
        loop.consciousness.get_operational_directive.return_value = {
            "route_preference": "reliability",
            "enable_aggressive_healing": True,
            "monitoring_interval_sec": 10,
        }
        loop.consciousness.get_trend_analysis.return_value = {"trend": "degrading"}

        directives = loop._plan(metrics)
        policy = directives["mesh_metric_evidence_policy"]

        assert directives["enable_aggressive_healing"] is False
        assert directives["preemptive_healing"] is False
        assert directives["blocked_high_risk_mesh_actions"] == [
            "aggressive_healing",
            "preemptive_healing",
        ]
        assert directives["mesh_high_risk_actions_blocked"] is True
        assert policy["decision_basis"] == "metric_source_missing"
        assert policy["allows_high_risk_mesh_actions"] is False


class TestExecutePhase:
    @pytest.mark.asyncio
    async def test_execute_route_preference(self, loop):
        directives = {"route_preference": "low_latency"}
        actions = await loop._execute(directives)
        loop.mesh.set_route_preference.assert_called_once_with("low_latency")
        assert "route_preference=low_latency" in actions

        event = _latest_core_mapek_event(
            loop.event_bus,
            operation="set_route_preference",
        )
        data = event.data
        assert data["safe_actuator"] is True
        assert data["control_action"] is True
        assert data["success"] is True
        assert data["context"] == {
            "route_preference": "low_latency",
            "values_redacted": True,
        }

    @pytest.mark.asyncio
    async def test_execute_links_mesh_action_downstream_evidence(self, loop):
        async def _set_route_preference(preference):
            event = loop.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "set_route_preference",
                    "control_action": True,
                    "route": "node-secret-1",
                    "preference": preference,
                },
            )
            return bool(event.event_id)

        loop.mesh.set_route_preference = AsyncMock(side_effect=_set_route_preference)

        await loop._execute({"route_preference": "low_latency"})
        event = _latest_core_mapek_event(
            loop.event_bus,
            operation="set_route_preference",
        )
        downstream = event.data["downstream_evidence"]
        event_text = str(event.data)

        assert downstream["source_agents"] == ["mesh-network-manager"]
        assert downstream["events_total"] == 1
        assert downstream["by_source_agent"]["mesh-network-manager"]["events_total"] == 1
        assert "node-secret-1" not in event_text

    @pytest.mark.asyncio
    async def test_execute_links_failed_mesh_action_downstream_evidence(self, loop):
        async def _set_route_preference(preference):
            loop.event_bus.publish(
                EventType.TASK_FAILED,
                "mesh-network-manager",
                {
                    "operation": "set_route_preference",
                    "control_action": True,
                    "route_preference": preference,
                },
            )
            return False

        loop.mesh.set_route_preference = AsyncMock(side_effect=_set_route_preference)

        actions = await loop._execute({"route_preference": "node-secret-1"})
        failed_events = [
            event
            for event in loop.event_bus.get_event_history(
                EventType.TASK_FAILED,
                source_agent="core-mapek-loop",
                limit=20,
            )
            if event.data.get("operation") == "set_route_preference"
        ]
        assert actions == []
        assert failed_events
        data = failed_events[-1].data

        assert data["downstream_evidence"]["source_agents"] == ["mesh-network-manager"]
        assert data["downstream_evidence"]["events_total"] == 1
        assert data["context"]["route_preference"] == "[redacted]"
        assert data["directives"]["route_preference"] == "[redacted]"
        assert "node-secret-1" not in str(data)

    @pytest.mark.asyncio
    async def test_execute_aggressive_healing(self, loop):
        directives = {
            "enable_aggressive_healing": True,
            "mesh_metric_evidence_policy": _mesh_metric_policy(),
        }
        actions = await loop._execute(directives)
        loop.mesh.trigger_aggressive_healing.assert_called_once()
        assert any("aggressive_healing" in a for a in actions)
        event = _latest_core_mapek_event(
            loop.event_bus,
            operation="trigger_aggressive_healing",
        )
        revalidation = event.data["post_action_dataplane_revalidation"]
        gate = revalidation["claim_gate"]
        assert revalidation["required_for_restored_dataplane_claim"] is True
        assert revalidation["dataplane_confirmed"] is False
        assert revalidation["restored_dataplane_claim_allowed"] is False
        assert gate["decision"] == "LOCAL_RECOVERY_LIFECYCLE_ONLY"
        assert gate["local_control_action_claim_allowed"] is True
        assert gate["local_action_applied"] is True
        assert gate["traffic_delivery_claim_allowed"] is False
        assert gate["customer_traffic_claim_allowed"] is False
        assert gate["production_readiness_claim_allowed"] is False
        assert gate["requires_post_action_dataplane_revalidation"] is True
        assert gate["required_evidence"]["event_ids_count_min"] == 1
        assert gate["blockers"] == ["no_bounded_post_action_dataplane_probe_attached"]
        assert "does not prove restored dataplane behavior" in gate["claim_boundary"]

    def test_safe_post_action_claim_gate_rejects_unbacked_dataplane_success(self):
        from src.core.mape_k_loop import _safe_post_action_claim_gate

        gate = _safe_post_action_claim_gate(
            {
                "schema": "x0tta6bl4.core_mapek.post_action_dataplane_claim_gate.v1",
                "operation": "trigger_aggressive_healing",
                "local_control_action_claim_allowed": True,
                "post_action_probe_enabled": True,
                "post_action_probe_target_present": True,
                "post_action_probe_attempted": True,
                "dataplane_confirmed": True,
                "post_action_dataplane_revalidated": True,
                "restored_dataplane_claim_allowed": True,
                "evidence": {"redacted": True},
                "claim_boundary": "bounded fake dataplane probe evidence only",
            }
        )

        assert gate is not None
        assert gate["decision"] == "LOCAL_RECOVERY_LIFECYCLE_ONLY"
        assert gate["dataplane_confirmed"] is True
        assert gate["post_action_dataplane_revalidated"] is False
        assert gate["restored_dataplane_claim_allowed"] is False
        assert "post_action_probe_evidence_missing" in gate["blockers"]
        assert "post_action_probe_source_agent_missing" in gate["blockers"]
        assert gate["traffic_delivery_claim_allowed"] is False
        assert gate["customer_traffic_claim_allowed"] is False
        assert gate["production_readiness_claim_allowed"] is False

    @pytest.mark.asyncio
    async def test_execute_preemptive_healing(self, loop):
        directives = {
            "preemptive_healing": True,
            "mesh_metric_evidence_policy": _mesh_metric_policy(
                decision_basis="dataplane_confirmed",
            ),
        }
        actions = await loop._execute(directives)
        loop.mesh.trigger_preemptive_checks.assert_called_once()
        assert "preemptive_healing_initiated" in actions

    @pytest.mark.asyncio
    async def test_execute_links_mesh_optimization_enforcer_evidence(self, loop):
        probe_claim_boundary = "bounded fake dataplane probe evidence only"

        class FakeOptimizer:
            def optimize_routes(self):
                return {
                    "recommendations": [
                        {
                            "action": "refresh",
                            "route_id": "direct-node-secret-1",
                        }
                    ]
                }

        class FakeEnforcer:
            event_bus = None
            event_project_root = "."
            metric_evidence_policy = None

            def enforce_recommendations(self, recommendations, *, metric_evidence_policy):
                assert recommendations
                self.metric_evidence_policy = metric_evidence_policy
                self.event_bus.publish(
                    EventType.PIPELINE_STAGE_END,
                    "mesh-action-enforcer",
                    {
                        "operation": "enforce_recommendations",
                        "control_action": True,
                        "route_id": "direct-node-secret-1",
                        "downstream_evidence": {
                            "source_agents": ["real-network-adapter"],
                            "event_ids": ["probe-event-1"],
                            "events_total": 1,
                            "claim_boundaries": [probe_claim_boundary],
                            "claim_boundaries_total": 1,
                            "redacted": True,
                        },
                    },
                )

        fake_enforcer = FakeEnforcer()

        with patch(
            "src.mesh.yggdrasil_optimizer.get_optimizer",
            return_value=FakeOptimizer(),
        ):
            import src.mesh.action_enforcer as action_enforcer_module

            with patch.object(
                action_enforcer_module,
                "mesh_action_enforcer",
                fake_enforcer,
            ):
                actions = await loop._execute(
                    {
                        "route_preference": "balanced",
                        "mesh_metric_evidence_policy": _mesh_metric_policy(),
                    }
                )

        event = _latest_core_mapek_event(
            loop.event_bus,
            operation="enforce_mesh_optimization",
        )
        downstream = event.data["downstream_evidence"]

        assert "mesh_optimization=1_actions" in actions
        assert downstream["source_agents"] == ["mesh-action-enforcer"]
        assert downstream["events_total"] == 1
        assert downstream["claim_boundaries"] == [probe_claim_boundary]
        assert downstream["claim_boundaries_total"] == 1
        assert downstream["by_source_agent"]["mesh-action-enforcer"][
            "claim_boundaries"
        ] == [probe_claim_boundary]
        assert (
            event.data["context"]["mesh_metric_decision_basis"]
            == "dataplane_confirmed"
        )
        assert fake_enforcer.metric_evidence_policy["decision_basis"] == (
            "dataplane_confirmed"
        )
        assert "direct-node-secret-1" not in str(event.data)

    @pytest.mark.asyncio
    async def test_execute_blocks_high_risk_with_explicit_missing_metric_policy(
        self,
        loop,
    ):
        directives = {
            "enable_aggressive_healing": True,
            "preemptive_healing": True,
            "mesh_metric_evidence_policy": _mesh_metric_policy(
                decision_basis="metric_source_missing",
                allows_high_risk_mesh_actions=False,
            ),
        }

        actions = await loop._execute(directives)
        blocked_events = loop.event_bus.get_event_history(
            EventType.TASK_BLOCKED,
            source_agent="core-mapek-loop",
            limit=20,
        )
        blocked_operations = {
            event.data["operation"]
            for event in blocked_events
        }

        assert actions == ["route_preference=balanced"]
        loop.mesh.trigger_aggressive_healing.assert_not_called()
        loop.mesh.trigger_preemptive_checks.assert_not_called()
        assert "trigger_aggressive_healing" in blocked_operations
        assert "trigger_preemptive_checks" in blocked_operations
        assert all(
            event.data["context"]["mesh_metric_decision_basis"]
            == "metric_source_missing"
            for event in blocked_events
        )

    @pytest.mark.asyncio
    async def test_execute_dao_actions(self, loop):
        from src.dao.governance import ActionDispatcher, ActionResult
        from unittest.mock import patch

        loop.action_dispatcher = ActionDispatcher()
        directives = {
            "dao_actions": [
                {"type": "restart_node", "node_id": "node-5"},
                {"type": "rotate_keys", "scope": "all"},
            ]
        }
        # Patch _handle_rotate_keys to avoid real XUIAPIClient/VPN calls in unit tests
        with patch.object(
            ActionDispatcher,
            "_handle_rotate_keys",
            staticmethod(
                lambda action: ActionResult("rotate_keys", True, "mocked rotation")
            ),
        ):
            actions = await loop._execute(directives)
        dao_actions = [a for a in actions if a.startswith("dao:")]
        assert len(dao_actions) == 2
        assert all("OK" in a for a in dao_actions)

        dao_events = [
            event
            for event in loop.event_bus.get_event_history(
                EventType.PIPELINE_STAGE_END,
                source_agent="core-mapek-loop",
                limit=20,
            )
            if event.data.get("operation") == "dispatch_dao_action"
        ]
        assert len(dao_events) == 2
        assert all(event.data["safe_actuator"] is True for event in dao_events)
        assert all(
            event.data["downstream_evidence"]["source_agents"] == ["dao-governance"]
            for event in dao_events
        )
        assert all(
            event.data["downstream_evidence"]["events_total"] == 1
            for event in dao_events
        )
        assert "node-5" not in str([event.data for event in dao_events])

    @pytest.mark.asyncio
    async def test_execute_no_dispatcher_skips_dao(self, loop):
        """Without action_dispatcher, dao_actions are ignored."""
        directives = {"dao_actions": [{"type": "restart_node", "node_id": "x"}]}
        actions = await loop._execute(directives)
        assert not any("dao:" in a for a in actions)


class TestEventTrace:
    @pytest.mark.asyncio
    async def test_core_mapek_trace_is_registered(self, loop):
        await loop._execute({"route_preference": "balanced"})

        trace = service_event_trace_history(
            loop.event_bus,
            service_name="core-mapek-loop",
            event_type=EventType.PIPELINE_STAGE_END,
            limit=10,
        )

        assert trace["events_total"] >= 1
        assert trace["filter"]["services"][0]["layer"] == "core_mapek_control_spine"
        assert trace["events"][0]["source_agent"] == "core-mapek-loop"


class TestKnowledgePhase:
    @pytest.mark.asyncio
    async def test_knowledge_exports_prometheus(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": "test"}
        await loop._knowledge(metrics, directives, ["action1"])
        loop.prometheus.set_gauge.assert_called()

    @pytest.mark.asyncio
    async def test_knowledge_stores_state(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": ""}
        await loop._knowledge(metrics, directives, [])
        assert len(loop.state_history) == 1

    @pytest.mark.asyncio
    async def test_knowledge_trims_history(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": ""}
        # Pre-fill history to just under limit
        loop.state_history = [MagicMock()] * 10000
        await loop._knowledge(metrics, directives, [])
        assert len(loop.state_history) == 10000  # trimmed after exceeding

    @pytest.mark.asyncio
    async def test_knowledge_logs_dao_for_euphoric(self, loop):
        metrics = _FakeMetrics(state=_FakeState.EUPHORIC)
        directives = {"message": "peak"}
        loop.dao_logger.log_consciousness_event = AsyncMock(return_value="cid-1")
        await loop._knowledge(metrics, directives, [])
        loop.dao_logger.log_consciousness_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_knowledge_raw_metrics_exported(self, loop):
        metrics = _FakeMetrics()
        directives = {"message": ""}
        raw = {"latency_ms": 120, "cpu_percent": 88, "packet_loss": 0.05}
        await loop._knowledge(metrics, directives, [], raw)
        # Should export mapped gauges
        calls = [c[0] for c in loop.prometheus.set_gauge.call_args_list]
        gauge_names = [c[0] for c in calls]
        assert "mesh_latency_ms" in gauge_names
        assert "system_cpu_percent" in gauge_names


class TestFullCycle:
    @pytest.mark.asyncio
    async def test_execute_cycle(self, loop):
        await loop._execute_cycle()
        # Verify all phases called
        loop.consciousness.get_consciousness_metrics.assert_called_once()
        loop.consciousness.get_operational_directive.assert_called_once()
        assert len(loop.state_history) == 1
        assert loop.loop_interval == 30  # updated from directives


class TestStartStop:
    @pytest.mark.asyncio
    async def test_stop_sets_flag(self, loop):
        await loop.stop()
        assert loop.running is False
