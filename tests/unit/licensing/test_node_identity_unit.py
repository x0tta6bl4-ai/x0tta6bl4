import importlib
import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_import_smoke():
    try:
        mod = importlib.import_module("src.licensing.node_identity")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None


def _fingerprint(mod):
    return mod.DeviceFingerprint(
        cpu_id="cpu",
        mac_address="00:11:22:33:44:55",
        machine_id="machine",
        hostname="node",
        platform="Linux-x86_64",
    )


def test_node_activation_uses_injected_activation_client(monkeypatch, tmp_path):
    mod = importlib.import_module("src.licensing.node_identity")
    fp = _fingerprint(mod)
    authority = mod.LicenseAuthority(master_key=b"1" * 32)
    requests = []

    def activation_client(payload):
        requests.append(payload)
        cert = authority.sign_certificate(
            fingerprint_hash=payload["fingerprint_hash"],
            activation_token=payload["activation_token"],
            license_tier="pro",
        )
        return {"certificate": cert.to_dict()}

    monkeypatch.setattr(mod.HardwareFingerprinter, "generate", lambda: fp)
    monkeypatch.setattr(mod.NodeLicenseManager, "CERT_PATH", tmp_path / "license.cert")

    manager = mod.NodeLicenseManager(activation_client=activation_client)
    ok, message = manager.activate("X0T-PRO-token")

    assert ok is True
    assert "Tier: pro" in message
    assert requests[0]["activation_token"] == "X0T-PRO-token"
    assert requests[0]["fingerprint_hash"] == fp.to_hash()
    assert manager.CERT_PATH.exists()
    assert manager.verify()[0] is True
    status = manager.get_thinking_status()
    techniques = set(status["techniques"])
    assert status["profile"]["role"] == "security"
    assert "zero_trust_review" in techniques
    assert "reverse_planning" in techniques
    context = status["last_context"]
    assert context["applied"]["framing"]["problem"] == (
        "node_license_manager_operation"
    )
    constraints = context["applied"]["framing"]["constraints"]
    assert constraints["operation"] == "verify"
    assert constraints["fingerprint_match"] is True
    assert constraints["certificate_valid"] is True
    assert constraints["license_check_is_not_hardware_attestation"] is True
    assert constraints["license_check_is_not_external_identity_finality"] is True
    rendered_status = str(status)
    assert "X0T-PRO-token" not in rendered_status
    assert "00:11:22:33:44:55" not in rendered_status
    assert "machine" not in rendered_status


def test_node_activation_requires_license_server(monkeypatch, tmp_path):
    mod = importlib.import_module("src.licensing.node_identity")
    monkeypatch.setattr(mod.HardwareFingerprinter, "generate", lambda: _fingerprint(mod))
    monkeypatch.setattr(mod.NodeLicenseManager, "CERT_PATH", tmp_path / "license.cert")

    manager = mod.NodeLicenseManager(auth_server_url="")
    ok, message = manager.activate("X0T-BAS-token")

    assert ok is False
    assert "LICENSE_SERVER is required" in message
    assert manager.certificate is None
    assert not manager.CERT_PATH.exists()


def test_node_activation_rejects_certificate_for_other_machine(monkeypatch, tmp_path):
    mod = importlib.import_module("src.licensing.node_identity")
    fp = _fingerprint(mod)
    authority = mod.LicenseAuthority(master_key=b"2" * 32)

    def activation_client(_payload):
        cert = authority.sign_certificate(
            fingerprint_hash="not-this-machine",
            activation_token="X0T-BAS-token",
        )
        return {"certificate": cert.to_dict()}

    monkeypatch.setattr(mod.HardwareFingerprinter, "generate", lambda: fp)
    monkeypatch.setattr(mod.NodeLicenseManager, "CERT_PATH", tmp_path / "license.cert")

    manager = mod.NodeLicenseManager(activation_client=activation_client)
    ok, message = manager.activate("X0T-BAS-token")

    assert ok is False
    assert "different machine" in message
    assert manager.certificate is None


def test_node_activation_client_error_fails_closed(monkeypatch, tmp_path):
    mod = importlib.import_module("src.licensing.node_identity")
    monkeypatch.setattr(mod.HardwareFingerprinter, "generate", lambda: _fingerprint(mod))
    monkeypatch.setattr(mod.NodeLicenseManager, "CERT_PATH", tmp_path / "license.cert")

    def activation_client(_payload):
        raise RuntimeError("network down")

    manager = mod.NodeLicenseManager(activation_client=activation_client)
    ok, message = manager.activate("X0T-BAS-token")

    assert ok is False
    assert message == "License activation client failed."
    assert manager.certificate is None
    status = manager.get_thinking_status()
    constraints = status["last_context"]["applied"]["framing"]["constraints"]
    assert constraints["operation"] == "activate"
    assert constraints["error_type"] == "LicenseActivationError"
    assert constraints["raw_activation_token_redacted"] is True
    assert "X0T-BAS-token" not in str(status)
    assert "network down" not in str(status)
