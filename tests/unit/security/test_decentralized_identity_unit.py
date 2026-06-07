import json

from src.security.decentralized_identity import DIDGenerator, DIDManager, DIDResolver


def test_multibase_roundtrip_preserves_raw_key_bytes():
    data = b"\x00\x00" + bytes(range(1, 33))

    encoded = DIDGenerator.multibase_encode(data)

    assert DIDGenerator.multibase_decode(encoded) == data


def test_did_manager_uses_ed25519_signature_verification():
    manager = DIDManager("node-ed25519")
    payload = b"mesh identity challenge"

    signature = manager.sign(payload)

    assert len(manager.private_key) == 32
    assert len(manager.public_key) == 32
    assert len(signature) == 64
    assert manager.verify_signature(payload, signature, manager.public_key) is True
    assert manager.verify_signature(b"tampered", signature, manager.public_key) is False


def test_verify_credential_rejects_tampered_claim():
    manager = DIDManager("issuer-node")
    credential = manager.issue_credential(
        subject_did="did:mesh:subject:abc",
        credential_type="MeshNodeOperatorCredential",
        claims={"role": "operator"},
    )
    credential_dict = credential.to_dict()

    assert manager.verify_credential(credential_dict) == (True, "Credential valid")

    tampered = dict(credential_dict)
    tampered["credentialSubject"] = {
        **credential_dict["credentialSubject"],
        "role": "admin",
    }

    assert manager.verify_credential(tampered) == (
        False,
        "Invalid credential signature",
    )


def test_verify_credential_rejects_revoked_verification_method_after_rotation():
    manager = DIDManager("issuer-node")
    credential = manager.issue_credential(
        subject_did="did:mesh:subject:abc",
        credential_type="MeshNodeOperatorCredential",
        claims={"role": "operator"},
    )

    manager.rotate_key()

    assert manager.verify_credential(credential.to_dict()) == (
        False,
        "Verification method not found or revoked",
    )


def test_did_manager_thinking_status_redacts_did_subject_and_claims():
    manager = DIDManager("issuer-secret-node")
    credential = manager.issue_credential(
        subject_did="did:mesh:subject-secret:abc",
        credential_type="MeshNodeOperatorCredential",
        claims={"role": "private-operator", "ip": "10.9.8.7"},
    )
    assert manager.verify_credential(credential.to_dict()) == (
        True,
        "Credential valid",
    )

    status = json.dumps(manager.get_thinking_status(), sort_keys=True)

    assert "did_credential_verified" in status
    assert "hash" in status
    assert "issuer-secret-node" not in status
    assert "did:mesh:subject-secret:abc" not in status
    assert "private-operator" not in status
    assert "10.9.8.7" not in status
    assert credential.proof["proofValue"] not in status


def test_did_resolver_thinking_status_redacts_did_and_peer_endpoint():
    manager = DIDManager("resolver-secret-node")
    resolver = DIDResolver()
    resolver.register_peer_resolver("mesh://peer-secret")
    resolver.cache_document(manager.did, manager.document)

    assert resolver.resolve(manager.did)["id"] == manager.did

    status = json.dumps(resolver.get_thinking_status(), sort_keys=True)

    assert "did_resolver_cache_hit" in status
    assert "hash" in status
    assert manager.did not in status
    assert "resolver-secret-node" not in status
    assert "mesh://peer-secret" not in status
