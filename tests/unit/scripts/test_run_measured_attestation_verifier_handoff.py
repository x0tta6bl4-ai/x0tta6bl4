from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_measured_attestation_verifier_handoff.py"


def _load_handoff():
    spec = importlib.util.spec_from_file_location(
        "run_measured_attestation_verifier_handoff",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_entrypoints(root: Path) -> None:
    for rel in (
        "scripts/ops/verify_measured_attestation_verifier_smoke.py",
        "scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py",
        "scripts/ops/run_cross_plane_proof_gate.py",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# test entrypoint\n", encoding="utf-8")


def _write_attestation_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    report = root / "private-report.bin"
    quote = root / "private-quote.bin"
    signature = root / "private-signature.bin"
    verifier = root / "sgx-verify"
    report.write_bytes(b"report-data-private")
    quote.write_bytes(b"quote-private")
    signature.write_bytes(b"signature-private")
    verifier.write_text("#!/bin/sh\n", encoding="utf-8")
    verifier.chmod(0o755)
    return report, quote, signature, verifier


def test_handoff_ready_with_redacted_local_inputs(tmp_path: Path) -> None:
    handoff = _load_handoff()
    _write_entrypoints(tmp_path)
    report_file, quote_file, signature_file, verifier = _write_attestation_inputs(tmp_path)

    report = handoff.build_report(
        tmp_path,
        report_data_file=str(report_file),
        quote_file=str(quote_file),
        signature_file=str(signature_file),
        sgx_verifier_command=f"{verifier} --json",
        operator_or_lab_id="private-operator",
        authorization_scope_id="ticket-123",
        environment_bucket="lab-sgx-node",
        hardware_profile_bucket="sgx-dcap",
        policy_context="private policy context",
    )
    rendered = json.dumps(report)

    assert report["decision"] == handoff.DECISION_READY
    assert report["ready_for_operator_run"] is True
    assert report["runs_verifier"] is False
    assert report["writes_artifacts"] is False
    assert report["raw_inputs_redacted"] is True
    assert report["inputs"]["report_data"]["non_empty"] is True
    assert report["inputs"]["provider"] == {
        "value": "sgx",
        "supported": True,
        "raw_value_redacted": True,
    }
    assert report["inputs"]["verifier_command"]["argv0_found"] is True
    assert report["inputs"]["sgx_verifier_command"]["argv0_found"] is True
    assert report["inputs"]["operator_or_lab_hash"] == handoff.sha256_text(
        "private-operator"
    )
    assert report["claim_flags"]["production_readiness_claimed"] is False
    assert report["claim_flags"]["production_trust_finality_claimed"] is False
    assert all(check["entrypoint_exists"] for check in report["operator_command_checks"])
    assert "private-report.bin" not in rendered
    assert "private-operator" not in rendered
    assert "ticket-123" not in rendered
    assert str(verifier) not in rendered


def test_handoff_ready_for_sev_with_generic_verifier_command(tmp_path: Path) -> None:
    handoff = _load_handoff()
    _write_entrypoints(tmp_path)
    report_file, quote_file, signature_file, verifier = _write_attestation_inputs(tmp_path)

    report = handoff.build_report(
        tmp_path,
        provider="sev",
        report_data_file=str(report_file),
        quote_file=str(quote_file),
        signature_file=str(signature_file),
        verifier_command=f"{verifier} --json",
        operator_or_lab_id="private-operator",
        authorization_scope_id="ticket-123",
        environment_bucket="lab-sev-node",
        hardware_profile_bucket="sev-snp",
        policy_context="private policy context",
    )

    assert report["decision"] == handoff.DECISION_READY
    assert report["ready_for_operator_run"] is True
    assert report["inputs"]["provider"]["value"] == "sev"
    assert report["inputs"]["provider"]["supported"] is True
    assert report["inputs"]["verifier_command"]["argv0_found"] is True
    assert "X0T_MEASURED_ATTESTATION_VERIFIER_COMMAND" in report["operator_env_vars"]


def test_handoff_blocks_missing_inputs_without_running_verifier(tmp_path: Path) -> None:
    handoff = _load_handoff()
    _write_entrypoints(tmp_path)

    report = handoff.build_report(tmp_path)

    assert report["ready_for_operator_run"] is False
    assert "report_data_file_required" in report["blockers"]
    assert "quote_file_required" in report["blockers"]
    assert "signature_file_required" in report["blockers"]
    assert "sgx_verifier_command_required" in report["blockers"]
    assert report["runs_verifier"] is False
    assert report["writes_artifacts"] is False


def test_handoff_blocks_symlink_attestation_input(tmp_path: Path) -> None:
    handoff = _load_handoff()
    _write_entrypoints(tmp_path)
    target = tmp_path / "target.bin"
    target.write_bytes(b"target")
    symlink = tmp_path / "report-link.bin"
    symlink.symlink_to(target)
    quote_file, signature_file, verifier = _write_attestation_inputs(tmp_path)[1:]

    report = handoff.build_report(
        tmp_path,
        report_data_file=str(symlink),
        quote_file=str(quote_file),
        signature_file=str(signature_file),
        sgx_verifier_command=str(verifier),
        operator_or_lab_id="private-operator",
        authorization_scope_id="ticket-123",
        environment_bucket="lab-sgx-node",
        hardware_profile_bucket="sgx-dcap",
        policy_context="private policy context",
    )

    assert report["ready_for_operator_run"] is False
    assert "report_data_file_must_not_be_symlink" in report["blockers"]


def test_handoff_cli_require_ready_fails_when_inputs_are_missing() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(ROOT),
            "--require-ready",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["decision"] == (
        "MEASURED_ATTESTATION_VERIFIER_HANDOFF_BLOCKED_ON_OPERATOR"
    )
    assert "report_data_file_required" in payload["blockers"]


"""
test_handoff_redacts_raw_evidence
"""
