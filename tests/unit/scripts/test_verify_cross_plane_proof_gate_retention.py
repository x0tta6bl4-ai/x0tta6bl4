from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_cross_plane_proof_gate_retention.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "cross_plane_proof_gate_retention_validator",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _write_retained_artifact(root: Path, *, timestamp_utc: str | None = None) -> Path:
    map_path = _write(
        root,
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        json.dumps({"schema": "test-map", "current_gaps": [], "next_actions": []}),
    )
    audit_path = _write(
        root,
        "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
        "# test audit\n",
    )
    output = root / ".tmp/validation-shards/cross-plane-proof-gate-current.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    sources = [
        {
            "role": "current_cross_plane_evidence_map",
            "path": "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
            "sha256": _sha256(map_path),
            "sha256_present": True,
        },
        {
            "role": "current_active_goal_gap_audit",
            "path": "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
            "sha256": _sha256(audit_path),
            "sha256_present": True,
        },
    ]
    payload = {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "timestamp_utc": timestamp_utc or _utc_now(),
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": False,
        "context": {
            "source_artifact_hashes_present": True,
            "source_artifacts": sources,
            "map_sha256": sources[0]["sha256"],
            "audit_sha256": sources[1]["sha256"],
        },
        "retention_manifest": {
            "schema": "x0tta6bl4.cross_plane_proof_gate.retention.v1",
            "retention_required": True,
            "canonical_artifact_path": ".tmp/validation-shards/cross-plane-proof-gate-current.json",
            "retained_artifact_path": ".tmp/validation-shards/cross-plane-proof-gate-current.json",
            "writer_command_shape": (
                "python3 scripts/ops/run_cross_plane_proof_gate.py --json "
                "--require-allowed --output-json "
                ".tmp/validation-shards/cross-plane-proof-gate-current.json"
            ),
            "source_artifact_hashes_present": True,
            "source_artifacts": sources,
            "mutates_runtime": False,
            "collects_live_evidence": False,
            "claim_boundary": "not live traffic proof",
        },
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output


def test_retention_validator_accepts_current_retained_artifact(tmp_path: Path) -> None:
    validator = _load_validator()
    artifact = _write_retained_artifact(tmp_path)

    report = validator.build_report(tmp_path, artifact)

    assert report["valid"] is True
    assert report["decision"] == validator.DECISION_VALID
    assert report["source_artifact_hashes_verified"] is True
    assert report["source_artifact_count"] == 2
    assert report["failures"] == []


def test_retention_validator_rejects_missing_artifact(tmp_path: Path) -> None:
    validator = _load_validator()

    report = validator.build_report(tmp_path)

    assert report["valid"] is False
    assert "retained_artifact_missing" in report["failures"]


def test_retention_validator_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    validator = _load_validator()
    artifact = _write_retained_artifact(tmp_path)
    map_path = tmp_path / "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    map_path.write_text('{"schema":"test-map","changed":true}', encoding="utf-8")

    report = validator.build_report(tmp_path, artifact)

    assert report["valid"] is False
    assert (
        "current_cross_plane_evidence_map:source_artifact_sha256_mismatch"
        in report["failures"]
    )


def test_retention_validator_rejects_stale_artifact(tmp_path: Path) -> None:
    validator = _load_validator()
    stale_timestamp = (
        datetime.now(timezone.utc) - timedelta(hours=169)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    artifact = _write_retained_artifact(tmp_path, timestamp_utc=stale_timestamp)

    report = validator.build_report(tmp_path, artifact)

    assert report["valid"] is False
    assert "retained_proof_gate_artifact_stale" in report["failures"]


def test_retention_validator_rejects_runtime_or_live_evidence_claims(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    artifact = _write_retained_artifact(tmp_path)
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["retention_manifest"]["mutates_runtime"] = True
    payload["retention_manifest"]["collects_live_evidence"] = True
    payload["retention_manifest"]["retained_artifact_path"] = "other.json"
    artifact.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = validator.build_report(tmp_path, artifact)

    assert report["valid"] is False
    assert "retention_mutates_runtime_not_false" in report["failures"]
    assert "retention_collects_live_evidence_not_false" in report["failures"]
    assert "retained_artifact_path_mismatch" in report["failures"]


def test_retention_validator_cli_require_valid(tmp_path: Path) -> None:
    artifact = _write_retained_artifact(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--artifact",
            str(artifact.relative_to(tmp_path)),
            "--require-valid",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["decision"] == "CROSS_PLANE_PROOF_GATE_RETENTION_VALID"
