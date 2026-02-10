"""Unit tests for src.network.byzantine.signed_gossip module.

Tests PQC-signed gossip protocol: message signing/verification, anti-replay,
rate limiting, quarantine, reputation, and key rotation.

NOTE: The real `oqs` library is installed; we patch `Signature` at the
module level (`src.network.byzantine.signed_gossip.Signature`) so that
SignedGossip and SignedMessage use our configured mock.
"""

import os
import time as _real_time
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

try:
    from src.network.byzantine.signed_gossip import (
        SignedGossip,
        SignedMessage,
        MessageType,
        LIBOQS_AVAILABLE,
    )
    GOSSIP_AVAILABLE = True
except ImportError as exc:
    GOSSIP_AVAILABLE = False

pytestmark = pytest.mark.skipif(not GOSSIP_AVAILABLE, reason="signed_gossip not available")

MODULE_PATH = "src.network.byzantine.signed_gossip"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sig_mock():
    """Create a pre-configured MagicMock mimicking oqs.Signature instance."""
    sig_instance = MagicMock()
    sig_instance.generate_keypair.return_value = (b"pub" * 10, b"priv" * 10)
    sig_instance.sign.return_value = b"signature" * 8
    sig_instance.verify.return_value = True
    return sig_instance


@pytest.fixture
def sig_mock():
    """Patch Signature at module level and return the mock instance."""
    sig_instance = _make_sig_mock()
    mock_cls = MagicMock(return_value=sig_instance)
    with patch(f"{MODULE_PATH}.Signature", mock_cls):
        yield sig_instance


@pytest.fixture
def gossip(sig_mock):
    return SignedGossip("node-1")


@pytest.fixture
def gossip_pair(sig_mock):
    """Two gossip instances for sender/receiver tests."""
    g1 = SignedGossip("node-A")
    g2 = SignedGossip("node-B")
    return g1, g2


# ===========================================================================
# TestMessageType
# ===========================================================================

class TestMessageType:

    def test_all_values_exist(self):
        assert len(MessageType) == 6

    def test_beacon_value(self):
        assert MessageType.BEACON.value == "beacon"

    def test_key_rotation_value(self):
        assert MessageType.KEY_ROTATION.value == "key_rotation"


# ===========================================================================
# TestSignedMessage
# ===========================================================================

class TestSignedMessage:

    def test_serialize_excludes_signature_and_public_key(self):
        msg = SignedMessage(
            msg_type=MessageType.BEACON,
            sender="node-1",
            timestamp=1000.0,
            nonce=42,
            epoch=0,
            payload={"data": "test"},
            signature=b"should-not-appear",
            public_key=b"pk",
        )
        raw = msg.serialize()
        assert b"should-not-appear" not in raw
        assert b'"sender": "node-1"' in raw

    def test_verify_calls_oqs(self, sig_mock):
        """Verify delegates to oqs.Signature; we patch at module level."""
        sig_instance = _make_sig_mock()
        mock_cls = MagicMock(return_value=sig_instance)
        with patch(f"{MODULE_PATH}.Signature", mock_cls):
            msg = SignedMessage(
                msg_type=MessageType.BEACON,
                sender="node-1",
                timestamp=1000.0,
                nonce=1,
                epoch=0,
                payload={},
                signature=b"sig",
                public_key=b"pub" * 10,
            )
            result = msg.verify()
            assert result is True


# ===========================================================================
# TestSignedGossipInit
# ===========================================================================

class TestSignedGossipInit:

    def test_node_id_stored(self, gossip):
        assert gossip.node_id == "node-1"

    def test_keys_generated(self, gossip):
        assert gossip.public_key is not None
        assert gossip.private_key is not None

    def test_initial_epoch_zero(self, gossip):
        assert gossip._current_epoch == 0

    def test_empty_quarantine(self, gossip):
        assert len(gossip._quarantined) == 0


# ===========================================================================
# TestSignMessage
# ===========================================================================

class TestSignMessage:

    def test_returns_signed_message(self, gossip):
        msg = gossip.sign_message(MessageType.BEACON, {"hello": "world"})
        assert isinstance(msg, SignedMessage)
        assert msg.msg_type == MessageType.BEACON
        assert msg.sender == "node-1"

    def test_signature_is_bytes(self, gossip):
        msg = gossip.sign_message(MessageType.BEACON, {})
        assert isinstance(msg.signature, bytes)
        assert len(msg.signature) > 0

    def test_explicit_nonce(self, gossip):
        msg = gossip.sign_message(MessageType.BEACON, {}, nonce=99999)
        assert msg.nonce == 99999

    def test_auto_nonce_is_microsecond_precision(self, gossip):
        msg = gossip.sign_message(MessageType.BEACON, {})
        assert msg.nonce > 1_000_000  # microsecond timestamp

    def test_epoch_matches_current(self, gossip):
        msg = gossip.sign_message(MessageType.BEACON, {})
        assert msg.epoch == gossip._current_epoch


