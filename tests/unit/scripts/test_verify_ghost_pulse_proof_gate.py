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


def _current_proof() -> dict:
    return json.loads((ROOT / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json").read_text(encoding="utf-8"))


def _write_fixture_proof(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_proof_gate_verifier_accepts_current_latest():
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_current",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )

    failures = verifier.verify_proof(
        ROOT / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json",
        ROOT,
    )

    assert failures == []


def test_proof_gate_verifier_rejects_promoted_claim_boundary(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_boundary",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )
    payload = _current_proof()
    payload["claim_boundary"]["stealth_verified"] = True
    proof_path = _write_fixture_proof(tmp_path, payload)

    failures = verifier.verify_proof(
        proof_path,
        ROOT,
        check_current_state=False,
        check_artifacts=False,
    )

    assert "claim_boundary does not match proof-row-derived boundary" in failures


def test_proof_gate_verifier_derives_current_runtime_boundary():
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_runtime_boundary",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )

    boundary = verifier.expected_claim_boundary(
        [
            {"claim_id": "kernel_attach", "status": "VERIFIED"},
            {"claim_id": "packet_capture", "status": "VERIFIED"},
            {"claim_id": "baseline_timing_comparison", "status": "VERIFIED"},
            {"claim_id": "dpi_lab", "status": "INVALID"},
            {"claim_id": "whitelist_lab", "status": "INVALID"},
            {"claim_id": "production_readiness", "status": "INVALID"},
            {"claim_id": "current_runtime_attached", "status": "INVALID"},
        ]
    )

    assert boundary["kernel_attach_verified"] is True
    assert boundary["current_runtime_attached"] is False
    assert boundary["production_ready"] is False


def test_proof_gate_verifier_rejects_stale_not_verified_list(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_not_verified",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )
    payload = _current_proof()
    payload["not_verified_yet"] = []
    proof_path = _write_fixture_proof(tmp_path, payload)

    failures = verifier.verify_proof(
        proof_path,
        ROOT,
        check_current_state=False,
        check_artifacts=False,
    )

    assert "not_verified_yet does not match non-VERIFIED proof rows" in failures


def test_proof_gate_verifier_rejects_missing_replacement_candidates_block(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_replacement_missing",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )
    payload = _current_proof()
    payload.pop("replacement_candidates", None)
    proof_path = _write_fixture_proof(tmp_path, payload)

    failures = verifier.verify_proof(
        proof_path,
        ROOT,
        check_current_state=False,
        check_artifacts=False,
    )

    assert "replacement_candidates must be an object" in failures


def test_proof_gate_verifier_rejects_failed_replacement_candidates_preflight(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_replacement_failed",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )
    payload = _current_proof()
    payload["replacement_candidates"]["status"] = "FAIL"
    payload["replacement_candidates"]["failures"] = ["saved preflight report is stale"]
    proof_path = _write_fixture_proof(tmp_path, payload)

    failures = verifier.verify_proof(
        proof_path,
        ROOT,
        check_current_state=False,
        check_artifacts=False,
    )

    assert "replacement_candidates verifier status must be PASS" in failures


def test_proof_gate_verifier_rejects_replacement_candidates_sha_mismatch(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_replacement_sha",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )
    payload = _current_proof()
    payload["replacement_candidates"]["sha256"] = "0" * 64
    proof_path = _write_fixture_proof(tmp_path, payload)

    failures = verifier.verify_proof(
        proof_path,
        ROOT,
        check_current_state=False,
        check_artifacts=False,
    )

    assert "replacement_candidates.sha256 does not match report artifact" in failures


def test_proof_gate_verifier_rejects_bundle_mismatch(tmp_path):
    verifier = _load_script(
        "verify_ghost_pulse_proof_gate_bundle",
        "scripts/ops/verify_ghost_pulse_proof_gate.py",
    )
    payload = _current_proof()
    latest = tmp_path / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json"
    latest_md = tmp_path / "docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.md"
    bundle_json = tmp_path / "docs/verification/ghost-pulse-proof-gate-fixture/proof.json"
    bundle_md = tmp_path / "docs/verification/ghost-pulse-proof-gate-fixture/summary.md"
    payload["artifacts"] = {
        "proof_latest_json": verifier.display_path(tmp_path, latest),
        "proof_latest_md": verifier.display_path(tmp_path, latest_md),
        "proof_bundle_json": verifier.display_path(tmp_path, bundle_json),
        "proof_bundle_md": verifier.display_path(tmp_path, bundle_md),
    }
    latest.parent.mkdir(parents=True, exist_ok=True)
    bundle_json.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    bundle_json.write_text("{}", encoding="utf-8")
    latest_md.write_text("latest\n", encoding="utf-8")
    bundle_md.write_text("bundle\n", encoding="utf-8")

    failures = verifier.verify_proof(
        latest,
        tmp_path,
        check_current_state=False,
        check_artifacts=True,
    )

    assert "proof latest JSON does not match bundle JSON" in failures
    assert "proof latest markdown does not match bundle markdown" in failures
