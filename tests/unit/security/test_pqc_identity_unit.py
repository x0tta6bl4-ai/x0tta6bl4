"""Unit tests for src.security.pqc_identity with a mocked PQC backend."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

import src.security.pqc_identity as mod


class _FakeSecurity:
    _counter = 0

    def __init__(self, node_id: str, kem_algorithm: str = "ML-KEM-768", sig_algorithm: str = "ML-DSA-65"):
        type(self)._counter += 1
        self.node_id = node_id
        self.instance_id = type(self)._counter
        self.pq_backend = SimpleNamespace(kem_algorithm=kem_algorithm, sig_algorithm=sig_algorithm)
        self.sig_keypair = SimpleNamespace(algorithm=SimpleNamespace(value=sig_algorithm))
        self.last_signed_payload = b""
        self._sig_public_hex = f"{self.instance_id:064x}"
        self._kem_public_hex = f"{(self.instance_id + 1):064x}"
        self._key_id = f"key-{self.instance_id:08d}"

    def get_public_keys(self):
        return {
            "key_id": self._key_id,
            "sig_algorithm": self.pq_backend.sig_algorithm,
            "sig_public_key": self._sig_public_hex,
            "kem_algorithm": self.pq_backend.kem_algorithm,
            "kem_public_key": self._kem_public_hex,
        }

    def sign(self, payload: bytes) -> bytes:
        self.last_signed_payload = payload
        return b"\x10\x20"

    def verify(self, payload: bytes, signature: bytes, pubkey: bytes) -> bool:
        return signature == b"\x10\x20" and pubkey == bytes.fromhex(self._sig_public_hex)


@pytest.fixture
def patched_backend(monkeypatch):
    _FakeSecurity._counter = 0
    monkeypatch.setattr(mod, "PQMeshSecurityLibOQS", _FakeSecurity)
    return mod


def test_document_to_dict_filters_revoked_methods():
    active = mod.PQCVerificationMethod(
        id="did:mesh:pqc:node#sig-1",
        type="ML-DSA-65",
        controller="did:mesh:pqc:node",
        public_key_hex="aa",
        key_id="key-1",
        revoked=False,
    )
    revoked = mod.PQCVerificationMethod(
        id="did:mesh:pqc:node#sig-2",
        type="ML-DSA-65",
        controller="did:mesh:pqc:node",
        public_key_hex="bb",
        key_id="key-2",
        revoked=True,
    )
    doc = mod.PQCDIDDocument(
        id="did:mesh:pqc:node",
        verification_method=[active, revoked],
        authentication=[active.id],
        assertion_method=[active.id],
        key_agreement=["did:mesh:pqc:node#kem-1"],
        created=1.0,
        updated=2.0,
    )
    payload = doc.to_dict()

    assert payload["id"] == "did:mesh:pqc:node"
    assert len(payload["verificationMethod"]) == 1
    assert payload["verificationMethod"][0]["id"] == active.id
    assert payload["created"] == datetime.fromtimestamp(1.0).isoformat()
    assert payload["updated"] == datetime.fromtimestamp(2.0).isoformat()


def test_identity_init_creates_did_and_document(patched_backend, monkeypatch):
    monkeypatch.setattr(patched_backend, "LIBOQS_AVAILABLE", True)
    identity = patched_backend.PQCNodeIdentity("node-1")
    key_prefix = identity.security.get_public_keys()["key_id"][:8]

    assert identity.did == f"did:mesh:pqc:node-1:{key_prefix}"
    assert identity.document.id == identity.did
    assert identity.document.authentication == [f"{identity.did}#sig-1"]
    assert identity.document.key_agreement == [f"{identity.did}#kem-1"]
    assert len(identity.document.verification_method) == 2


def test_sign_manifest_includes_expected_proof(patched_backend, monkeypatch):
    monkeypatch.setattr(patched_backend, "LIBOQS_AVAILABLE", True)
    identity = patched_backend.PQCNodeIdentity("node-a")
    manifest = {"b": 2, "a": 1}
    signed = identity.sign_manifest(manifest)

    assert identity.security.last_signed_payload == json.dumps(manifest, sort_keys=True).encode()
    assert signed["manifest"] == manifest
    assert signed["proof"]["type"] == "ML-DSA-65"
    assert signed["proof"]["verificationMethod"] == identity.document.authentication[0]
    assert signed["proof"]["signatureValue"] == "1020"


def test_verify_remote_node_success_and_error_path(patched_backend, monkeypatch):
    monkeypatch.setattr(patched_backend, "LIBOQS_AVAILABLE", True)
    identity = patched_backend.PQCNodeIdentity("node-v")
    signed = identity.sign_manifest({"status": "ok"})
    remote_pub = identity.security.get_public_keys()["sig_public_key"]

    assert identity.verify_remote_node(signed, remote_pub) is True
    assert identity.verify_remote_node({"invalid": "shape"}, remote_pub) is False


def test_rotate_keys_reinitializes_backend_and_updates_timestamp(patched_backend, monkeypatch):
    monkeypatch.setattr(patched_backend, "LIBOQS_AVAILABLE", True)
    identity = patched_backend.PQCNodeIdentity("node-r")
    old_backend = identity.security

    monkeypatch.setattr(patched_backend.time, "time", lambda: 12345.0)
    returned_did = identity.rotate_keys()

    assert returned_did == identity.did
    assert identity.security is not old_backend
    assert identity.document.updated == 12345.0


def test_init_logs_critical_when_liboqs_unavailable(patched_backend, monkeypatch, caplog):
    monkeypatch.setattr(patched_backend, "LIBOQS_AVAILABLE", False)
    with caplog.at_level("CRITICAL"):
        patched_backend.PQCNodeIdentity("node-x")
    assert any("liboqs is NOT available" in message for message in caplog.messages)
