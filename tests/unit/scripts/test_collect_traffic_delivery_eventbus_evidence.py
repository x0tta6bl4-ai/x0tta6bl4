from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scripts.ops.run_cross_plane_proof_gate import (
    build_report,
    dataplane_delivery_artifact_evidence,
)


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_traffic_delivery_eventbus_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "collect_traffic_delivery_eventbus_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_map(root: Path, *, traffic_flags: bool = True) -> None:
    path = root / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    (root / "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md").write_text(
        "# audit\n",
        encoding="utf-8",
    )
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.cross_plane_evidence_map.test.v1",
                "status": "working_map_not_production_completion_proof",
                "planes": {
                    "data_plane": {},
                    "control_plane": {},
                    "trust_plane": {},
                    "evidence_plane": {},
                    "economy_plane": {},
                },
                "cross_plane_links": [
                    {
                        "id": "traffic-delivery-link",
                        "from_planes": ["data_plane"],
                        "to_planes": ["evidence_plane"],
                        "proof_flags": {
                            "traffic_delivery_confirmed": traffic_flags,
                            "traffic_delivery_claim_allowed": traffic_flags,
                        },
                    }
                ],
                "current_gaps": [],
                "next_actions": [],
            }
        ),
        encoding="utf-8",
    )


def _write_proof(
    tmp_path: Path,
    *,
    traffic_flow_confirmed: bool = True,
    request_observed: bool = True,
    response_validated: bool = True,
    status: str = "VERIFIED",
) -> Path:
    path = tmp_path / "traffic_delivery.json"
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.traffic_delivery.local_evidence_input.v1",
                "status": status,
                "observed_evidence": {
                    "environment": "lab",
                    "traffic_class": "synthetic_mesh_flow",
                    "traffic_flow_confirmed": traffic_flow_confirmed,
                    "request_observed": request_observed,
                    "response_validated": response_validated,
                    "traffic_payloads_redacted": True,
                },
                "source_artifacts": [
                    {
                        "role": "redacted_traffic_delivery_scenario_probe_report",
                        "sha256": "c" * 64,
                        "redacted": True,
                    }
                ],
                "raw_identifiers_redacted": True,
                "raw_values_redacted": True,
                "payloads_redacted": True,
                "authorization_scope_redacted": True,
                "claim_boundary": (
                    "Bounded redacted traffic-delivery scenario evidence only; "
                    "not customer traffic or production readiness proof."
                ),
            }
        ),
        encoding="utf-8",
    )
    return path


def test_collect_blocks_without_explicit_redacted_proof_authorization(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path)
    args = collector.parse_args(["--root", str(tmp_path), "--proof-json", str(proof)])

    report = collector.collect(args)

    assert report["decision"] == "BLOCKED_PROOF_INTAKE_NOT_AUTHORIZED"
    assert report["event_written"] is False
    assert report["ready_for_proof_gate"] is False
    assert "allow_redacted_local_proof_intake_required" in report["blockers"]


def test_collect_writes_event_recognized_by_cross_plane_proof_gate(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    _write_map(tmp_path, traffic_flags=True)
    proof = _write_proof(tmp_path)
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--proof-json",
            str(proof),
            "--allow-redacted-local-proof-intake",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "TRAFFIC_DELIVERY_EVENTBUS_EVIDENCE_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is True

    artifact = dataplane_delivery_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["matching_events"] == 1
    assert artifact["selected_event"]["event_id"] == report["event_id"]
    assert artifact["selected_event"]["source_agent"] == "traffic-delivery-probe"
    assert artifact["selected_event"]["traffic_delivery_claim_allowed"] is True
    assert artifact["selected_event"]["customer_traffic_claim_allowed"] is False
    assert artifact["selected_event"]["production_readiness_claim_allowed"] is False

    proof_gate = build_report(tmp_path, claims=("traffic_delivery",))
    assert proof_gate["decision"] == "CROSS_PLANE_CLAIMS_ALLOWED"
    assert proof_gate["allowed_claim_ids"] == ["traffic_delivery"]


def test_collect_partial_proof_writes_non_promoting_event(tmp_path: Path) -> None:
    collector = _load_script()
    _write_map(tmp_path, traffic_flags=True)
    proof = _write_proof(tmp_path, response_validated=False)
    args = collector.parse_args(
        [
            "--root",
            str(tmp_path),
            "--proof-json",
            str(proof),
            "--allow-redacted-local-proof-intake",
            "--write-event",
        ]
    )

    report = collector.collect(args)

    assert report["decision"] == "TRAFFIC_DELIVERY_PROOF_NOT_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is False
    assert "traffic_delivery_input_response_not_validated" in report["blockers"]

    artifact = dataplane_delivery_artifact_evidence(tmp_path)
    assert artifact["valid"] is False
    assert "verified_dataplane_delivery_event_not_found" in artifact["blockers"]
    assert "dataplane_probe_not_confirmed" in artifact["candidate_blockers"]


def test_collect_exposes_template_without_writing_event(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(
        ["--root", str(tmp_path), "--print-template", "--json"]
    )

    report = collector.collect(args)

    assert report["decision"] == "TRAFFIC_DELIVERY_TEMPLATE"
    assert report["event_written"] is False
    assert report["template"]["raw_identifiers_redacted"] is True
    assert report["template"]["payloads_redacted"] is True
    assert report["template"]["observed_evidence"]["traffic_flow_confirmed"] is False
