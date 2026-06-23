from src.mesh.metric_evidence_policy import (
    MESH_METRIC_POLICY_KEY,
    build_mesh_metric_evidence_policy,
    latest_mesh_metric_policy_evidence,
    mesh_metric_policy_allows_high_risk,
    mesh_metric_policy_context,
    safe_mesh_metric_evidence_policy,
)
from src.coordination.events import EventBus, EventType


def test_build_policy_allows_dataplane_confirmed_decisions():
    policy = build_mesh_metric_evidence_policy(
        {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 2.0,
            "mesh_metric_estimated_samples": 0.0,
            "mesh_metric_fallback_samples": 0.0,
        }
    )

    assert MESH_METRIC_POLICY_KEY == "mesh_metric_evidence_policy"
    assert policy["decision_basis"] == "dataplane_confirmed"
    assert policy["control_risk"] == "normal"
    assert policy["allows_high_risk_mesh_actions"] is True
    assert policy["sample_counts"]["dataplane_probe"] == 2


def test_build_policy_blocks_estimate_or_fallback_high_risk_decisions():
    policy = build_mesh_metric_evidence_policy(
        {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 0.0,
            "mesh_metric_estimated_samples": 1.0,
            "mesh_metric_fallback_samples": 1.0,
        }
    )

    assert policy["decision_basis"] == "estimate_or_fallback_based"
    assert policy["control_risk"] == "blocked"
    assert policy["estimate_or_fallback_based"] is True
    assert policy["allows_high_risk_mesh_actions"] is False
    assert mesh_metric_policy_allows_high_risk(policy) is False


def test_build_policy_blocks_missing_metric_source():
    policy = build_mesh_metric_evidence_policy(
        {
            "mesh_metric_source_available": 0.0,
            "mesh_metric_dataplane_samples": 0.0,
            "mesh_metric_estimated_samples": 0.0,
            "mesh_metric_fallback_samples": 0.0,
        }
    )

    assert policy["decision_basis"] == "metric_source_missing"
    assert policy["control_risk"] == "blocked"
    assert policy["allows_high_risk_mesh_actions"] is False
    assert mesh_metric_policy_allows_high_risk(policy) is False


def test_safe_policy_redacts_missing_or_malformed_values():
    policy = safe_mesh_metric_evidence_policy(
        {
            "decision_basis": "dataplane_confirmed",
            "control_risk": "normal",
            "dataplane_confirmed": True,
            "allows_high_risk_mesh_actions": True,
            "sample_counts": {"dataplane_probe": "3", "bad": object()},
        }
    )
    missing = safe_mesh_metric_evidence_policy(None)

    assert policy["policy_present"] is True
    assert policy["sample_counts"] == {"dataplane_probe": 3}
    assert policy["redacted"] is True
    assert missing["policy_present"] is False
    assert missing["decision_basis"] == "policy_missing"
    assert missing["redacted"] is True


def test_policy_context_and_missing_policy_compatibility_mode():
    context = mesh_metric_policy_context(
        build_mesh_metric_evidence_policy(
            {
                "mesh_metric_source_available": 1.0,
                "mesh_metric_dataplane_samples": 0.0,
                "mesh_metric_estimated_samples": 1.0,
                "mesh_metric_fallback_samples": 0.0,
            }
        ),
        high_risk_action="mesh_optimization",
    )

    assert context == {
        "mesh_high_risk_action": "mesh_optimization",
        "mesh_metric_decision_basis": "estimate_or_fallback_based",
        "mesh_metric_control_risk": "blocked",
        "mesh_estimate_or_fallback_based": True,
        "mesh_dataplane_confirmed": False,
    }
    assert mesh_metric_policy_allows_high_risk(None) is False
    assert (
        mesh_metric_policy_allows_high_risk(None, require_present=False)
        is True
    )


def test_latest_policy_evidence_reads_redacted_eventbus_summary(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    policy = build_mesh_metric_evidence_policy(
        {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 1.0,
            "mesh_metric_estimated_samples": 0.0,
            "mesh_metric_fallback_samples": 0.0,
        }
    )
    event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        "core-mapek-loop",
        {
            "operation": "enforce_mesh_optimization",
            "directives": {
                MESH_METRIC_POLICY_KEY: policy,
                "route_id": "direct-10.0.0.1",
            },
        },
    )

    evidence = latest_mesh_metric_policy_evidence(bus)

    assert evidence["status"] == "available"
    assert evidence["source_agents"] == ["core-mapek-loop"]
    assert evidence["event_ids"] == [event.event_id]
    assert (
        evidence[MESH_METRIC_POLICY_KEY]["decision_basis"]
        == "dataplane_confirmed"
    )
    assert evidence["redacted"] is True
    assert "10.0.0.1" not in str(evidence)


def test_latest_policy_evidence_reports_missing_without_bus():
    evidence = latest_mesh_metric_policy_evidence(None)

    assert evidence["status"] == "missing"
    assert evidence["event_ids"] == []
    assert evidence[MESH_METRIC_POLICY_KEY]["decision_basis"] == "policy_missing"
    assert evidence["redacted"] is True
