from __future__ import annotations

import json
import shutil
from urllib.error import URLError

import pytest

from scripts.ops import verify_maas_real_agent_control_loop as verifier
from scripts.ops.verify_maas_real_agent_control_loop import (
    READY_DECISION,
    run_verification,
)


def test_local_api_health_ready_treats_startup_refusal_as_not_ready(monkeypatch) -> None:
    def fake_http_json(*args, **kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr(verifier, "_http_json", fake_http_json)

    assert verifier._local_api_health_ready("http://127.0.0.1:1") is False


def test_local_api_health_ready_accepts_http_200(monkeypatch) -> None:
    def fake_http_json(*args, **kwargs):
        return 200, {}, "{}"

    monkeypatch.setattr(verifier, "_http_json", fake_http_json)

    assert verifier._local_api_health_ready("http://127.0.0.1:1") is True


@pytest.mark.slow
def test_real_go_agent_control_loop_smoke(tmp_path) -> None:
    if shutil.which("go") is None:
        pytest.skip("go toolchain is not available")

    target = "10.123.45.67"
    report = run_verification(
        work_dir=str(tmp_path),
        dataplane_probe_target=target,
        timeout_seconds=90.0,
    )

    assert report["ready"] is True
    assert report["decision"] == READY_DECISION
    assert report["agent"]["binary_built"] is True
    assert report["agent"]["process_started"] is True
    assert report["agent"]["node_runtime_credential_hash_stored"] is True
    assert report["agent"]["node_runtime_credential_expiry_stored"] is True
    assert report["agent"]["node_runtime_credential_rotation_observed"] is True
    assert report["agent"]["raw_node_runtime_credential_redacted"] is True
    assert report["agent"]["node_config_fetch_observed"] is True
    assert report["agent"]["heartbeat_observed"] is True
    assert report["agent"]["operator_heal_observed"] is True
    assert report["healing_surface"]["status"] == "healed"
    assert report["healing_surface"]["healing_claim"] == "local_control_action_applied"
    assert report["healing_surface"]["components_healed"] > 0
    assert report["healing_surface"]["post_heal_node_status"] == "healthy"
    assert report["healing_surface"]["post_action_revalidation_present"] is True
    assert report["healing_surface"]["dataplane_confirmed"] is True
    assert report["healing_surface"]["post_action_dataplane_revalidated"] is True
    assert report["healing_surface"]["restored_dataplane_claim_allowed"] is True
    assert report["healing_surface"]["traffic_delivery_claim_allowed"] is False
    assert report["healing_surface"]["customer_traffic_claim_allowed"] is False
    assert report["healing_surface"]["external_reachability_claim_allowed"] is False
    assert report["healing_surface"]["production_slo_claim_allowed"] is False
    assert report["healing_surface"]["production_readiness_claim_allowed"] is False
    assert report["healing_surface"]["raw_target_redacted"] is True

    stage_names = {stage["name"] for stage in report["stages"]}
    assert {
        "local_maas_api_started",
        "mesh_deploy",
        "go_agent_build",
        "go_agent_started",
        "agent_registration_pending",
        "agent_node_runtime_credential_metadata_stored",
        "operator_approved_agent_node",
        "enrollment_token_node_config_rejected",
        "missing_heartbeat_credential_rejected",
        "wrong_heartbeat_credential_rejected",
        "secondary_node_registered_for_negative_acl",
        "secondary_node_approved_for_negative_acl",
        "secondary_node_runtime_credential_rotated",
        "old_rotated_runtime_credential_rejected",
        "heartbeat_path_body_node_mismatch_rejected",
        "cross_node_credential_rejected",
        "secondary_node_revoked_for_negative_acl",
        "revoked_node_credential_rejected",
        "agent_node_config_fetch_observed",
        "agent_heartbeat_persisted",
        "agent_node_marked_offline_for_local_heal",
        "operator_heal_after_real_agent_heartbeat",
    }.issubset(stage_names)

    assert report["entities"]["mesh"]["present"] is True
    assert report["entities"]["node"]["present"] is True
    assert report["dataplane_probe_target"]["raw_value_redacted"] is True
    assert report["dataplane_probe_target"]["requested_raw_value_redacted"] is True
    assert report["dataplane_probe_target"]["local_listener_target"] is True
    assert target not in json.dumps(report, sort_keys=True)
