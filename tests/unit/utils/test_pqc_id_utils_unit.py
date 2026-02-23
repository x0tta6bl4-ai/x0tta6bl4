"""Unit tests for src.utils.pqc_id_utils."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.utils.pqc_id_utils import extract_node_id_from_did, verify_pqc_manifest


def test_verify_pqc_manifest_delegates_to_identity_manager():
    signed = {
        "manifest": {"status": "ok"},
        "proof": {"publicKeyHex": "deadbeef"},
    }
    identity = MagicMock()
    identity.verify_remote_node.return_value = True

    assert verify_pqc_manifest(signed, identity) is True
    identity.verify_remote_node.assert_called_once_with(signed, "deadbeef")


def test_verify_pqc_manifest_without_public_key_returns_false():
    signed = {"manifest": {"status": "ok"}, "proof": {}}
    identity = MagicMock()

    assert verify_pqc_manifest(signed, identity) is False
    identity.verify_remote_node.assert_not_called()


def test_verify_pqc_manifest_catches_verifier_errors():
    signed = {
        "manifest": {"status": "ok"},
        "proof": {"publicKeyHex": "deadbeef"},
    }
    identity = MagicMock()
    identity.verify_remote_node.side_effect = RuntimeError("verifier down")

    assert verify_pqc_manifest(signed, identity) is False


def test_extract_node_id_from_did_valid_and_invalid_cases():
    assert extract_node_id_from_did("did:mesh:pqc:node-123:key-abc") == "node-123"
    assert extract_node_id_from_did("did:mesh:pqc:node-only") == "node-only"
    assert extract_node_id_from_did("did:other:pqc:node-123:key-abc") is None
    assert extract_node_id_from_did("did:mesh:legacy:node-123:key-abc") is None
    assert extract_node_id_from_did("did:mesh:pqc::key-abc") is None
    assert extract_node_id_from_did(None) is None
    assert extract_node_id_from_did("not-a-did") is None
