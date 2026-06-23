from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_dataplane_delivery_operator_flow.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_dataplane_delivery_operator_flow",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_operator_flow_verifier_collects_event_and_proof_gate_accepts_it(
    tmp_path: Path,
) -> None:
    module = load_module()

    report = module.build_report(ROOT, evidence_root=tmp_path)

    assert report["schema"] == module.SCHEMA
    assert report["decision"] == module.DECISION_VERIFIED
    assert report["ok"] is True
    assert report["summary"]["handoff_ready"] is True
    assert report["summary"]["collector_ready"] is True
    assert report["summary"]["event_written"] is True
    assert report["summary"]["proof_gate_artifact_valid"] is True
    assert report["summary"]["cases_run"] == 5
    assert report["summary"]["cases_checked"] == 5
    assert report["summary"]["runs_live_probe"] is False
    assert report["summary"]["mutates_project_runtime"] is False
    assert report["summary"]["writes_temp_eventbus"] is True
    assert report["summary"]["operator_run_evidence_claimed"] is False
    assert report["summary"]["real_operator_run_evidence_retained"] is False
    assert report["summary"]["eventbus_evidence_recognized_by_proof_gate"] is True
    assert report["summary"]["raw_targets_redacted"] is True
    assert report["summary"]["customer_traffic_claimed"] is False
    assert report["summary"]["traffic_delivery_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    assert report["evidence"]["event_id"]
    assert report["evidence"]["matching_events"] == 1
    selected = report["evidence"]["selected_event"]
    assert selected["dataplane_confirmed"] is True
    assert selected["restored_dataplane_claim_allowed"] is True
    assert selected["traffic_delivery_claim_allowed"] is False
    assert selected["customer_traffic_claim_allowed"] is False
    assert selected["production_readiness_claim_allowed"] is False
    assert selected["redacted"] is True
    assert report["failures"] == []


def test_operator_flow_verifier_rejects_overpromoted_artifact() -> None:
    module = load_module()

    failures = module._validate_flow(
        handoff_report={
            "decision": module.handoff.DECISION_READY,
            "ready_for_operator_run": True,
            "mutates_runtime": False,
            "runs_probe": False,
            "writes_eventbus": False,
            "target": {"raw_target_redacted": True},
        },
        collector_report={
            "decision": "DATAPLANE_EVENTBUS_EVIDENCE_READY",
            "event_written": True,
            "ready_for_proof_gate": True,
            "probe": {"target": {"raw_target_redacted": True}},
        },
        artifact={
            "valid": True,
            "selected_event": {
                "dataplane_confirmed": True,
                "restored_dataplane_claim_allowed": True,
                "traffic_delivery_claim_allowed": True,
                "customer_traffic_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "redacted": True,
            },
        },
    )

    assert "proof_gate_overpromotes_traffic_delivery" in failures


def test_operator_flow_verifier_cli_require_verified(tmp_path: Path) -> None:
    output = tmp_path / "operator-flow.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(ROOT),
            "--evidence-root",
            str(tmp_path / "events"),
            "--require-verified",
            "--output-json",
            str(output),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"] == "DATAPLANE_DELIVERY_OPERATOR_FLOW_VERIFIED"
    assert payload["ok"] is True
