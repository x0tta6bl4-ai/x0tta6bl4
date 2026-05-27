import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _false_boundary() -> dict:
    return {
        "stealth_verified": False,
        "whitelist_verified": False,
        "kernel_attach_verified": False,
        "production_ready": False,
    }


def _write_state(root: Path, verifier, pending: list[str]):
    supported = ["dpi_lab", "whitelist_lab", "security_review", "production_readiness"]
    proof_rows = [
        {
            "claim_id": claim_id,
            "status": "INVALID" if claim_id in pending else "VERIFIED",
            "errors": [f"{claim_id}: fixture gap"] if claim_id in pending else [],
        }
        for claim_id in supported
    ]
    _write_json(
        root / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json",
        {
            "schema": "x0tta6bl4.ghost_pulse.proof_gate.v1",
            "decision": "GHOST_PULSE_PROOF_INCOMPLETE" if pending else "GHOST_PULSE_ALL_CLAIMS_PROVEN",
            "proof_rows": proof_rows,
            "not_verified_yet": pending,
            "claim_boundary": _false_boundary(),
            "failures": ["fixture proof incomplete"] if pending else [],
        },
    )
    _write_json(
        root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
        {
            "schema": "x0tta6bl4.ghost_pulse.replacement_candidate_preflight.v1",
            "status": "PASS",
            "decision": "REPLACEMENT_CANDIDATES_NOT_READY" if pending else "REPLACEMENT_CANDIDATES_READY",
            "ready": [],
            "not_ready": pending,
            "replacement_required": pending,
            "failures": [],
            "claim_boundary": _false_boundary(),
        },
    )
    _write_json(
        root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
        {
            "schema": "x0tta6bl4.ghost_pulse.external_evidence_intake.v1",
            "status": "PASS",
            "decision": (
                "EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED"
                if pending
                else "EXTERNAL_EVIDENCE_INTAKE_READY_NOT_WRITTEN"
            ),
            "ready": [],
            "not_ready": pending,
            "replacement_required": pending,
            "failures": [],
            "claim_boundary": _false_boundary(),
        },
    )
    return {
        "proof_path": root / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json",
        "replacement_path": root / "docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json",
        "intake_path": root / "docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json",
    }


def test_incoming_gap_candidates_accept_current_fail_closed_state():
    verifier = _load_script(
        "verify_ghost_pulse_incoming_gap_candidates_current",
        "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    )

    report = verifier.build_report(ROOT)

    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_FAIL_CLOSED
    assert report["expected_gap_claims"] == [
        "dpi_lab",
        "whitelist_lab",
        "security_review",
        "production_readiness",
    ]
    assert [row["import_decision"] for row in report["rows"]] == ["REJECTED"] * 4
    assert all(row["payload_mode"] == verifier.GAP_MODE for row in report["rows"])
    assert report["claim_boundary"]["production_ready"] is False


def test_incoming_gap_candidates_verify_scaffolded_gap_candidates(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_incoming_gap_candidates_fixture",
        "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    )
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_incoming_gap_verifier_test",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    pending = ["dpi_lab", "whitelist_lab", "security_review", "production_readiness"]
    _write_state(tmp_path, verifier, pending)
    scaffold.write_incoming_gap_candidates(tmp_path, pending)

    report = verifier.build_report(tmp_path)

    assert report["status"] == "PASS"
    assert report["decision"] == verifier.DECISION_FAIL_CLOSED
    assert report["expected_gap_claims"] == pending
    assert report["unexpected_gap_claims"] == []
    assert report["checks"]["importer_rejects_gap_candidates"]["status"] == "PASS"
    first = report["rows"][0]
    assert first["candidate"] == "docs/verification/incoming/dpi_lab.json"
    assert first["payload_status"] == "INCOMPLETE"
    assert "dpi_lab: status must be VERIFIED" in first["import_failures"]
    assert "dpi_lab: mode must not be EXTERNAL_EVIDENCE_GAP_RECORD" in first["import_failures"]


def test_incoming_gap_candidates_fail_when_candidate_is_missing(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_incoming_gap_candidates_missing",
        "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    )
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_incoming_gap_verifier_missing",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    pending = ["dpi_lab"]
    _write_state(tmp_path, verifier, pending)
    scaffold.write_incoming_gap_candidates(tmp_path, pending)
    (tmp_path / "docs/verification/incoming/dpi_lab.json").unlink()

    report = verifier.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == verifier.DECISION_INVALID
    assert "dpi_lab: incoming gap candidate is missing: docs/verification/incoming/dpi_lab.json" in report["failures"]


def test_incoming_gap_candidates_detect_stale_gap_for_verified_claim(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_incoming_gap_candidates_stale_gap",
        "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    )
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_incoming_gap_verifier_stale",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    _write_state(tmp_path, verifier, [])
    scaffold.write_incoming_gap_candidates(tmp_path, ["dpi_lab"])

    report = verifier.build_report(tmp_path)

    assert report["status"] == "FAIL"
    assert report["decision"] == verifier.DECISION_INVALID
    assert report["expected_gap_claims"] == []
    assert report["unexpected_gap_claims"] == ["dpi_lab"]
    assert "incoming gap candidates are stale for verified/non-pending claims: dpi_lab" in report["failures"]


def test_incoming_gap_candidates_saved_report_detects_stale_candidate(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_incoming_gap_candidates_saved",
        "scripts/ops/verify_ghost_pulse_incoming_gap_candidates.py",
    )
    scaffold = _load_script(
        "scaffold_ghost_pulse_external_evidence_gaps_for_incoming_gap_verifier_saved",
        "scripts/ops/scaffold_ghost_pulse_external_evidence_gaps.py",
    )
    pending = ["dpi_lab"]
    _write_state(tmp_path, verifier, pending)
    scaffold.write_incoming_gap_candidates(tmp_path, pending)
    report = verifier.build_report(tmp_path)
    latest_json = tmp_path / "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.json"
    latest_md = tmp_path / "docs/verification/GHOST_PULSE_INCOMING_GAP_CANDIDATES_LATEST.md"
    verifier.write_report_outputs(tmp_path, report, latest_json, latest_md)
    assert verifier.verify_saved_report(latest_json, tmp_path) == []

    candidate = tmp_path / "docs/verification/incoming/dpi_lab.json"
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["missing_inputs"] = []
    candidate.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failures = verifier.verify_saved_report(latest_json, tmp_path)

    assert "incoming gap candidate stable fields do not match current proof/intake state" in failures
