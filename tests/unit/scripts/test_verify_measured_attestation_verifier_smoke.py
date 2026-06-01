from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/verify_measured_attestation_verifier_smoke.py"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
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


def _args(module, root: Path, *extra: str):
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
            *extra,
        ]
    )


def test_sgx_verifier_smoke_writes_redacted_ready_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load("verify_measured_attestation_verifier_smoke_ready")
    calls = []

    def fake_run(command, input, capture_output, text, timeout, check):
        calls.append(
            {
                "command": command,
                "input": input,
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
                "check": check,
            }
        )
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

    report = module.run_smoke(_args(module, tmp_path, "--allow-local-verifier-run"))
    output = tmp_path / "docs/verification/incoming/measured_attestation_verifier_smoke.json"
    output_text = output.read_text(encoding="utf-8")

    assert report["ready"] is True
    assert report["decision"] == module.READY_DECISION
    assert report["schema"] == module.SCHEMA
    assert report["verifier"]["backend"] == "sgx_command"
    assert report["verifier"]["production_verifier_claim_allowed"] is True
    assert report["verifier"]["provenance"]["raw_command_redacted"] is True
    assert report["verifier"]["provenance"]["raw_attestation_redacted"] is True
    assert report["measurements"]["production_trust_finality"] is False
    assert report["result_summary"]["production_ready"] is False
    assert report["claim_boundary"]["proof_claims"][
        "production_attestation_verifier_claim_allowed"
    ] is True
    assert report["artifact_identity"]["artifact_sha256"] == module.artifact_content_sha256(
        report
    )
    assert calls[0]["command"] == ["/opt/x0t/sgx-verify", "--json"]
    verifier_payload = json.loads(calls[0]["input"])
    assert verifier_payload["provider"] == "sgx"
    assert "report_data_b64" in verifier_payload
    assert "quote_b64" in verifier_payload
    assert "signature_b64" in verifier_payload
    assert "report-data-private" not in output_text
    assert "quote-bytes-private" not in output_text
    assert "signature-bytes-private" not in output_text
    assert "private-operator" not in output_text
    assert "ticket-123" not in output_text
    assert "/opt/x0t/sgx-verify" not in output_text


def test_sgx_verifier_smoke_blocks_without_production_verifier_claim(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load("verify_measured_attestation_verifier_smoke_blocked")

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"valid": True}),
            stderr="",
        )

    monkeypatch.setattr("src.security.tee_attestation.subprocess.run", fake_run)

    report = module.run_smoke(_args(module, tmp_path, "--allow-local-verifier-run"))

    assert report["ready"] is False
    assert report["decision"] == module.BLOCKED_DECISION
    assert report["measurements"]["attestation_verified"] is True
    assert report["measurements"]["production_verifier_claim_allowed"] is False
    assert report["claim_boundary"]["proof_claims"]["production_trust_finality"] is False


def test_sgx_verifier_smoke_requires_explicit_local_authorization(tmp_path: Path) -> None:
    module = _load("verify_measured_attestation_verifier_smoke_requires_auth")

    try:
        module.run_smoke(_args(module, tmp_path))
    except SystemExit as exc:
        assert "--allow-local-verifier-run is required" in str(exc)
    else:
        raise AssertionError("smoke should require explicit local verifier authorization")
