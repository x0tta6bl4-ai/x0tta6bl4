from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
SMOKE_SCRIPT = ROOT / "scripts/ops/verify_measured_attestation_verifier_smoke.py"
VALIDATOR_SCRIPT = ROOT / "scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_attestation_files(root: Path) -> tuple[Path, Path, Path]:
    report = root / "report.bin"
    quote = root / "quote.bin"
    signature = root / "signature.bin"
    report.write_bytes(b"report-data-private")
    quote.write_bytes(b"quote-bytes-private")
    signature.write_bytes(b"signature-bytes-private")
    return report, quote, signature


def _smoke_args(module, root: Path):
    report, quote, signature = _write_attestation_files(root)
    return module.parse_args(
        [
            "--root",
            str(root),
            "--report-data-file",
            str(report),
            "--quote-file",
            str(quote),
            "--signature-file",
            str(signature),
            "--sgx-verifier-command",
            "/opt/x0t/sgx-verify --json",
            "--operator-or-lab-id",
            "private-operator",
            "--authorization-scope-id",
            "ticket-123",
            "--environment-bucket",
            "lab-sgx-node",
            "--hardware-profile-bucket",
            "sgx-dcap",
            "--policy-context",
            "private production verifier policy",
            "--allow-local-verifier-run",
        ]
    )


def _write_ready_candidate(tmp_path: Path, monkeypatch) -> Path:
    smoke = _load(SMOKE_SCRIPT, "measured_attestation_smoke_for_artifact_validator")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "valid": True,
                    "verifier_id": "dcap-local",
                    "policy_id": "sgx-prod-policy",
                    "production_verifier_claim_allowed": True,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("src.security.tee_attestation.subprocess.run", fake_run)
    smoke.run_smoke(_smoke_args(smoke, tmp_path))
    return tmp_path / "docs/verification/incoming/measured_attestation_verifier_smoke.json"


def test_validator_accepts_redacted_ready_smoke_artifact(tmp_path: Path, monkeypatch) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    validator = _load(VALIDATOR_SCRIPT, "measured_attestation_smoke_artifact_validator_ready")

    report = validator.build_report(tmp_path, candidate, require_ready=True)

    assert report["ready"] is True
    assert report["decision"] == validator.DECISION_READY
    assert report["artifact_schema"] == validator.ARTIFACT_SCHEMA
    assert report["artifact_ready"] is True
    assert report["artifact_freshness"]["fresh"] is True
    assert report["candidate_sha256"]
    assert report["failures"] == []


def test_validator_rejects_production_ready_claim(tmp_path: Path, monkeypatch) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["result_summary"]["production_ready"] = True
    payload["artifact_identity"]["artifact_sha256"] = validator_hash_zero_placeholder()
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    validator = _load(VALIDATOR_SCRIPT, "measured_attestation_smoke_artifact_validator_claims")

    report = validator.build_report(tmp_path, candidate, require_ready=True)

    assert report["ready"] is False
    assert report["decision"] == validator.DECISION_REJECTED
    assert "result_summary.production_ready must be false" in report["failures"]


def test_validator_rejects_goal_completion_claim(tmp_path: Path, monkeypatch) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["goal_can_be_marked_complete"] = True
    payload["artifact_identity"]["artifact_sha256"] = validator_hash_zero_placeholder()
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    validator = _load(
        VALIDATOR_SCRIPT,
        "measured_attestation_smoke_artifact_validator_goal_completion",
    )

    report = validator.build_report(tmp_path, candidate, require_ready=True)

    assert report["ready"] is False
    assert "goal_can_be_marked_complete must be false" in report["failures"]


def test_validator_rejects_claim_gate_overpromotion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["claim_gate"]["production_readiness_claim_allowed"] = True
    payload["claim_gate"]["customer_traffic_claim_allowed"] = True
    payload["artifact_identity"]["artifact_sha256"] = validator_hash_zero_placeholder()
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    validator = _load(
        VALIDATOR_SCRIPT,
        "measured_attestation_smoke_artifact_validator_claim_gate",
    )

    report = validator.build_report(tmp_path, candidate, require_ready=True)

    assert report["ready"] is False
    assert (
        "claim_gate.production_readiness_claim_allowed must be false"
        in report["failures"]
    )
    assert (
        "claim_gate.customer_traffic_claim_allowed must be false"
        in report["failures"]
    )


def test_validator_rejects_unredacted_attestation_material(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["input_redaction"]["raw_attestation_material_retained"] = True
    payload["artifact_identity"]["artifact_sha256"] = validator_hash_zero_placeholder()
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    validator = _load(VALIDATOR_SCRIPT, "measured_attestation_smoke_artifact_validator_redaction")

    report = validator.build_report(tmp_path, candidate)

    assert report["ready"] is False
    assert (
        "input_redaction.raw_attestation_material_retained must be false"
        in report["failures"]
    )


def test_validator_rejects_bad_artifact_hash(tmp_path: Path, monkeypatch) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    payload["artifact_identity"]["artifact_sha256"] = "0" * 64
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    validator = _load(VALIDATOR_SCRIPT, "measured_attestation_smoke_artifact_validator_hash")

    report = validator.build_report(tmp_path, candidate)

    assert report["ready"] is False
    assert any("artifact_identity.artifact_sha256 must match" in item for item in report["failures"])


def test_validator_rejects_stale_smoke_artifact(tmp_path: Path, monkeypatch) -> None:
    candidate = _write_ready_candidate(tmp_path, monkeypatch)
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    captured_at = datetime(2026, 5, 31, tzinfo=timezone.utc)
    payload["captured_at_utc"] = captured_at.isoformat().replace("+00:00", "Z")
    payload["artifact_identity"]["artifact_sha256"] = _artifact_content_sha256(payload)
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    validator = _load(VALIDATOR_SCRIPT, "measured_attestation_smoke_artifact_validator_freshness")

    report = validator.build_report(
        tmp_path,
        candidate,
        require_ready=True,
        max_age_hours=168,
        now_utc=captured_at + timedelta(hours=169),
    )

    assert report["ready"] is False
    assert report["artifact_freshness"]["fresh"] is False
    assert any("captured_at_utc is stale" in item for item in report["failures"])


def validator_hash_zero_placeholder() -> str:
    return "f" * 64


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _artifact_content_sha256(payload: dict) -> str:
    normalized = json.loads(_canonical_json(payload))
    normalized["artifact_identity"]["artifact_sha256"] = "0" * 64
    return hashlib.sha256(
        _canonical_json(normalized).encode("utf-8", errors="replace")
    ).hexdigest()
