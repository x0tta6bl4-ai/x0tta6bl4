from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_traffic_delivery_operator_flow.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "verify_traffic_delivery_operator_flow",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_traffic_delivery_operator_flow_writes_redacted_event_and_gate_allows(
    tmp_path: Path,
) -> None:
    module = load_module()

    report = module.build_report(ROOT, evidence_root=tmp_path)

    assert report["schema"] == module.SCHEMA
    assert report["decision"] == module.DECISION_VERIFIED
    assert report["ok"] is True
    assert report["summary"]["local_loopback_probe"] is True
    assert report["summary"]["controlled_synthetic_traffic"] is True
    assert report["summary"]["collector_ready"] is True
    assert report["summary"]["event_written"] is True
    assert report["summary"]["proof_gate_allowed"] is True
    assert report["summary"]["proof_gate_artifact_valid"] is True
    assert report["summary"]["eventbus_evidence_recognized_by_proof_gate"] is True
    assert report["summary"]["raw_targets_redacted"] is True
    assert report["summary"]["payloads_redacted"] is True
    assert report["summary"]["mutates_project_runtime"] is False
    assert report["summary"]["writes_temp_eventbus"] is True
    assert report["summary"]["traffic_delivery_claimed"] is True
    assert report["summary"]["customer_traffic_claimed"] is False
    assert report["summary"]["external_reachability_claimed"] is False
    assert report["summary"]["production_readiness_claimed"] is False
    assert report["evidence"]["event_id"]
    assert report["evidence"]["matching_events"] == 1
    selected = report["evidence"]["selected_event"]
    assert selected["traffic_delivery_claim_allowed"] is True
    assert selected["traffic_delivery_confirmed"] is True
    assert selected["claim_scope"] == "traffic_delivery"
    assert selected["customer_traffic_claim_allowed"] is False
    assert selected["production_readiness_claim_allowed"] is False
    assert selected["redacted"] is True
    assert report["failures"] == []
    encoded = json.dumps(report, sort_keys=True)
    assert "x0tta6bl4 traffic delivery probe request" not in encoded
    assert "x0tta6bl4 traffic delivery probe response" not in encoded
    assert "127.0.0.1:" not in encoded


def test_traffic_delivery_operator_flow_rejects_overpromoted_artifact() -> None:
    module = load_module()

    failures = module._validate_flow(
        probe={
            "traffic_flow_confirmed": True,
            "raw_target_redacted": True,
        },
        collector_report={
            "decision": "TRAFFIC_DELIVERY_EVENTBUS_EVIDENCE_READY",
            "event_written": True,
            "ready_for_proof_gate": True,
        },
        proof_gate_report={
            "decision": "CROSS_PLANE_CLAIMS_ALLOWED",
            "allowed": True,
        },
        artifact={
            "valid": True,
            "matching_events": 1,
            "selected_event": {
                "traffic_delivery_claim_allowed": True,
                "traffic_delivery_confirmed": True,
                "claim_scope": "traffic_delivery",
                "customer_traffic_claim_allowed": True,
                "production_readiness_claim_allowed": False,
                "redacted": True,
            },
        },
    )

    assert "traffic_delivery_overpromotes_customer_traffic" in failures


def test_traffic_delivery_operator_flow_cli_require_verified(tmp_path: Path) -> None:
    output = tmp_path / "traffic-flow.json"

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
    assert payload["decision"] == "TRAFFIC_DELIVERY_OPERATOR_FLOW_VERIFIED"
    assert payload["ok"] is True
