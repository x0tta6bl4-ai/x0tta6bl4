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

    def fake_run(command, **kwargs):
        calls.append(
            {
                "command": command,
                **kwargs,
            }
        )
        return _Result()

    monkeypatch.setattr("src.core.security.subprocess_validator.subprocess.run", fake_run)
    monkeypatch.setattr(
        "src.core.security.subprocess_validator.shutil.which",
        lambda cmd: "/usr/bin/sgx-verify" if cmd == "sgx-verify" else None
    )
    validator = TEEValidator(sgx_verifier_command=["sgx-verify", "--json"])

    assert validator.verify_report(_sgx_attestation()) is True
    payload = json.loads(calls[0]["input"])
    assert calls[0]["command"] == ["/usr/bin/sgx-verify", "--json"]
    assert payload["provider"] == "sgx"
    assert base64.b64decode(payload["report_data_b64"]) == b"report-data"
    assert base64.b64decode(payload["quote_b64"]) == b"quote-bytes"
    assert base64.b64decode(payload["signature_b64"]) == b"signature-bytes"


def test_sgx_command_backend_rejects_nonzero_exit(monkeypatch):
    class _Result:
        returncode = 1
        stdout = ""
        stderr = "rejected"

    monkeypatch.setattr(
        "src.core.security.subprocess_validator.subprocess.run",
        lambda *args, **kwargs: _Result(),
    )
    monkeypatch.setattr(
        "src.core.security.subprocess_validator.shutil.which",
        lambda cmd: "/usr/bin/sgx-verify" if cmd == "sgx-verify" else None
    )

    assert (
        TEEValidator(sgx_verifier_command=["sgx-verify"]).verify_report(
            _sgx_attestation()
        )
        is False
    )


def test_sev_and_nitro_verification(monkeypatch):
    monkeypatch.setenv("_X0TTA_TEST_MODE_", "true")
    validator = TEEValidator()

    # AMD SEV
    sev_att = TEEAttestation(provider="sev", report_data=b"report", quote=b"SEV_MOCK_TRUSTED")
    res_sev = validator.verify_report_with_context(sev_att)
    assert res_sev.verified is True
    assert res_sev.provider == "sev"
    assert res_sev.verifier_backend == "x0tta6bl4_sev_verifier_v1"

    # AWS Nitro
    nitro_att = TEEAttestation(provider="nitro", report_data=b"report", quote=b"NITRO_MOCK_TRUSTED")
    res_nitro = validator.verify_report_with_context(nitro_att)
    assert res_nitro.verified is True
    assert res_nitro.provider == "nitro"
    assert res_nitro.verifier_backend == "x0tta6bl4_nitro_verifier_v1"
