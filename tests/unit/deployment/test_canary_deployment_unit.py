import importlib
import os

import pytest

from src.coordination.events import EventBus, EventType

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_import_smoke():
    try:
        mod = importlib.import_module("src.deployment.canary_deployment")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None


def test_status_exposes_claim_boundary_and_false_proof_flags():
    mod = importlib.import_module("src.deployment.canary_deployment")

    canary = mod.CanaryDeployment(config=mod.DeploymentConfig())
    status = canary.get_deployment_status()

    assert status["traffic_shift_claim_allowed"] is False
    assert status["live_customer_traffic_proven"] is False
    assert status["production_readiness_claim_allowed"] is False
    assert status["production_slo_claim_allowed"] is False
    assert status["external_dpi_bypass_confirmed"] is False
    assert status["settlement_finality_confirmed"] is False
    assert "does not prove traffic shifting" in status["claim_boundary"]
    assert status["integration"]["live_actions_authorized"] is False
    metadata = status["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert (
        claim_gate["schema"]
        == "x0tta6bl4.deployment.canary.safe_actuator_claim_gate.v1"
    )
    assert claim_gate["local_canary_metrics_observation_claim_allowed"] is False
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["traffic_shift_claim_allowed"] is False
    assert claim_gate["live_customer_traffic_claim_allowed"] is False
    assert claim_gate["production_slo_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["resource"] == "deployment:canary:get_deployment_status"
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True


def test_rollback_is_recommendation_only_without_live_authorization(monkeypatch):
    mod = importlib.import_module("src.deployment.canary_deployment")
    canary = mod.CanaryDeployment(config=mod.DeploymentConfig())

    def _unexpected_run(*args, **kwargs):
        raise AssertionError("live command should not run")

    monkeypatch.setattr(mod.subprocess, "run", _unexpected_run)

    canary._trigger_rollback("low_success_rate")

    assert canary.current_stage == mod.DeploymentStage.ROLLBACK
    assert canary.current_traffic_percentage == 0.0
    assert canary.last_rollback_result["rollback_recommended"] is True
    assert canary.last_rollback_result["rollback_executed"] is False
    assert canary.last_rollback_result["live_action_authorized"] is False
    assert canary.last_rollback_result["live_action_executed"] is False
    assert canary.last_rollback_result["traffic_shift_claim_allowed"] is False
    claim_gate = canary.last_rollback_result["safe_actuator_evidence_metadata"][
        "claim_gate"
    ]
    assert claim_gate["local_rollback_recommendation_claim_allowed"] is True
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["traffic_shift_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False


def test_cicd_rollback_is_blocked_without_live_authorization(monkeypatch):
    mod = importlib.import_module("src.deployment.canary_deployment")
    canary = mod.CanaryDeployment(config=mod.DeploymentConfig())

    monkeypatch.setenv("CI_SYSTEM", "github")
    monkeypatch.setenv("GITHUB_REPOSITORY", "user/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

    def _unexpected_post(*args, **kwargs):
        raise AssertionError("external CI/CD request should not run")

    import httpx

    monkeypatch.setattr(httpx, "post", _unexpected_post)

    assert canary._trigger_cicd_rollback() is False
    assert canary.last_live_action_result["action"] == "cicd_rollback"
    assert canary.last_live_action_result["live_action_authorized"] is False
    claim_gate = canary.last_live_action_result["safe_actuator_evidence_metadata"][
        "claim_gate"
    ]
    assert claim_gate["action"] == "cicd_rollback"
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["local_canary_rollout_attempt_claim_allowed"] is False
    assert claim_gate["traffic_shift_claim_allowed"] is False
    assert claim_gate["production_slo_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert "secret-token" not in str(canary.last_live_action_result)


def test_deploy_canary_version_publishes_eventbus_safe_actuator_metadata(
    tmp_path,
    monkeypatch,
):
    mod = importlib.import_module("src.deployment.canary_deployment")
    bus = EventBus(str(tmp_path))
    canary = mod.CanaryDeployment(
        config=mod.DeploymentConfig(allow_live_actions=True),
        event_bus=bus,
        node_id="node-canary-test",
    )

    class Result:
        returncode = 0
        stdout = "helm upgrade ok with private rollout detail"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: Result())

    assert canary._deploy_canary_version("v-runtime") is True

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="canary-deployment",
        limit=10,
    )
    payload = events[-1].data
    metadata = payload["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]

    assert payload["stage"] == "actuator_completed"
    assert payload["resource"] == "deployment:canary:deploy_canary_version"
    assert payload["safe_actuator"] is True
    assert payload["node_id"] == "node-canary-test"
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["local_canary_rollout_attempt_claim_allowed"] is True
    assert claim_gate["local_canary_rollout_action_succeeded"] is True
    assert claim_gate["traffic_shift_claim_allowed"] is False
    assert claim_gate["live_customer_traffic_claim_allowed"] is False
    assert claim_gate["production_slo_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["resource"] == "deployment:canary:deploy_canary_version"
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True
    assert "private rollout detail" not in str(payload)
