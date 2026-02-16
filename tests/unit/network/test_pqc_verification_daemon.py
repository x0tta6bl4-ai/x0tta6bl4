#!/usr/bin/env python3
"""
Unit tests for PQC Verification Daemon
Tests the userspace ML-DSA-65 verification offload component.
"""

import hashlib
import secrets
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

# Import the daemon module
from src.network.ebpf.pqc_verification_daemon import (
    LIBOQS_AVAILABLE, MockPQCVerificationDaemon, PQCVerificationDaemon,
    PQCVerificationEvent, VerifiedSession)


class TestPQCVerificationEvent:
    """Tests for PQCVerificationEvent dataclass"""

    def test_create_event(self):
        """Test creating a verification event"""
        session_id = secrets.token_bytes(16)
        signature = secrets.token_bytes(100)
        payload_hash = hashlib.sha256(b"test").digest()
        pubkey_id = secrets.token_bytes(16)
        timestamp = time.time_ns()

        event = PQCVerificationEvent(
            session_id=session_id,
            signature=signature,
            payload_hash=payload_hash,
            pubkey_id=pubkey_id,
            timestamp=timestamp,
        )

        assert event.session_id == session_id
        assert event.signature == signature
        assert event.payload_hash == payload_hash
        assert event.pubkey_id == pubkey_id
        assert event.timestamp == timestamp


class TestVerifiedSession:
    """Tests for VerifiedSession dataclass"""

    def test_create_session(self):
        """Test creating a verified session"""
        session_id = secrets.token_bytes(16)
        expiration = time.time_ns() + 3600_000_000_000

        session = VerifiedSession(
            session_id=session_id,
            expiration=expiration,
            verification_count=1,
            last_verified=time.time(),
        )

        assert session.session_id == session_id
        assert session.expiration == expiration
        assert session.verification_count == 1


