from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_production_deploy_blocked_preflight_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "run_production_deploy_blocked_preflight_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_blocked_preflight_evidence_retains_fail_closed_metadata(
    tmp_path: Path,
) -> None:
    module = load_module()

    report = module.build_report(tmp_path)

    assert report["schema"] == module.SCHEMA
    assert report["decision"] == module.DECISION_RETAINED
    assert report["ok"] is True
    assert report["summary"]["blocked_before_live_subprocess"] is True
    assert report["summary"]["blocked_before_kubectl_prerequisites"] is True
    assert report["summary"]["safe_actuator_metadata_retained"] is True
    assert report["summary"]["live_deploy_authorized"] is False
    assert report["summary"]["live_deploy_subprocess_attempted"] is False
    assert report["summary"]["kubectl_prerequisites_attempted"] is False
    assert report["summary"]["traffic_shift_claimed"] is False
    assert report["summary"]["customer_traffic_claimed"] is False
    assert report["summary"]["production_slo_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    metadata = report["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    evidence = metadata["evidence"]
    assert (
        claim_gate["schema"]
        == "x0tta6bl4.ops.production_deploy.safe_actuator_claim_gate.v1"
    )
    assert claim_gate["local_deployment_command_attempt_claim_allowed"] is False
    assert claim_gate["local_real_readiness_preflight_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert evidence["component"] == "scripts.deploy.production_deploy"
    assert evidence["action"] == "deploy"
    assert evidence["live_action_authorized"] is False
    assert evidence["live_action_executed"] is False
    assert report["failures"] == []


def test_blocked_preflight_evidence_cli_writes_report(tmp_path: Path) -> None:
    output = tmp_path / "blocked-preflight.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--output-json",
            str(output),
            "--require-retained",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "PRODUCTION_DEPLOY_BLOCKED_PREFLIGHT_EVIDENCE_RETAINED"
    assert written["decision"] == payload["decision"]
    assert written["summary"]["mutates_runtime"] is False
    assert written["summary"]["production_readiness_claimed"] is False


def test_blocked_preflight_validator_rejects_overpromoted_claim() -> None:
    module = load_module()

    failures = module._validate_claim_state(
        deploy_result=False,
        subprocess_attempted=False,
        prerequisites_attempted=False,
        claim_state={
            "live_action_authorized": False,
            "real_readiness_checked": False,
            "real_readiness_passed": False,
            "production_readiness_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "traffic_shift_claim_allowed": False,
            "live_customer_traffic_proven": False,
            "safe_actuator_evidence_metadata": {
                "schema": module.SAFE_ACTUATOR_METADATA_SCHEMA,
                "redacted": True,
                "claim_boundary": "local only",
                "claim_gate": {
                    "schema": (
                        "x0tta6bl4.ops.production_deploy.safe_actuator_claim_gate.v1"
                    ),
                    "redacted": True,
                    "local_deployment_command_attempt_claim_allowed": False,
                    "local_deployment_command_succeeded": False,
                    "local_real_readiness_preflight_claim_allowed": False,
                    "local_real_readiness_preflight_passed": False,
                    "traffic_shift_claim_allowed": False,
                    "live_customer_traffic_claim_allowed": False,
                    "production_readiness_claim_allowed": True,
                    "production_slo_claim_allowed": False,
                    "external_dpi_bypass_confirmed": False,
                    "external_settlement_finality_claim_allowed": False,
                },
                "cross_plane_claim_gate": {"allowed": False},
                "evidence": {
                    "component": "scripts.deploy.production_deploy",
                    "action": "deploy",
                    "raw_output_redacted": True,
                    "live_action_authorized": False,
                    "live_action_executed": False,
                    "real_readiness_checked": False,
                    "real_readiness_passed": False,
                },
            },
        },
    )

    assert "claim_gate_overpromoted:production_readiness_claim_allowed" in failures
