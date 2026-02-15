from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.security import pqc_mtls as mod


class _DummyKEM:
    def __init__(self):
        self.counter = 0

    def generate_keypair(self, key_id: str, validity_days: int):
        self.counter += 1
        return SimpleNamespace(
            key_id=f"{key_id}_{self.counter}",
            secret_key=b"kem-secret",
            public_key=b"kem-public",
            expires_at=datetime.utcnow() + timedelta(days=validity_days),
        )


class _DummyDSA:
    def __init__(self):
        self.counter = 0

    def generate_keypair(self, key_id: str, validity_days: int):
        self.counter += 1
        return SimpleNamespace(
            key_id=f"{key_id}_{self.counter}",
            secret_key=b"dsa-secret",
            public_key=b"dsa-public",
            expires_at=datetime.utcnow() + timedelta(days=validity_days),
        )

    async def sign(self, data: bytes, secret_key: bytes, key_id: str):
        return SimpleNamespace(
            algorithm="ML-DSA-65",
            signature_bytes=b"sig:" + data[:8],
            signer_key_id=key_id,
        )

    async def verify(self, data: bytes, signature_bytes: bytes, public_key: bytes):
        return signature_bytes.startswith(b"sig:")


class _DummyHybrid:
    def __init__(self, enabled=True):
        self.enable_pqc = enabled
        self.kem = _DummyKEM()
        self.dsa = _DummyDSA()

    async def setup_secure_channel(self):
        return {"status": "success", "shared_secret_len": 32}


@pytest.mark.asyncio
async def test_pqc_mtls_disabled_mode():
    controller = mod.PQCmTLSController(enable_hybrid=False)
    assert controller.enabled is False

    key_init = await controller.initialize_pqc_keys()
    assert key_init["status"] == "disabled"

    channel = await controller.establish_pqc_channel()
    assert channel["status"] == "disabled"


@pytest.mark.asyncio
async def test_pqc_mtls_initialize_and_channel_with_mock_hybrid(monkeypatch):
    monkeypatch.setattr(mod, "get_pqc_hybrid", lambda: _DummyHybrid(enabled=True))
    controller = mod.PQCmTLSController(enable_hybrid=True)
    assert controller.enabled is True

    key_init = await controller.initialize_pqc_keys(validity_days=7)
    assert key_init["status"] == "success"
    assert "kem_key_id" in key_init
    assert "dsa_key_id" in key_init

    channel = await controller.establish_pqc_channel()
    assert channel["status"] == "success"
    assert channel["shared_secret_bits"] == 256


@pytest.mark.asyncio
async def test_pqc_mtls_sign_verify_and_rotation(monkeypatch):
    monkeypatch.setattr(mod, "get_pqc_hybrid", lambda: _DummyHybrid(enabled=True))
    controller = mod.PQCmTLSController(enable_hybrid=True)
    await controller.initialize_pqc_keys()

    payload = b"payload-for-signing"
    signed_data, sig = await controller.sign_request(payload)
    assert signed_data == payload
    assert sig.algorithm == "ML-DSA-65"

    verified = await controller.verify_response(payload, sig.signature_bytes)
    assert verified is True

    rot = await controller.rotate_pqc_keys(validity_days=10)
    assert rot["status"] == "success"
    assert rot["old_kem_key_id"] != rot["new_kem_key_id"]


@pytest.mark.asyncio
async def test_test_pqc_mtls_setup_reports_disabled(monkeypatch):
    mod._pqc_mtls_controller = None
    monkeypatch.setattr(mod, "get_pqc_hybrid", lambda: _DummyHybrid(enabled=False))
    result = await mod.test_pqc_mtls_setup()
    assert result["status"] in {"disabled", "error"}