# ===========================================================================
# TestVerifyMessage
# ===========================================================================

class TestVerifyMessage:

    def test_valid_message_passes(self, gossip, sig_mock):
        """sig_mock patches Signature, so verify() inside verify_message works."""
        msg = gossip.sign_message(MessageType.BEACON, {"data": 1})
        valid, err = gossip.verify_message(msg)
        assert valid is True
        assert err is None

    def test_replay_detected(self, gossip, sig_mock):
        msg = gossip.sign_message(MessageType.BEACON, {}, nonce=42)
        gossip.verify_message(msg)  # first time OK
        valid, err = gossip.verify_message(msg)  # replay!
        assert valid is False
        assert "replay" in err.lower()

    def test_stale_epoch_rejected(self, gossip, sig_mock):
        gossip._current_epoch = 5
        msg = gossip.sign_message(MessageType.BEACON, {})
        msg.epoch = 2  # stale: 2 < (5-1)=4
        valid, err = gossip.verify_message(msg)
        assert valid is False
        assert "epoch" in err.lower()

    def test_invalid_signature_rejected(self, gossip, sig_mock):
        msg = gossip.sign_message(MessageType.BEACON, {})
        sig_mock.verify.return_value = False
        valid, err = gossip.verify_message(msg)
        assert valid is False
        assert "signature" in err.lower()


# ===========================================================================
# TestRateLimiting
# ===========================================================================

class TestRateLimiting:

    def test_rate_limit_exceeded(self, gossip, sig_mock):
        """Sending more than _rate_limit messages in 1 second triggers limit."""
        gossip._rate_limit = 3
        for i in range(3):
            msg = gossip.sign_message(MessageType.BEACON, {}, nonce=i + 1000)
            gossip.verify_message(msg)

        # 4th should be rate limited
        msg = gossip.sign_message(MessageType.BEACON, {}, nonce=2000)
        valid, err = gossip.verify_message(msg)
        assert valid is False
        assert "rate" in err.lower()


# ===========================================================================
# TestQuarantine
# ===========================================================================

class TestQuarantine:

    def test_is_quarantined_false_by_default(self, gossip):
        assert gossip.is_quarantined("node-X") is False

    def test_quarantine_blocks_messages(self, gossip, sig_mock):
        gossip._quarantined["bad-node"] = _real_time.time() + 3600
        msg = gossip.sign_message(MessageType.BEACON, {})
        msg.sender = "bad-node"
        valid, err = gossip.verify_message(msg)
        assert valid is False
        assert "quarantin" in err.lower()

    def test_quarantine_expires(self, gossip):
        gossip._quarantined["temp-node"] = _real_time.time() - 1  # already expired
        assert gossip.is_quarantined("temp-node") is False

    def test_low_reputation_triggers_quarantine(self, gossip):
        """Repeated penalties drop reputation below 0.3 and trigger quarantine."""
        gossip._reputation["attacker"] = 0.31
        gossip._penalize_node("attacker", "test")
        # 0.31 * 0.9 = 0.279 < 0.3 → quarantined
        assert gossip.is_quarantined("attacker") is True


# ===========================================================================
# TestReputation
# ===========================================================================

class TestReputation:

    def test_default_reputation_is_1(self, gossip):
        assert gossip.get_reputation("unknown-node") == pytest.approx(1.0)

    def test_penalize_reduces_reputation(self, gossip):
        gossip._penalize_node("node-X", "test")
        assert gossip.get_reputation("node-X") == pytest.approx(0.9)

    def test_reward_increases_reputation(self, gossip):
        gossip._reputation["node-X"] = 0.5
        gossip._reward_node("node-X")
        assert gossip.get_reputation("node-X") == pytest.approx(0.5 * 1.05)

    def test_reward_capped_at_1(self, gossip):
        gossip._reputation["node-X"] = 0.99
        gossip._reward_node("node-X")
        assert gossip.get_reputation("node-X") == pytest.approx(1.0)


# ===========================================================================
# TestKeyRotation
# ===========================================================================

class TestKeyRotation:

    def test_rotate_increments_epoch(self, gossip, sig_mock):
        assert gossip._current_epoch == 0
        gossip.rotate_keys()
        assert gossip._current_epoch == 1

    def test_rotate_generates_new_keys(self, gossip, sig_mock):
        old_pub = gossip.public_key
        gossip.rotate_keys()
        # generate_keypair was called again
        assert sig_mock.generate_keypair.call_count >= 2

    def test_rotate_clears_old_nonces(self, gossip, sig_mock):
        # Add nonces for epoch 0
        gossip._seen_nonces["node-X"][0].add(100)
        gossip._seen_nonces["node-X"][0].add(200)
        gossip.rotate_keys()
        # Epoch 0 nonces should be cleaned (only current epoch kept)
        assert 0 not in gossip._seen_nonces.get("node-X", {})
