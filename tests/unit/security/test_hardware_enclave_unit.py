"""Unit tests for src.security.hardware_enclave."""

from __future__ import annotations

import hashlib
from io import StringIO

from src.security.hardware_enclave import AttestationService, HardwareSecurityModule


def test_detect_prefers_tpm_when_device_exists(monkeypatch):
    monkeypatch.setattr("src.security.hardware_enclave.os.path.exists", lambda path: path == "/dev/tpm0")
    hsm = HardwareSecurityModule()
    assert hsm._detected_module == "tpm2.0"


def test_get_hardware_identity_from_tpm_mode():
    hsm = HardwareSecurityModule()
    hsm._detected_module = "tpm2.0"
    expected = hashlib.sha256(b"tpm-endorsement-key-sha256").hexdigest()
    assert hsm.get_hardware_identity() == expected


def test_get_hardware_identity_reads_system_uuid(monkeypatch):
    hsm = HardwareSecurityModule()
    hsm._detected_module = "mock"
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: StringIO("uuid-1234\n"))
    assert hsm.get_hardware_identity() == "uuid-1234"


def test_get_hardware_identity_falls_back_when_uuid_unavailable(monkeypatch):
    hsm = HardwareSecurityModule()
    hsm._detected_module = "mock"

    def _raise(*_args, **_kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr("builtins.open", _raise)
    assert hsm.get_hardware_identity() == "mock-hardware-id-0000-ffff"


def test_sign_with_hardware_uses_blake2b_fallback(monkeypatch):
    hsm = HardwareSecurityModule()
    monkeypatch.delattr("src.security.hardware_enclave.hashlib.blake3", raising=False)

    payload = b"mesh-payload"
    expected = hashlib.blake2b(hashlib.sha256(payload).digest() + b"hw-secret").digest()
    assert hsm.sign_with_hardware(payload) == expected


def test_verify_hardware_attestation_returns_true():
    hsm = HardwareSecurityModule()
    assert hsm.verify_hardware_attestation(b"quote", b"nonce") is True


def test_attestation_service_security_level():
    assert AttestationService.validate_node(
        {"hardware_id": "node-1", "enclave_enabled": True}
    ) == {
        "is_trusted": True,
        "security_level": "HARDWARE_ROOTED",
        "hardware_id": "node-1",
    }

    assert AttestationService.validate_node(
        {"hardware_id": "node-2", "enclave_enabled": False}
    ) == {
        "is_trusted": True,
        "security_level": "SOFTWARE_ONLY",
        "hardware_id": "node-2",
    }
