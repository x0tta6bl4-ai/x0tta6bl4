"""
Tests for SVIDSigner — SPIFFE-verifiable PBFT message signing.
"""

import hashlib
import time
from copy import deepcopy

import pytest

from src.self_healing.svid_signer import SVIDSigner, MAX_CLOCK_SKEW


def _make_pbft_msg(overrides: dict = None) -> dict:
    msg = {
        "type": "prepare",
        "view": 0,
        "sequence": 1,
        "digest": "abcd1234",
        "sender_id": "node-a",
    }
    if overrides:
        msg.update(overrides)
    return msg


class TestSVIDSignerUnit:
    def test_sign_round_trip(self):
        """Signed message must verify correctly."""
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        msg = _make_pbft_msg()
        signed = signer.sign_payload(msg)
        assert "svid_signature" in signed
        assert "svid_signer" in signed
        assert signed["svid_signer"] == "spiffe://x0tta6bl4.mesh/workload/node-a"
        result = signer.verify_payload(signed)
        assert result is True

    def test_rejects_tampered_message(self):
        """Tampered payload must fail verification."""
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        msg = _make_pbft_msg()
        signed = signer.sign_payload(msg)
        # Tamper: change the sequence
        signed["sequence"] = 999
        result = signer.verify_payload(signed)
        assert result is False

    def test_rejects_wrong_signer(self):
        """Message must be verified against the actual signer, not claimed."""
        signer_a = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        signer_b = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-b", mode="dev")
        msg = _make_pbft_msg()
        signed = signer_a.sign_payload(msg)

        # Verify as node-b should fail (wrong signer/key)
        result = signer_b.verify_payload(signed)
        assert result is False

    def test_peer_key_registration(self):
        """Register a peer's key and verify messages from that peer."""
        signer_a = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        signer_a.register_peer("spiffe://x0tta6bl4.mesh/workload/node-b")

        signer_b = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-b", mode="dev")
        msg = _make_pbft_msg({"sender_id": "node-b"})
        signed = signer_b.sign_payload(msg)

        # signer_a should verify the message from its registered peer node-b
        result = signer_a.verify_payload(signed, expected_spiffe_id=signed["svid_signer"])
        assert result is True

    def test_clock_skew_rejection(self):
        """Old messages must be rejected."""
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        msg = _make_pbft_msg()
        signed = signer.sign_payload(msg)
        # Pretend time moved forward
        signed["svid_signature_ts"] = time.time() - MAX_CLOCK_SKEW * 2
        result = signer.verify_payload(signed)
        assert result is False

    def test_missing_signature_fields(self):
        """Messages without signature fields must be handled gracefully."""
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        msg = _make_pbft_msg()
        result = signer.verify_payload(msg)
        assert result is False

    def test_set_signing_key(self):
        """Explicit signing key must work."""
        key = hashlib.sha256(b"custom key").digest()
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        signer.set_signing_key(key)
        msg = _make_pbft_msg()
        signed = signer.sign_payload(msg)
        result = signer.verify_payload(signed)
        assert result is True

    def test_get_status_no_keys_leaked(self):
        """get_status must not leak key material."""
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        status = signer.get_status()
        assert status["mode"] == "dev"
        assert status["spiffe_id"].startswith("spiffe://")
        assert "signing_key" not in status
        assert "has_signing_key" in status

    def test_register_peer_with_explicit_key(self):
        """Register a peer with an explicit verification key."""
        signer = SVIDSigner(spiffe_id="spiffe://x0tta6bl4.mesh/workload/node-a", mode="dev")
        vk = hashlib.sha256(b"peer-vk").digest()
        signer.register_peer("spiffe://x0tta6bl4.mesh/workload/node-b", verification_key=vk)
        assert signer._known_peers["spiffe://x0tta6bl4.mesh/workload/node-b"] == vk

    def test_unknown_mode_raises(self):
        """Invalid mode must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown SVID signer mode"):
            SVIDSigner(spiffe_id="test", mode="invalid")

    def test_prod_mode_not_implemented(self):
        """Prod mode must raise NotImplementedError on sign."""
        signer = SVIDSigner(spiffe_id="test", mode="prod", _signing_key=b"test")
        with pytest.raises(NotImplementedError, match="SPIRE JWT-SVID signing"):
            signer.sign_payload({"test": "data"})
