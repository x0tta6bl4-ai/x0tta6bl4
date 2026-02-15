import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import time

import pytest

from src.security.decentralized_identity import (DIDDocument, DIDGenerator,
                                                 DIDManager, DIDResolver,
                                                 MeshCredentialTypes,
                                                 hmac_compare)


def test_did_generator_create_ids() -> None:
    public_key = b"\x11" * 32
    did_mesh = DIDGenerator.create_did_mesh("n1", public_key)
    did_key = DIDGenerator.create_did_key(public_key)
    assert did_mesh.startswith("did:mesh:n1:")
    assert len(did_mesh.split(":")[-1]) == 16
    assert did_key.startswith("did:key:z")


def test_multibase_encode_non_empty_prefix() -> None:
    encoded = DIDGenerator.multibase_encode(b"\x01\x02\x03")
    assert encoded.startswith("z")
    assert len(encoded) > 1


def test_manager_initial_document_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        DIDGenerator, "generate_keypair", lambda: (b"a" * 32, b"b" * 32)
    )
    manager = DIDManager("node-x")
    doc = manager.get_document()
    assert doc["id"] == manager.did
    assert doc["authentication"][0].endswith("#key-1")
    assert doc["service"][0]["type"] == "MeshMessaging"


def test_rotate_key_revokes_previous_and_updates_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = [(b"a" * 32, b"b" * 32), (b"c" * 32, b"d" * 32)]
    monkeypatch.setattr(DIDGenerator, "generate_keypair", lambda: keys.pop(0))
    manager = DIDManager("node-r")
    first_id = manager.document.authentication[0]
    new_vm = manager.rotate_key()
    assert new_vm.id != first_id
    assert manager.document.authentication == [new_vm.id]
    assert len(manager.key_history) == 1
    assert manager.key_history[0].revoked is True


def test_sign_and_verify_signature_false_for_mismatched_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DIDGenerator, "generate_keypair", lambda: (b"x" * 32, b"y" * 32)
    )
    manager = DIDManager("node-s")
    payload = b"hello"
    signature = manager.sign(payload)
    assert manager.verify_signature(payload, signature, manager.public_key) is False


def test_issue_credential_with_and_without_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DIDGenerator, "generate_keypair", lambda: (b"a" * 32, b"b" * 32)
    )
    manager = DIDManager("issuer")

    vc1 = manager.issue_credential(
        subject_did="did:mesh:subj:1",
        credential_type=MeshCredentialTypes.NODE_OPERATOR,
        claims={"role": "operator"},
        expiration_days=1,
    )
    vc2 = manager.issue_credential(
        subject_did="did:mesh:subj:2",
        credential_type=MeshCredentialTypes.TRUST_ANCHOR,
        claims={"anchor": True},
        expiration_days=None,
    )
    d1 = vc1.to_dict()
    d2 = vc2.to_dict()
    assert "proof" in d1
    assert "expirationDate" in d1
    assert "expirationDate" not in d2
    assert vc1.id in manager.credentials
    assert vc2.id in manager.credentials


def test_verify_credential_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        DIDGenerator, "generate_keypair", lambda: (b"a" * 32, b"b" * 32)
    )
    manager = DIDManager("issuer-v")
    vc = manager.issue_credential(
        subject_did="did:mesh:subj:v",
        credential_type=MeshCredentialTypes.PEER_ATTESTATION,
        claims={"ok": True},
    ).to_dict()

    ok, msg = manager.verify_credential(vc)
    assert ok is True
    assert "valid" in msg.lower()

    no_proof = dict(vc)
    no_proof.pop("proof", None)
    ok, msg = manager.verify_credential(no_proof)
    assert ok is False
    assert msg == "No proof found"

    bad_type = dict(vc)
    bad_type["proof"] = dict(vc["proof"])
    bad_type["proof"]["type"] = "Unknown"
    ok, msg = manager.verify_credential(bad_type)
    assert ok is False
    assert "Unknown proof type" in msg

    expired = dict(vc)
    expired["expirationDate"] = "2000-01-01T00:00:00+00:00"
    ok, msg = manager.verify_credential(expired)
    assert ok is False
    assert msg == "Credential expired"

    broken = dict(vc)
    broken["expirationDate"] = {"not": "iso"}  # type: ignore[assignment]
    ok, msg = manager.verify_credential(broken)
    assert ok is False
    assert "Verification error" in msg


def test_create_presentation_includes_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        DIDGenerator, "generate_keypair", lambda: (b"a" * 32, b"b" * 32)
    )
    manager = DIDManager("holder")
    vc = manager.issue_credential(
        subject_did="did:mesh:subj:p",
        credential_type=MeshCredentialTypes.SERVICE_AUTHORIZATION,
        claims={"svc": "x"},
    )
    pres = manager.create_presentation([vc], challenge="nonce-1")
    assert pres["holder"] == manager.did
    assert pres["proof"]["challenge"] == "nonce-1"
    assert len(pres["verifiableCredential"]) == 1


def test_deactivate_revokes_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        DIDGenerator, "generate_keypair", lambda: (b"a" * 32, b"b" * 32)
    )
    manager = DIDManager("node-z")
    manager.rotate_key()
    manager.deactivate()
    assert manager.document.deactivated is True
    assert all(vm.revoked for vm in manager.document.verification_method)


def test_resolver_cache_and_method_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = DIDResolver()
    doc = DIDDocument(id="did:mesh:cached:1")
    resolver.cache_document("did:mesh:cached:1", doc)
    cached = resolver.resolve("did:mesh:cached:1")
    assert cached is not None
    assert cached["id"] == "did:mesh:cached:1"

    # expire cache and route to mesh resolver (returns None)
    resolver.cache["did:mesh:cached:1"] = (doc, time.time() - resolver.cache_ttl - 1)
    assert resolver.resolve("did:mesh:cached:1") is None
    assert resolver.resolve("did:key:zabc")["id"] == "did:key:zabc"
    assert resolver.resolve("did:web:example.com") is None
    assert resolver.resolve("did:unknown:x") is None
    assert resolver.resolve("bad-did-format") is None


def test_resolver_register_peer_unique() -> None:
    resolver = DIDResolver()
    resolver.register_peer_resolver("http://p1")
    resolver.register_peer_resolver("http://p1")
    resolver.register_peer_resolver("http://p2")
    assert resolver.peer_resolvers == ["http://p1", "http://p2"]


def test_hmac_compare_behaviour() -> None:
    assert hmac_compare(b"abc", b"abc") is True
    assert hmac_compare(b"abc", b"abd") is False
    assert hmac_compare(b"a", b"ab") is False
