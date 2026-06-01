from __future__ import annotations

import base64
import json

from src.security.tee_attestation import TEEAttestation, TEEValidator


def _sgx_attestation() -> TEEAttestation:
    return TEEAttestation(
        provider="sgx",
        report_data=b"report-data",
        quote=b"quote-bytes",
        signature=b"signature-bytes",
    )


def test_mock_provider_requires_explicit_allow_mock():
    attestation = TEEAttestation(provider="mock", report_data=b"TRUSTED_X0T")

    assert TEEValidator().verify_report(attestation) is False
    assert TEEValidator(allow_mock=True).verify_report(attestation) is True


def test_sgx_rejects_without_backend():
    assert TEEValidator().verify_report(_sgx_attestation()) is False


def test_sgx_rejects_missing_quote_or_signature():
    validator = TEEValidator(sgx_verifier=lambda _att: True)

    assert (
        validator.verify_report(
            TEEAttestation(provider="sgx", report_data=b"report", quote=b"quote")
        )
        is False
    )


def test_sgx_uses_callable_backend():
    seen = []

    def verifier(attestation: TEEAttestation) -> bool:
        seen.append(attestation)
        return attestation.quote == b"quote-bytes"

    attestation = _sgx_attestation()

    assert TEEValidator(sgx_verifier=verifier).verify_report(attestation) is True
    assert seen == [attestation]


def test_sgx_command_backend_receives_base64_payload(monkeypatch):
    calls = []

    class _Result:
        returncode = 0
        stdout = '{"valid": true}'
        stderr = ""

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
        return _Result()

    monkeypatch.setattr("src.security.tee_attestation.subprocess.run", fake_run)
    validator = TEEValidator(sgx_verifier_command=["sgx-verify", "--json"])

    assert validator.verify_report(_sgx_attestation()) is True
    payload = json.loads(calls[0]["input"])
    assert calls[0]["command"] == ["sgx-verify", "--json"]
    assert payload["provider"] == "sgx"
    assert base64.b64decode(payload["report_data_b64"]) == b"report-data"
    assert base64.b64decode(payload["quote_b64"]) == b"quote-bytes"
    assert base64.b64decode(payload["signature_b64"]) == b"signature-bytes"


def test_sgx_command_backend_context_records_redacted_provenance(monkeypatch):
    class _Result:
        returncode = 0
        stdout = json.dumps(
            {
                "valid": True,
                "verifier_id": "dcap-local",
                "policy_id": "sgx-prod-policy",
                "production_verifier_claim_allowed": True,
            }
        )
        stderr = ""

    monkeypatch.setattr(
        "src.security.tee_attestation.subprocess.run",
        lambda *args, **kwargs: _Result(),
    )
    validator = TEEValidator(sgx_verifier_command=["/opt/x0t/sgx-verify", "--json"])

    result = validator.verify_report_with_context(_sgx_attestation())

    assert result.verified is True
    assert result.provider == "sgx"
    assert result.verifier_backend == "sgx_command"
    assert result.production_verifier_claim_allowed is True
    assert result.verifier_provenance["backend_kind"] == "local_command"
    assert result.verifier_provenance["executable_name"] == "sgx-verify"
    assert result.verifier_provenance["raw_command_redacted"] is True
    assert result.verifier_provenance["verifier_id"] == "dcap-local"
    assert result.verifier_provenance["policy_id"] == "sgx-prod-policy"
    assert "command_sha256_prefix" in result.verifier_provenance
    assert "/opt/x0t/sgx-verify" not in json.dumps(result.verifier_provenance)


def test_mock_context_never_allows_production_verifier_claim():
    result = TEEValidator(allow_mock=True).verify_report_with_context(
        TEEAttestation(provider="mock", report_data=b"TRUSTED_X0T")
    )

    assert result.verified is True
    assert result.verifier_backend == "mock_local_allowlist"
    assert result.production_verifier_claim_allowed is False
    assert result.verifier_provenance["raw_attestation_redacted"] is True


def test_sgx_command_backend_rejects_nonzero_exit(monkeypatch):
    class _Result:
        returncode = 1
        stdout = ""
        stderr = "rejected"

    monkeypatch.setattr(
        "src.security.tee_attestation.subprocess.run",
        lambda *args, **kwargs: _Result(),
    )

    assert (
        TEEValidator(sgx_verifier_command=["sgx-verify"]).verify_report(
            _sgx_attestation()
        )
        is False
    )
