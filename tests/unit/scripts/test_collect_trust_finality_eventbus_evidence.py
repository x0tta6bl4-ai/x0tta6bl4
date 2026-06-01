from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scripts.ops.run_cross_plane_proof_gate import trust_finality_artifact_evidence


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_trust_finality_eventbus_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "collect_trust_finality_eventbus_evidence",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_proof(
    tmp_path: Path,
    *,
    live_spiffe_svid_confirmed: bool = True,
    status: str = "VERIFIED",
    source_artifact_role: str = "redacted_local_spiffe_svid_probe_report",
) -> Path:
    path = tmp_path / "trust_finality.json"
    path.write_text(
        json.dumps(
            {
                "schema": "x0tta6bl4.trust_finality.local_evidence_input.v1",
                "status": status,
                "observed_evidence": {
                    "live_spiffe_svid_confirmed": live_spiffe_svid_confirmed,
                    "did_ownership_confirmed": False,
                    "wallet_control_confirmed": False,
                    "chain_identity_finality_confirmed": False,
                },
                "source_artifacts": [
                    {
                        "role": source_artifact_role,
                        "sha256": "a" * 64,
                        "redacted": True,
                    }
                ],
                "raw_identity_values_redacted": True,
                "payloads_redacted": True,
                "claim_boundary": (
                    "Redacted local trust-finality evidence only; not dataplane, "
                    "customer traffic, settlement, or production readiness proof."
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

    assert report["decision"] == "TRUST_FINALITY_EVENTBUS_EVIDENCE_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is True

    artifact = trust_finality_artifact_evidence(tmp_path)
    assert artifact["valid"] is True
    assert artifact["matching_events"] == 1
    assert artifact["selected_event"]["event_id"] == report["event_id"]
    assert artifact["selected_event"]["redacted"] is True


def test_collect_unconfirmed_proof_writes_non_promoting_event(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path, live_spiffe_svid_confirmed=False)
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

    assert report["decision"] == "TRUST_FINALITY_PROOF_NOT_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is False
    assert "trust_finality_input_has_no_confirmed_identity_fact" in report["blockers"]

    artifact = trust_finality_artifact_evidence(tmp_path)
    assert artifact["valid"] is False
    assert "verified_trust_finality_event_not_found" in artifact["blockers"]
    assert "trust_finality_not_confirmed" in artifact["candidate_blockers"]


def test_collect_blocks_verified_proof_without_required_trust_probe_artifact_role(
    tmp_path: Path,
) -> None:
    collector = _load_script()
    proof = _write_proof(tmp_path, source_artifact_role="generic_redacted_identity_log")
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

    assert report["decision"] == "TRUST_FINALITY_PROOF_NOT_READY"
    assert report["event_written"] is True
    assert report["ready_for_proof_gate"] is False
    assert "trust_finality_input_required_source_artifact_missing" in report[
        "blockers"
    ]

    artifact = trust_finality_artifact_evidence(tmp_path)
    assert artifact["valid"] is False
    assert "verified_trust_finality_event_not_found" in artifact["blockers"]
    assert "trust_finality_not_confirmed" in artifact["candidate_blockers"]


def test_collect_exposes_template_without_writing_event(tmp_path: Path) -> None:
    collector = _load_script()
    args = collector.parse_args(
        ["--root", str(tmp_path), "--print-template", "--json"]
    )

    report = collector.collect(args)

    assert report["decision"] == "TRUST_FINALITY_TEMPLATE"
    assert report["event_written"] is False
    assert report["template"]["raw_identity_values_redacted"] is True
    assert report["template"]["payloads_redacted"] is True
