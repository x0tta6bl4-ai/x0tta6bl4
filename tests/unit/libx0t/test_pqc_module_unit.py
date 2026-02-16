"""Unit tests for libx0t.crypto.pqc."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import libx0t.crypto.pqc as pqc_mod


def _patch_import_without_oqs(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = pqc_mod.importlib.import_module

    def fake_import(name: str, *args, **kwargs):
        if name == "oqs":
            raise ImportError("oqs not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(pqc_mod.importlib, "import_module", fake_import)


def test_pqc_fail_closed_without_oqs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X0T_ALLOW_INSECURE_PQC_SIM", raising=False)
    _patch_import_without_oqs(monkeypatch)

    pqc = pqc_mod.PQC()
    with pytest.raises(RuntimeError, match="PQC backend unavailable"):
        pqc.generate_keypair()


def test_pqc_insecure_simulation_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X0T_ALLOW_INSECURE_PQC_SIM", "1")
    _patch_import_without_oqs(monkeypatch)

    pqc = pqc_mod.PQC()
    pub, priv = pqc.generate_keypair()
    shared_a, ciphertext = pqc.encapsulate(pub)
    shared_b = pqc.decapsulate(ciphertext, priv)

    assert len(pub) == 32
    assert len(priv) == 32
    assert shared_a == shared_b
    assert pub != b"sim_pub"
    assert priv != b"sim_priv"
    assert shared_a != b"sim_shared"


def test_pqc_uses_real_oqs_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X0T_ALLOW_INSECURE_PQC_SIM", raising=False)

    class FakeKEM:
        def __init__(self, algorithm: str, secret_key: bytes | None = None):
            self.algorithm = algorithm
            self.secret_key = secret_key

        def generate_keypair(self) -> bytes:
            return b"fake_pub"

        def export_secret_key(self) -> bytes:
            return b"fake_priv"

        def encap_secret(self, peer_public_key: bytes) -> tuple[bytes, bytes]:
            assert peer_public_key == b"peer_pub"
            return b"fake_cipher", b"fake_shared"

        def decap_secret(self, ciphertext: bytes) -> bytes:
            assert self.secret_key == b"fake_priv"
            assert ciphertext == b"fake_cipher"
            return b"fake_shared"

    fake_oqs = SimpleNamespace(KeyEncapsulation=FakeKEM)
    original_import = pqc_mod.importlib.import_module

    def fake_import(name: str, *args, **kwargs):
        if name == "oqs":
            return fake_oqs
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(pqc_mod.importlib, "import_module", fake_import)

    pqc = pqc_mod.PQC(algorithm="Kyber768")
    pub, priv = pqc.generate_keypair()
    assert (pub, priv) == (b"fake_pub", b"fake_priv")

    shared, cipher = pqc.encapsulate(b"peer_pub")
    assert (shared, cipher) == (b"fake_shared", b"fake_cipher")
    assert pqc.decapsulate(cipher, priv) == b"fake_shared"