class TestMockPQCVerificationDaemon:
    """Tests for MockPQCVerificationDaemon"""

    def test_initialization(self):
        """Test daemon initialization"""
        daemon = MockPQCVerificationDaemon()

        assert daemon.running is False
        assert len(daemon.public_keys) == 0
        assert daemon.stats["events_received"] == 0

    def test_register_public_key(self):
        """Test registering a public key"""
        daemon = MockPQCVerificationDaemon()

        pubkey_id = secrets.token_bytes(16)
        public_key = secrets.token_bytes(1952)  # ML-DSA-65 pubkey size

        daemon.register_public_key(pubkey_id, public_key)

        assert pubkey_id in daemon.public_keys
        assert daemon.public_keys[pubkey_id] == public_key

    def test_register_public_key_invalid_id(self):
        """Test registering with invalid pubkey_id length"""
        daemon = MockPQCVerificationDaemon()

        with pytest.raises(ValueError, match="pubkey_id must be 16 bytes"):
            daemon.register_public_key(b"short", b"key")

    def test_submit_event_unknown_pubkey(self):
        """Test submitting event with unknown public key"""
        daemon = MockPQCVerificationDaemon()
        daemon.start()

        event = PQCVerificationEvent(
            session_id=secrets.token_bytes(16),
            signature=secrets.token_bytes(100),
            payload_hash=hashlib.sha256(b"test").digest(),
            pubkey_id=secrets.token_bytes(16),  # Unknown
            timestamp=time.time_ns(),
        )

        daemon.submit_event(event)

        assert daemon.stats["unknown_pubkey"] == 1
        assert daemon.stats["verifications_success"] == 0

    def test_submit_event_with_known_pubkey(self):
        """Test submitting event with registered public key"""
        daemon = MockPQCVerificationDaemon()
        daemon.start()

        pubkey_id = hashlib.sha256(b"test-peer").digest()[:16]
        public_key = secrets.token_bytes(1952)

        daemon.register_public_key(pubkey_id, public_key)

        event = PQCVerificationEvent(
            session_id=secrets.token_bytes(16),
            signature=secrets.token_bytes(100),
            payload_hash=hashlib.sha256(b"test").digest(),
            pubkey_id=pubkey_id,
            timestamp=time.time_ns(),
        )

        daemon.submit_event(event)

        # In mock mode, verification always succeeds
        assert daemon.stats["verifications_success"] == 1
        assert daemon.stats["verifications_failed"] == 0

    def test_multiple_verifications_same_session(self):
        """Test multiple verifications for same session increment count"""
        daemon = MockPQCVerificationDaemon()
        daemon.start()

        pubkey_id = hashlib.sha256(b"peer").digest()[:16]
        session_id = secrets.token_bytes(16)

        daemon.register_public_key(pubkey_id, b"key")

        # Submit same session multiple times
        for _ in range(3):
            event = PQCVerificationEvent(
                session_id=session_id,
                signature=secrets.token_bytes(100),
                payload_hash=hashlib.sha256(b"test").digest(),
                pubkey_id=pubkey_id,
                timestamp=time.time_ns(),
            )
            daemon.submit_event(event)

        assert daemon.stats["verifications_success"] == 3
        assert session_id in daemon.verified_sessions
        assert daemon.verified_sessions[session_id].verification_count == 3

    def test_get_stats(self):
        """Test getting daemon statistics"""
        daemon = MockPQCVerificationDaemon()

        pubkey_id = secrets.token_bytes(16)
        daemon.register_public_key(pubkey_id, b"key")

        stats = daemon.get_stats()

        assert "events_received" in stats
        assert "verifications_success" in stats
        assert "verifications_failed" in stats
        assert "active_sessions" in stats
        assert stats["registered_pubkeys"] == 1

    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions"""
        daemon = MockPQCVerificationDaemon()
        daemon.start()

        session_id = secrets.token_bytes(16)

        # Add expired session
        daemon.verified_sessions[session_id] = VerifiedSession(
            session_id=session_id,
            expiration=time.time_ns() - 1000,  # Already expired
            verification_count=1,
            last_verified=time.time() - 3700,
        )

        daemon.cleanup_expired_sessions()

        assert session_id not in daemon.verified_sessions
        assert daemon.stats["expired_sessions"] == 1

    def test_anomaly_callback(self):
        """Test anomaly callback is called on verification failure"""
        anomaly_events = []

        def anomaly_handler(event_type: str, data: dict):
            anomaly_events.append((event_type, data))

        daemon = MockPQCVerificationDaemon(anomaly_callback=anomaly_handler)
        daemon.start()

        event = PQCVerificationEvent(
            session_id=secrets.token_bytes(16),
            signature=secrets.token_bytes(100),
            payload_hash=hashlib.sha256(b"test").digest(),
            pubkey_id=secrets.token_bytes(16),  # Unknown pubkey
            timestamp=time.time_ns(),
        )

        daemon.submit_event(event)

        assert len(anomaly_events) == 1
        assert anomaly_events[0][0] == "unknown_pubkey"

    def test_stop(self):
        """Test stopping the daemon"""
        daemon = MockPQCVerificationDaemon()
        daemon.start()

        assert daemon.running is True

        daemon.stop()

        assert daemon.running is False


class TestPQCVerificationDaemonMockMode:
    """Tests for PQCVerificationDaemon in mock mode (no BCC)"""

    def test_initialization_without_bpf(self):
        """Test initialization without BPF object"""
        daemon = PQCVerificationDaemon(bpf=None)

        assert daemon.bpf is None
        assert daemon.pqc_events_ringbuf is None
        assert daemon.pqc_verified_sessions_map is None

    def test_verify_signature_mock_mode(self):
        """Test signature verification in mock mode"""
        daemon = PQCVerificationDaemon(bpf=None)

        # In mock mode (no liboqs), verification always succeeds
        result = daemon.verify_signature(
            message=b"test message", signature=b"mock signature", public_key=b"mock key"
        )

        if not LIBOQS_AVAILABLE:
            assert result is True


def _is_oqs_mocked():
    """Check if oqs is mocked by conftest"""
    try:
        import oqs

        # If oqs.Signature is a MagicMock, it's mocked
        return hasattr(oqs.Signature, "_mock_name") or "MagicMock" in str(
            type(oqs.Signature)
        )
    except ImportError:
        return True


@pytest.mark.skipif(not LIBOQS_AVAILABLE, reason="liboqs not available")
class TestPQCVerificationDaemonWithLiboqs:
    """Tests that require liboqs"""

    def test_real_signature_verification(self):
        """Test real ML-DSA-65 signature verification"""
        if _is_oqs_mocked():
            pytest.skip("oqs is mocked by conftest")

        import oqs

        # Generate keypair
        sig = oqs.Signature("ML-DSA-65")
        public_key = sig.generate_keypair()

        # Sign a message
        message = b"test message to sign"
        signature = sig.sign(message)

        # Create daemon and use its internal sig object
        daemon = PQCVerificationDaemon(bpf=None)

        # Direct verification using daemon's sig object
        result = daemon.sig.verify(message, signature, public_key)
        assert result is True

    def test_invalid_signature_fails(self):
        """Test that invalid signature fails verification"""
        if _is_oqs_mocked():
            pytest.skip("oqs is mocked by conftest")

        import oqs

        sig = oqs.Signature("ML-DSA-65")
        public_key = sig.generate_keypair()

        daemon = PQCVerificationDaemon(bpf=None)

        # Invalid signature should fail
        result = daemon.verify_signature(
            message=b"test",
            signature=b"invalid" * 100,  # Make it long enough
            public_key=public_key,
        )

        assert result is False


class TestIntegration:
    """Integration tests for daemon with mock BPF"""

    def test_full_verification_flow(self):
        """Test complete verification flow"""
        # Create daemon
        daemon = MockPQCVerificationDaemon()
        daemon.start()

        # Register peer
        peer_id = "peer-node-1"
        pubkey_id = hashlib.sha256(peer_id.encode()).digest()[:16]
        public_key = secrets.token_bytes(1952)

        daemon.register_public_key(pubkey_id, public_key)

        # Simulate packet verification
        session_id = secrets.token_bytes(16)
        payload = b"encrypted mesh data"
        payload_hash = hashlib.sha256(payload).digest()

        event = PQCVerificationEvent(
            session_id=session_id,
            signature=secrets.token_bytes(4627),  # Max ML-DSA-65 size
            payload_hash=payload_hash,
            pubkey_id=pubkey_id,
            timestamp=time.time_ns(),
        )

        daemon.submit_event(event)

        # Verify results
        stats = daemon.get_stats()
        assert stats["verifications_success"] == 1
        assert stats["active_sessions"] == 1

        # Session should be in cache
        assert session_id in daemon.verified_sessions

        daemon.stop()

    def test_mapek_anomaly_integration(self):
        """Test MAPE-K anomaly reporting integration"""
        anomalies = []

        def mapek_anomaly_handler(event_type: str, data: dict):
            anomalies.append(
                {"type": event_type, "data": data, "timestamp": time.time()}
            )

        daemon = MockPQCVerificationDaemon(anomaly_callback=mapek_anomaly_handler)
        daemon.start()

        # Trigger unknown pubkey anomaly
        event = PQCVerificationEvent(
            session_id=secrets.token_bytes(16),
            signature=secrets.token_bytes(100),
            payload_hash=hashlib.sha256(b"test").digest(),
            pubkey_id=secrets.token_bytes(16),
            timestamp=time.time_ns(),
        )

        daemon.submit_event(event)

        # Check anomaly was reported
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "unknown_pubkey"

        daemon.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
