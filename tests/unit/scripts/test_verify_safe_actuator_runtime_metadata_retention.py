from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_safe_actuator_runtime_metadata_retention.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_safe_actuator_runtime_metadata_retention",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_metadata_retention_passes_in_local_harness(tmp_path: Path) -> None:
    module = load_module()

    report = module.build_report(tmp_path)

    assert report["schema"] == module.SCHEMA
    assert report["ok"] is True
    assert report["decision"] == module.DECISION_RETAINED
    assert report["summary"]["cases_run"] == 25
    assert report["summary"]["events_checked"] == 20
    assert report["summary"]["result_metadata_cases_checked"] == 5
    assert report["summary"]["metadata_events"] == 25
    assert report["summary"]["claim_gates_fail_closed"] is True
    assert report["summary"]["live_spire_or_dataplane_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    assert report["failures"] == []
    case_ids = {case["case"] for case in report["cases"]}
    assert "token_bridge_push_rewards_to_chain" in case_ids
    assert "dao_executor_release_script" in case_ids
    assert "dao_proposal_executor_helm_upgrade" in case_ids
    assert "dao_governance_dispatch_update_config" in case_ids
    assert "governance_contract_create_proposal" in case_ids
    assert "ghost_l3_setup_tun" in case_ids
    assert "ebpf_adjust_route_weights" in case_ids
    assert "maas_governance_rotate_keys" in case_ids
    assert "pqc_rotator_rotate_identity" in case_ids
    assert "mptcp_manager_enable_mptcp" in case_ids
    assert "integration_spine_safe_actuator_event_metadata" in case_ids
    assert "mesh_action_enforcer_yggdrasil_restart" in case_ids
    assert "core_mapek_aggressive_healing_execute" in case_ids
    assert "self_healing_mapek_execute" in case_ids
    assert "pbft_execute_callback" in case_ids
    assert "swarm_mapek_healing_execute" in case_ids
    assert "canary_deployment_rollout" in case_ids
    assert "multi_cloud_deployment_rollout" in case_ids
    assert "ops_canary_rollout_script_result_metadata" in case_ids
    assert "ops_production_monitor_health_result_metadata" in case_ids
    assert "ops_auto_rollback_recommendation_result_metadata" in case_ids
    assert "ops_production_deploy_blocked_preflight_result_metadata" in case_ids
    assert "ledger_event_trace_citation_safe_actuator_result_metadata" in case_ids


def test_ledger_event_trace_case_keeps_callback_claims_bounded(
    tmp_path: Path,
) -> None:
    module = load_module()

    case = module._run_ledger_event_trace_citation_result_case(tmp_path)

    assert case["case"] == "ledger_event_trace_citation_safe_actuator_result_metadata"
    assert case["result_metadata_retained"] is True
    assert case["failures"] == []


def test_core_mapek_case_keeps_post_action_dataplane_claim_blocked(
    tmp_path: Path,
) -> None:
    module = load_module()

    case = module._run_core_mapek_aggressive_healing_case(tmp_path)

    assert case["case"] == "core_mapek_aggressive_healing_execute"
    assert case["metadata_retained"] is True
    assert case["failures"] == []


def test_integration_spine_case_retains_safe_actuator_metadata(
    tmp_path: Path,
) -> None:
    module = load_module()

    case = module._run_integration_spine_case(tmp_path)

    assert case["case"] == "integration_spine_safe_actuator_event_metadata"
    assert case["metadata_retained"] is True
    assert case["failures"] == []


def test_production_monitor_case_ignores_host_proxy_env(
    monkeypatch, tmp_path: Path
) -> None:
    module = load_module()
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:10918/")
    monkeypatch.setenv("all_proxy", "socks://127.0.0.1:10918/")

    case = module._run_ops_production_monitor_health_result_case(tmp_path)

    assert case["case"] == "ops_production_monitor_health_result_metadata"
    assert case["result_metadata_retained"] is True
    assert case["failures"] == []
    assert os.environ["ALL_PROXY"] == "socks://127.0.0.1:10918/"


def test_auto_rollback_case_ignores_host_proxy_env(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:10918/")
    monkeypatch.setenv("all_proxy", "socks://127.0.0.1:10918/")

    case = module._run_ops_auto_rollback_recommendation_result_case(tmp_path)

    assert case["case"] == "ops_auto_rollback_recommendation_result_metadata"
    assert case["result_metadata_retained"] is True
    assert case["failures"] == []
    assert os.environ["ALL_PROXY"] == "socks://127.0.0.1:10918/"


def test_production_deploy_case_blocks_before_live_subprocess(tmp_path: Path) -> None:
    module = load_module()

    case = module._run_ops_production_deploy_blocked_preflight_result_case(tmp_path)

    assert case["case"] == "ops_production_deploy_blocked_preflight_result_metadata"
    assert case["result_metadata_retained"] is True
    assert case["failures"] == []


def test_payload_validator_rejects_missing_metadata() -> None:
    module = load_module()
    event = module.Event(
        event_type=module.EventType.PIPELINE_STAGE_END,
        source_agent="spire-server-client",
        data={
            "stage": "actuator_completed",
            "resource": "identity:spire_server:create_entry",
            "safe_actuator": True,
        },
    )

    failures = module.validate_event_payload(
        event,
        expected_source_agent="spire-server-client",
        expected_resource="identity:spire_server:create_entry",
    )

    assert "metadata_schema_invalid" in failures
    assert "claim_gate_missing" in failures


def test_payload_validator_rejects_overpromoted_claim() -> None:
    module = load_module()
    event = module.Event(
        event_type=module.EventType.PIPELINE_STAGE_END,
        source_agent="spire-agent-manager",
        data={
            "stage": "actuator_completed",
            "resource": "identity:spire_agent:start_agent",
            "safe_actuator": True,
            "safe_actuator_evidence_metadata": {
                "schema": module.SAFE_ACTUATOR_METADATA_SCHEMA,
                "redacted": True,
                "claim_boundary": "local only",
                "claim_gate": {
                    "safe_actuator_result_recorded": True,
                    "redacted": True,
                    "dataplane_delivery_claim_allowed": True,
                },
                "evidence": {
                    "resource": "identity:spire_agent:start_agent",
                    "raw_context_values_redacted": True,
                    "raw_command_output_redacted": True,
                },
            },
        },
    )

    failures = module.validate_event_payload(
        event,
        expected_source_agent="spire-agent-manager",
        expected_resource="identity:spire_agent:start_agent",
    )

    assert "overpromoted_claim:dataplane_delivery_claim_allowed" in failures


def test_result_metadata_validator_rejects_overpromoted_claim() -> None:
    module = load_module()

    failures = module.validate_result_metadata(
        {
            "schema": module.SAFE_ACTUATOR_METADATA_SCHEMA,
            "redacted": True,
            "claim_boundary": "local only",
            "claim_gate": {
                "redacted": True,
                "traffic_shift_claim_allowed": True,
            },
            "cross_plane_claim_gate": {"allowed": False},
            "evidence": {
                "component": "scripts.canary_deployment",
                "action": "deploy_canary_observation",
                "raw_output_redacted": True,
            },
        },
        expected_component="scripts.canary_deployment",
        expected_action="deploy_canary_observation",
    )

    assert "overpromoted_claim:traffic_shift_claim_allowed" in failures


def test_runtime_metadata_retention_cli_require_retained(tmp_path: Path) -> None:
    output = tmp_path / "runtime-retention.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path / "run"),
            "--require-retained",
            "--output-json",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["decision"] == "SAFE_ACTUATOR_RUNTIME_METADATA_RETAINED"
