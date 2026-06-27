from src.security.decentralized_identity import DIDGenerator, DIDManager


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
