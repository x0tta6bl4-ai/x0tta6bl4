"""Unit tests for MeshActionEnforcer (action_enforcer.py)."""
import pytest
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.mesh.metric_evidence_policy import build_mesh_metric_evidence_policy


def _metric_policy(
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


@pytest.fixture(autouse=True)
def mock_optimizer():
    with patch("src.mesh.action_enforcer.get_optimizer") as mock_get:
        mock_get.return_value = MagicMock()
        yield mock_get


class TestMeshActionEnforcer:
    def _make_enforcer(self):
        from src.mesh.action_enforcer import MeshActionEnforcer
        return MeshActionEnforcer()

    def test_init_gets_optimizer(self, mock_optimizer):
        self._make_enforcer()
        mock_optimizer.assert_called_once()

    def test_enforce_empty_recommendations(self):
        enforcer = self._make_enforcer()
        # Should not raise
        enforcer.enforce_recommendations([])

    def test_enforce_refresh_calls_restart_peer(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations(
                [{"action": "refresh", "route_id": "direct-10.0.0.1:9000"}],
                metric_evidence_policy=_metric_policy(),
            )
            mock_restart.assert_called_once_with(
                "direct-10.0.0.1:9000",
                peer_uri="",
            )

    def test_enforce_investigate_does_not_call_restart(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([
                {"action": "investigate", "route_id": "direct-10.0.0.1:9000"}
            ])
            mock_restart.assert_not_called()

    def test_enforce_unknown_action_ignored(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([
                {"action": "unknown_action", "route_id": "direct-10.0.0.1:9000"}
            ])
            mock_restart.assert_not_called()

    def test_enforce_multiple_recommendations(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations(
                [
                    {"action": "refresh", "route_id": "direct-10.0.0.1"},
                    {"action": "investigate", "route_id": "direct-10.0.0.2"},
                    {"action": "refresh", "route_id": "direct-10.0.0.3"},
                ],
                metric_evidence_policy=_metric_policy(
                    decision_basis="dataplane_confirmed",
                ),
            )
            assert mock_restart.call_count == 2

    def test_enforce_refresh_with_estimate_or_fallback_policy_is_blocked(self):
        enforcer = self._make_enforcer()

        with patch.object(enforcer, "_restart_peer") as mock_restart:
            result = enforcer.enforce_recommendations(
                [{"action": "refresh", "route_id": "direct-10.0.0.1:9000"}],
                metric_evidence_policy=_metric_policy(
                    decision_basis="estimate_or_fallback_based",
                ),
            )

        mock_restart.assert_not_called()
        assert result["success"] is False
        assert result["blocked_refresh_requests"] == 1
        assert result["metric_evidence_policy"]["decision_basis"] == (
            "estimate_or_fallback_based"
        )

    def test_enforce_refresh_without_metric_policy_is_blocked(self, tmp_path):
        from src.mesh.action_enforcer import MeshActionEnforcer

        bus = EventBus(project_root=str(tmp_path))
        enforcer = MeshActionEnforcer(event_bus=bus)

        with patch.object(enforcer, "_restart_peer") as mock_restart:
            result = enforcer.enforce_recommendations(
                [
                    {
                        "action": "refresh",
                        "route_id": "direct-10.0.0.1:9000",
                        "peer_uri": "tcp://10.0.0.1:9000",
                    }
                ]
            )

        events = bus.get_event_history(
            EventType.TASK_BLOCKED,
            source_agent="mesh-action-enforcer",
            limit=10,
        )
        assert events
        data = events[-1].data

        mock_restart.assert_not_called()
        assert result["success"] is False
        assert data["stage"] == "action_blocked"
        assert data["status"] == "blocked"
        assert data["success"] is False
        assert data["error"] == {
            "type": "MeshMetricEvidencePolicyBlocked",
            "message_redacted": True,
        }
        assert data["result"]["blocked_refresh_requests"] == 1
        assert data["result"]["blocked_by_metric_evidence_policy"] is True
        assert data["result"]["post_action_dataplane_revalidation"]["status"] == (
            "not_attempted"
        )
        assert data["result"]["post_action_dataplane_revalidation"]["reason"] == (
            "action_blocked_by_metric_evidence_policy"
        )
        assert data["result"]["post_action_dataplane_revalidation"][
            "dataplane_confirmed"
        ] is False
        assert data["dataplane_confirmed"] is False
        assert data["post_action_dataplane_revalidated"] is False
        assert data["result"]["metric_evidence_policy"]["decision_basis"] == (
            "policy_missing"
        )
        assert "10.0.0.1" not in str(data)

    def test_enforce_refresh_with_denied_metric_policy_is_blocked(self):
        enforcer = self._make_enforcer()

        with patch.object(enforcer, "_restart_peer") as mock_restart:
            result = enforcer.enforce_recommendations(
                [{"action": "refresh", "route_id": "direct-10.0.0.1:9000"}],
                metric_evidence_policy=_metric_policy(
                    decision_basis="metric_source_missing",
                    allows_high_risk_mesh_actions=False,
                ),
            )

        mock_restart.assert_not_called()
        assert result["success"] is False
        assert result["blocked_refresh_requests"] == 1
        assert result["metric_evidence_policy"]["decision_basis"] == (
            "metric_source_missing"
        )

    def test_enforce_missing_action_key_ignored(self):
        enforcer = self._make_enforcer()
        with patch.object(enforcer, "_restart_peer") as mock_restart:
            enforcer.enforce_recommendations([{"route_id": "direct-10.0.0.1"}])
            mock_restart.assert_not_called()

    def test_enforce_publishes_redacted_control_action_event(self, tmp_path):
        from src.mesh.action_enforcer import MeshActionEnforcer

        bus = EventBus(project_root=str(tmp_path))
        enforcer = MeshActionEnforcer(event_bus=bus)

        enforcer.enforce_recommendations(
            [
                {"action": "refresh", "route_id": "direct-10.0.0.1:9000"},
                {"action": "investigate", "route_id": "direct-10.0.0.2:9000"},
                {"action": "unknown", "route_id": "direct-10.0.0.3:9000"},
            ],
            metric_evidence_policy=_metric_policy(),
        )
        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-action-enforcer",
            limit=10,
        )
        assert events
        data = events[-1].data

        assert data["operation"] == "enforce_recommendations"
        assert data["resource"] == "mesh:action_enforcer:recommendations"
        assert data["service_name"] == "mesh-action-enforcer"
        assert data["layer"] == "mesh_action_enforcer_control_action"
        assert data["control_action"] is True
        assert data["success"] is True
        assert data["recommendations"]["recommendation_count"] == 3
        assert data["recommendations"]["action_counts"] == {
            "investigate": 1,
            "refresh": 1,
            "unknown": 1,
        }
        assert data["result"]["refresh_requests"] == 1
        assert data["result"]["investigate_requests"] == 1
        assert data["result"]["unknown_actions"] == 1
        assert data["result"]["blocked_refresh_requests"] == 0
        assert data["result"]["metric_evidence_policy"]["decision_basis"] == (
            "dataplane_confirmed"
        )
        assert data["result"]["yggdrasil_reconfiguration_applied"] is False
        assert data["result"]["restart_outcomes"] == {"missing_peer_uri": 1}
        assert data["result"]["post_action_dataplane_revalidation"] == {
            "status": "not_attempted",
            "reason": "restart_not_applied",
            "probe_enabled": False,
            "probe_target_present": False,
            "probe_attempted": False,
            "post_action_dataplane_revalidated": False,
            "dataplane_confirmed": False,
            "required_for_restored_dataplane_claim": True,
            "restored_dataplane_claim_allowed": False,
            "claim_gate": {
                "required_for_restored_dataplane_claim": True,
                "restored_dataplane_claim_allowed": False,
                "blockers": ["no_bounded_post_action_dataplane_probe_attached"],
                "required_evidence": {
                    "probe_attempted": True,
                    "dataplane_confirmed": True,
                    "redacted_evidence": True,
                    "event_ids_count_min": 1,
                    "events_total_min": 1,
                    "source_agents_min": 1,
                },
                "observed_evidence": {
                    "probe_attempted": False,
                    "dataplane_confirmed": False,
                    "redacted_evidence": True,
                    "event_ids_count": 0,
                    "events_total": 0,
                    "source_agents_count": 0,
                },
                "claim_boundary": (
                    "Post-action dataplane revalidation metadata only. A local "
                    "restart/refresh result is not treated as dataplane proof unless "
                    "a bounded dataplane probe is attempted and recorded separately."
                ),
                "redacted": True,
            },
            "probe_result": None,
            "evidence": {
                "source_agents": [],
                "event_ids": [],
                "events_total": 0,
                "event_ids_count": 0,
                "claim_boundaries": [],
                "claim_boundaries_total": 0,
                "claim_boundaries_truncated": False,
                "redacted": True,
            },
            "refresh_requests": 1,
            "command_attempts": 0,
            "control_action_applied": False,
            "claim_boundary": (
                "Post-action dataplane revalidation metadata only. A local "
                "restart/refresh result is not treated as dataplane proof unless "
                "a bounded dataplane probe is attempted and recorded separately."
            ),
            "redacted": True,
        }
        assert data["dataplane_confirmed"] is False
        assert data["post_action_dataplane_revalidated"] is False
        assert data["restored_dataplane_claim_allowed"] is False
        assert "10.0.0." not in str(data)

    def test_enforce_includes_bounded_command_metadata_when_apply_enabled(
        self,
        monkeypatch,
        tmp_path,
    ):
        import subprocess
        import src.mesh.action_enforcer as action_enforcer_module
        from src.mesh.action_enforcer import MeshActionEnforcer

        def fake_run(command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ok tcp://10.0.0.1:9000",
                stderr="",
            )

        monkeypatch.setenv("X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY", "1")
        monkeypatch.setattr(
            action_enforcer_module,
            "_find_yggdrasilctl",
            lambda: "/usr/bin/yggdrasilctl",
        )
        monkeypatch.setattr(action_enforcer_module.subprocess, "run", fake_run)

        bus = EventBus(project_root=str(tmp_path))
        enforcer = MeshActionEnforcer(event_bus=bus)

        enforcer.enforce_recommendations(
            [
                {
                    "action": "refresh",
                    "route_id": "direct-route-1",
                    "peer_uri": "tcp://10.0.0.1:9000",
                }
            ],
            metric_evidence_policy=_metric_policy(),
        )
        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-action-enforcer",
            limit=10,
        )
        data = events[-1].data

        assert data["result"]["restart_outcomes"] == {"applied": 1}
        assert data["result"]["command_attempts"] == 2
        assert data["result"]["command_successes"] == 2
        assert data["result"]["yggdrasil_reconfiguration_applied"] is True
        assert data["result"]["command_metadata_total"] == 2
        assert data["result"]["command_metadata"][0]["command"] == "removePeer"
        assert data["result"]["command_metadata"][0]["stdout_sha256"]
        assert data["result"]["metric_evidence_policy"]["decision_basis"] == (
            "dataplane_confirmed"
        )
        assert data["result"]["post_action_dataplane_revalidation"]["status"] == (
            "not_attempted"
        )
        assert data["result"]["post_action_dataplane_revalidation"]["reason"] == (
            "no_post_action_dataplane_probe_configured"
        )
        assert data["result"]["post_action_dataplane_revalidation"][
            "control_action_applied"
        ] is True
        assert data["result"]["post_action_dataplane_revalidation"][
            "dataplane_confirmed"
        ] is False
        assert data["dataplane_confirmed"] is False
        assert data["post_action_dataplane_revalidated"] is False
        assert data["recommendations"]["peer_uri_hashes_total"] == 1
        assert "10.0.0.1" not in str(data)

    def test_enforce_runs_configured_post_action_dataplane_probe_after_apply(
        self,
        monkeypatch,
        tmp_path,
    ):
        import subprocess
        import src.mesh.action_enforcer as action_enforcer_module
        from src.mesh.action_enforcer import MeshActionEnforcer
        probe_claim_boundary = "Local ICMP ping dataplane probe only; target redacted."

        class ProbeProvider:
            def __init__(self):
                self.targets = []

            async def probe_peer(self, target):
                self.targets.append(target)
                return {
                    "status": "ok",
                    "latency_ms": 12.5,
                    "packet_loss_percent": 0.0,
                    "jitter_ms": 1.5,
                    "evidence": {
                        "source_agents": ["real-network-adapter"],
                        "event_ids": ["probe-event-1"],
                        "events_total": 1,
                        "redacted": True,
                    },
                    "claim_boundary": probe_claim_boundary,
                    "redacted": True,
                }

        def fake_run(command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ok tcp://10.0.0.1:9000",
                stderr="",
            )

        monkeypatch.setenv("X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY", "1")
        monkeypatch.setattr(
            action_enforcer_module,
            "_find_yggdrasilctl",
            lambda: "/usr/bin/yggdrasilctl",
        )
        monkeypatch.setattr(action_enforcer_module.subprocess, "run", fake_run)

        bus = EventBus(project_root=str(tmp_path))
        probe_provider = ProbeProvider()
        enforcer = MeshActionEnforcer(
            event_bus=bus,
            enable_post_action_dataplane_probe=True,
            post_action_dataplane_probe_provider=probe_provider,
        )

        result = enforcer.enforce_recommendations(
            [
                {
                    "action": "refresh",
                    "route_id": "direct-route-1",
                    "peer_uri": "tcp://10.0.0.1:9000",
                }
            ],
            metric_evidence_policy=_metric_policy(),
        )
        events = bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent="mesh-action-enforcer",
            limit=10,
        )
        data = events[-1].data
        revalidation = data["result"]["post_action_dataplane_revalidation"]

        assert probe_provider.targets == ["10.0.0.1"]
        assert result["success"] is True
        assert revalidation["status"] == "success"
        assert revalidation["reason"] == "bounded_dataplane_probe_succeeded"
        assert revalidation["probe_enabled"] is True
        assert revalidation["probe_target_present"] is True
        assert revalidation["probe_attempted"] is True
        assert revalidation["post_action_dataplane_revalidated"] is True
        assert revalidation["dataplane_confirmed"] is True
        assert revalidation["restored_dataplane_claim_allowed"] is True
        assert revalidation["claim_gate"]["restored_dataplane_claim_allowed"] is True
        assert revalidation["claim_gate"]["blockers"] == []
        assert revalidation["probe_result"]["latency_ms"] == 12.5
        assert revalidation["probe_result"]["packet_loss_percent"] == 0.0
        assert revalidation["evidence"]["source_agents"] == ["real-network-adapter"]
        assert revalidation["evidence"]["event_ids_count"] == 1
        assert revalidation["evidence"]["claim_boundaries"] == [probe_claim_boundary]
        assert revalidation["evidence"]["claim_boundaries_total"] == 1
        assert data["downstream_evidence"]["source_agents"] == ["real-network-adapter"]
        assert data["downstream_evidence"]["event_ids"] == ["probe-event-1"]
        assert data["downstream_evidence"]["claim_boundaries"] == [
            probe_claim_boundary
        ]
        assert data["downstream_evidence"]["claim_boundaries_total"] == 1
        assert data["dataplane_confirmed"] is True
        assert data["post_action_dataplane_revalidated"] is True
        assert data["restored_dataplane_claim_allowed"] is True
        assert "10.0.0.1" not in str(data)

    def test_enforce_rechecks_env_post_action_probe_flag_at_runtime(
        self,
        monkeypatch,
        tmp_path,
    ):
        import subprocess
        import src.mesh.action_enforcer as action_enforcer_module
        from src.mesh.action_enforcer import MeshActionEnforcer

        class ProbeProvider:
            def __init__(self):
                self.targets = []

            def probe_peer(self, target):
                self.targets.append(target)
                return {
                    "status": "ok",
                    "latency_ms": 8.0,
                    "packet_loss_percent": 0.0,
                    "evidence": {
                        "source_agents": ["real-network-adapter"],
                        "event_ids": ["runtime-probe-event"],
                        "events_total": 1,
                        "redacted": True,
                    },
                    "redacted": True,
                }

        def fake_run(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        monkeypatch.delenv(
            "X0TTA6BL4_MESH_ACTION_ENFORCER_POST_ACTION_PROBE",
            raising=False,
        )
        monkeypatch.setenv("X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY", "1")
        monkeypatch.setattr(
            action_enforcer_module,
            "_find_yggdrasilctl",
            lambda: "/usr/bin/yggdrasilctl",
        )
        monkeypatch.setattr(action_enforcer_module.subprocess, "run", fake_run)

        bus = EventBus(project_root=str(tmp_path))
        probe_provider = ProbeProvider()
        enforcer = MeshActionEnforcer(
            event_bus=bus,
            post_action_dataplane_probe_provider=probe_provider,
        )
        monkeypatch.setenv(
            "X0TTA6BL4_MESH_ACTION_ENFORCER_POST_ACTION_PROBE",
            "1",
        )

        result = enforcer.enforce_recommendations(
            [
                {
                    "action": "refresh",
                    "route_id": "direct-route-1",
                    "peer_uri": "tcp://10.0.0.1:9000",
                }
            ],
            metric_evidence_policy=_metric_policy(),
        )

        revalidation = result["post_action_dataplane_revalidation"]
        assert probe_provider.targets == ["10.0.0.1"]
        assert revalidation["probe_enabled"] is True
        assert revalidation["post_action_dataplane_revalidated"] is True
        assert revalidation["claim_gate"]["restored_dataplane_claim_allowed"] is True

    def test_enforce_failure_event_redacts_route_id(self, tmp_path):
        from src.mesh.action_enforcer import MeshActionEnforcer

        bus = EventBus(project_root=str(tmp_path))
        enforcer = MeshActionEnforcer(event_bus=bus)

        with patch.object(
            enforcer,
            "_restart_peer",
            side_effect=RuntimeError("failed direct-10.0.0.1:9000"),
        ):
            with pytest.raises(RuntimeError):
                enforcer.enforce_recommendations(
                    [{"action": "refresh", "route_id": "direct-10.0.0.1:9000"}],
                    metric_evidence_policy=_metric_policy(),
                )

        events = bus.get_event_history(
            EventType.TASK_FAILED,
            source_agent="mesh-action-enforcer",
            limit=10,
        )
        assert events
        data = events[-1].data

        assert data["operation"] == "enforce_recommendations"
        assert data["success"] is False
        assert data["error"] == {"type": "RuntimeError", "message_redacted": True}
        assert "10.0.0.1" not in str(data)


class TestRestartPeer:
    def _make_enforcer(self):
        from src.mesh.action_enforcer import MeshActionEnforcer
        return MeshActionEnforcer()

    def test_non_direct_route_is_skipped(self):
        enforcer = self._make_enforcer()
        result = enforcer._restart_peer("indirect-10.0.0.1")

        assert result["reason_code"] == "unsupported_route_id"
        assert result["applied"] is False
        assert result["restart_peer_supported"] is False
        assert result["safe_actuator"] is True

    def test_direct_route_extracts_peer_addr(self):
        enforcer = self._make_enforcer()
        result = enforcer._restart_peer("direct-10.0.0.1:9000")

        assert result["reason_code"] == "missing_peer_uri"
        assert result["applied"] is False
        assert result["peer_uri_present"] is False

    def test_empty_route_id_skipped(self):
        enforcer = self._make_enforcer()
        result = enforcer._restart_peer("")

        assert result["reason_code"] == "unsupported_route_id"

    def test_restart_peer_with_peer_uri_is_fail_closed_by_default(self, monkeypatch):
        enforcer = self._make_enforcer()
        monkeypatch.delenv("X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY", raising=False)

        result = enforcer._restart_peer(
            "direct-route-1",
            peer_uri="tcp://10.0.0.1:9000",
        )

        assert result["reason_code"] == "apply_disabled"
        assert result["restart_peer_supported"] is True
        assert result["applied"] is False
        assert result["peer_uri_present"] is True
        assert result["peer_uri_sha256"]
        assert "10.0.0.1" not in str(result)

    def test_restart_peer_runs_bounded_yggdrasilctl_when_enabled(
        self,
        monkeypatch,
    ):
        import subprocess
        import src.mesh.action_enforcer as action_enforcer_module

        enforcer = self._make_enforcer()
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="ok tcp://10.0.0.1:9000",
                stderr="",
            )

        monkeypatch.setenv("X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY", "1")
        monkeypatch.setattr(
            action_enforcer_module,
            "_find_yggdrasilctl",
            lambda: "/usr/bin/yggdrasilctl",
        )
        monkeypatch.setattr(action_enforcer_module.subprocess, "run", fake_run)

        result = enforcer._restart_peer(
            "direct-route-1",
            peer_uri="tcp://10.0.0.1:9000",
        )

        assert [call[0][1] for call in calls] == ["removePeer", "addPeer"]
        assert result["reason_code"] == "applied"
        assert result["applied"] is True
        assert result["command_attempts"] == 2
        assert result["command_successes"] == 2
        assert result["returncodes"] == [0, 0]
        assert result["commands"] == ["removePeer", "addPeer"]
        assert result["output"][0]["stdout_sha256"]
        assert "10.0.0.1" not in str(result)

    def test_restart_peer_records_command_failure_without_raw_output(
        self,
        monkeypatch,
    ):
        import subprocess
        import src.mesh.action_enforcer as action_enforcer_module

        enforcer = self._make_enforcer()

        def fake_run(command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                17,
                stdout="",
                stderr="failed tcp://10.0.0.1:9000",
            )

        monkeypatch.setenv("X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY", "1")
        monkeypatch.setattr(
            action_enforcer_module,
            "_find_yggdrasilctl",
            lambda: "/usr/bin/yggdrasilctl",
        )
        monkeypatch.setattr(action_enforcer_module.subprocess, "run", fake_run)

        result = enforcer._restart_peer(
            "direct-route-1",
            peer_uri="tcp://10.0.0.1:9000",
        )

        assert result["reason_code"] == "command_failed"
        assert result["applied"] is False
        assert result["returncodes"] == [17, 17]
        assert result["command_successes"] == 0
        assert result["output"][0]["stderr_sha256"]
        assert "10.0.0.1" not in str(result)
