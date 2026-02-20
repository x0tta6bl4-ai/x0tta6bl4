"""Unit tests for PQC Verification Daemon."""
import os
import hashlib
import struct
import time
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.pqc_verification_daemon import (
    PQCVerificationEvent,
    VerifiedSession,
    PQCVerificationDaemon,
    MockPQCVerificationDaemon,
)


class TestPQCVerificationEvent:
    def test_fields(self):
        e = PQCVerificationEvent(
            session_id=b"\x01" * 16,
            signature=b"\x02" * 100,
            payload_hash=b"\x03" * 32,
            pubkey_id=b"\x04" * 16,
            timestamp=12345,
        )
        assert len(e.session_id) == 16
        assert len(e.payload_hash) == 32
        assert e.timestamp == 12345


class TestVerifiedSession:
    def test_defaults(self):
        s = VerifiedSession(session_id=b"\x01" * 16, expiration=99999)
        assert s.verification_count == 0
        assert s.last_verified == 0

    def test_custom(self):
        s = VerifiedSession(session_id=b"\x01" * 16, expiration=99999,
                           verification_count=5, last_verified=1.0)
        assert s.verification_count == 5


class TestPQCVerificationDaemonInit:
    def test_default_init(self):
        d = PQCVerificationDaemon()
        assert d.bpf is None
        assert d.public_keys == {}
        assert d.anomaly_callback is None
        assert d.running is False
        assert d.stats["events_received"] == 0

    def test_with_public_key_store(self):
        keys = {b"\x01" * 16: b"key1"}
        d = PQCVerificationDaemon(public_key_store=keys)
        assert len(d.public_keys) == 1

    def test_with_bpf(self):
        bpf = MagicMock()
        d = PQCVerificationDaemon(bpf=bpf)
        bpf.get_table.assert_called()

    def test_init_bpf_maps_missing(self):
        bpf = MagicMock()
        bpf.get_table.side_effect = KeyError("not found")
        d = PQCVerificationDaemon(bpf=bpf)
        assert d.pqc_events_ringbuf is None


class TestRegisterPublicKey:
    def test_register(self):
        d = PQCVerificationDaemon()
        d.register_public_key(b"\x01" * 16, b"pubkey_data")
        assert b"\x01" * 16 in d.public_keys

    def test_invalid_length(self):
        d = PQCVerificationDaemon()
        with pytest.raises(ValueError, match="16 bytes"):
            d.register_public_key(b"\x01" * 10, b"pubkey")


class TestVerifySignature:
    @patch("src.network.ebpf.pqc_verification_daemon.LIBOQS_AVAILABLE", False)
    def test_mock_mode(self):
        d = PQCVerificationDaemon()
        d.sig = None
        assert d.verify_signature(b"msg", b"sig", b"key") is True

    @patch("src.network.ebpf.pqc_verification_daemon.LIBOQS_AVAILABLE", True)
    def test_real_mode_success(self):
        d = PQCVerificationDaemon()
        d.sig = MagicMock()
        d.sig.verify.return_value = True
        assert d.verify_signature(b"msg", b"sig", b"key") is True

    @patch("src.network.ebpf.pqc_verification_daemon.LIBOQS_AVAILABLE", True)
    def test_real_mode_failure(self):
        d = PQCVerificationDaemon()
        d.sig = MagicMock()
        d.sig.verify.return_value = False
        assert d.verify_signature(b"msg", b"sig", b"key") is False

    @patch("src.network.ebpf.pqc_verification_daemon.LIBOQS_AVAILABLE", True)
    def test_real_mode_exception(self):
        d = PQCVerificationDaemon()
        d.sig = MagicMock()
        d.sig.verify.side_effect = Exception("oqs error")
        assert d.verify_signature(b"msg", b"sig", b"key") is False


class TestParseEvent:
    def test_too_short(self):
        d = PQCVerificationDaemon()
        assert d._parse_event(b"\x00" * 10) is None

    def test_valid_event(self):
        d = PQCVerificationDaemon()
        # Build a properly-sized event buffer
        data = bytearray(PQCVerificationDaemon.EVENT_SIZE)
        # session_id (16 bytes)
        data[0:16] = b"\xAA" * 16
        # signature_len at offset 16+4627 = 4643
        sig_len = 100
        struct.pack_into("<H", data, 4643, sig_len)
        # signature at 16..116
        data[16:116] = b"\xBB" * 100
        # payload_hash at 4645..4677
        data[4645:4677] = b"\xCC" * 32
        # pubkey_id at 4677..4693
        data[4677:4693] = b"\xDD" * 16
        # timestamp at 4693..4701
        struct.pack_into("<Q", data, 4693, 999999)

        event = d._parse_event(bytes(data))
        assert event is not None
        assert event.session_id == b"\xAA" * 16
        assert event.pubkey_id == b"\xDD" * 16
        assert event.timestamp == 999999

    def test_parse_exception(self):
        d = PQCVerificationDaemon()
        # Event that causes struct unpack error (too short for sig_len)
        data = b"\x00" * 100
        result = d._parse_event(data)
        # Should return None (parsing error handled)
        assert result is None


class TestVerifyEvent:
    def test_unknown_pubkey(self):
        d = PQCVerificationDaemon()
        cb = MagicMock()
        d.anomaly_callback = cb
        event = PQCVerificationEvent(
            session_id=b"\x01" * 16, signature=b"\x02" * 100,
            payload_hash=b"\x03" * 32, pubkey_id=b"\x04" * 16, timestamp=0
        )
        d._verify_event(event)
        assert d.stats["unknown_pubkey"] == 1
        cb.assert_called_once()

    def test_successful_verification(self):
        d = PQCVerificationDaemon()
        d.verify_signature = MagicMock(return_value=True)
        pubkey_id = b"\x04" * 16
        d.public_keys[pubkey_id] = b"pubkey_data"
        event = PQCVerificationEvent(
            session_id=b"\x01" * 16, signature=b"\x02" * 100,
            payload_hash=b"\x03" * 32, pubkey_id=pubkey_id, timestamp=0
        )
        d._verify_event(event)
        assert d.stats["verifications_success"] == 1
        assert b"\x01" * 16 in d.verified_sessions

    def test_repeated_verification_increments_count(self):
        d = PQCVerificationDaemon()
        d.verify_signature = MagicMock(return_value=True)
        pubkey_id = b"\x04" * 16
        d.public_keys[pubkey_id] = b"pubkey_data"
        event = PQCVerificationEvent(
            session_id=b"\x01" * 16, signature=b"\x02" * 100,
            payload_hash=b"\x03" * 32, pubkey_id=pubkey_id, timestamp=0
        )
        d._verify_event(event)
        d._verify_event(event)
        assert d.verified_sessions[b"\x01" * 16].verification_count == 2

    def test_failed_verification(self):
        d = PQCVerificationDaemon()
        pubkey_id = b"\x04" * 16
        d.public_keys[pubkey_id] = b"pubkey_data"
        d.verify_signature = MagicMock(return_value=False)
        cb = MagicMock()
        d.anomaly_callback = cb
        event = PQCVerificationEvent(
            session_id=b"\x01" * 16, signature=b"\x02" * 100,
            payload_hash=b"\x03" * 32, pubkey_id=pubkey_id, timestamp=0
        )
        d._verify_event(event)
        assert d.stats["verifications_failed"] == 1
        cb.assert_called_once()


class TestUpdateBPFVerifiedSession:
    def test_no_map(self):
        d = PQCVerificationDaemon()
        d._update_bpf_verified_session(b"\x01" * 16, 99999)  # Should not raise

    def test_with_map(self):
        d = PQCVerificationDaemon()
        d.pqc_verified_sessions_map = {}
        d._update_bpf_verified_session(b"\x01" * 16, 99999)
        assert b"\x01" * 16 in d.pqc_verified_sessions_map

    def test_map_error(self):
        d = PQCVerificationDaemon()
        m = MagicMock()
        m.__setitem__ = MagicMock(side_effect=Exception("map error"))
        d.pqc_verified_sessions_map = m
        d._update_bpf_verified_session(b"\x01" * 16, 99999)  # Should not raise


class TestCleanupExpiredSessions:
    def test_no_expired(self):
        d = PQCVerificationDaemon()
        future = time.time_ns() + 999999999999
        d.verified_sessions[b"\x01" * 16] = VerifiedSession(
            session_id=b"\x01" * 16, expiration=future
        )
        d.cleanup_expired_sessions()
        assert len(d.verified_sessions) == 1

    def test_expired_removed(self):
        d = PQCVerificationDaemon()
        past = time.time_ns() - 999
        d.verified_sessions[b"\x01" * 16] = VerifiedSession(
            session_id=b"\x01" * 16, expiration=past
        )
        d.cleanup_expired_sessions()
        assert len(d.verified_sessions) == 0
        assert d.stats["expired_sessions"] == 1

    def test_expired_with_bpf_map(self):
        d = PQCVerificationDaemon()
        d.pqc_verified_sessions_map = {}
        d.pqc_verified_sessions_map[b"\x01" * 16] = b"data"
        past = time.time_ns() - 999
        d.verified_sessions[b"\x01" * 16] = VerifiedSession(
            session_id=b"\x01" * 16, expiration=past
        )
        d.cleanup_expired_sessions()
        assert b"\x01" * 16 not in d.pqc_verified_sessions_map


class TestGetStats:
    def test_initial(self):
        d = PQCVerificationDaemon()
        stats = d.get_stats()
        assert stats["events_received"] == 0
        assert stats["active_sessions"] == 0
        assert stats["registered_pubkeys"] == 0

    def test_after_activity(self):
        d = PQCVerificationDaemon()
        d.stats["events_received"] = 10
        d.public_keys[b"\x01" * 16] = b"key"
        d.verified_sessions[b"\x02" * 16] = VerifiedSession(
            session_id=b"\x02" * 16, expiration=99999
        )
        stats = d.get_stats()
        assert stats["active_sessions"] == 1
        assert stats["registered_pubkeys"] == 1


class TestDaemonStartStop:
    def test_start_no_bcc(self):
        d = PQCVerificationDaemon()
        with patch("src.network.ebpf.pqc_verification_daemon.BCC_AVAILABLE", False):
            d.start()  # Should return immediately
        assert d.running is False

    def test_start_no_ringbuf(self):
        d = PQCVerificationDaemon()
        with patch("src.network.ebpf.pqc_verification_daemon.BCC_AVAILABLE", True):
            d.start()  # No ring buffer
        assert d.running is False

    def test_stop(self):
        d = PQCVerificationDaemon()
        d.running = True
        d.stop()
        assert d.running is False


class TestProcessEvent:
    def test_increments_events_received(self):
        d = PQCVerificationDaemon()
        d._parse_event = MagicMock(return_value=None)
        d._process_event(0, b"\x00" * 100, 100)
        assert d.stats["events_received"] == 1

    def test_submits_to_executor(self):
        d = PQCVerificationDaemon()
        mock_event = MagicMock()
        d._parse_event = MagicMock(return_value=mock_event)
        d.executor = MagicMock()
        d._process_event(0, b"\x00" * 100, 100)
        d.executor.submit.assert_called_once()


class TestMockDaemon:
    def test_init(self):
        d = MockPQCVerificationDaemon()
        assert d.bpf is None
        assert d._mock_mode is True

    def test_verify_always_true(self):
        d = MockPQCVerificationDaemon()
        assert d.verify_signature(b"m", b"s", b"k") is True

    def test_submit_event(self):
        d = MockPQCVerificationDaemon()
        pubkey_id = b"\x04" * 16
        d.public_keys[pubkey_id] = b"key"
        event = PQCVerificationEvent(
            session_id=b"\x01" * 16, signature=b"\x02" * 100,
            payload_hash=b"\x03" * 32, pubkey_id=pubkey_id, timestamp=0
        )
        d.submit_event(event)
        assert len(d.pending_events) == 1
        assert d.stats["verifications_success"] == 1

    def test_start_stop(self):
        d = MockPQCVerificationDaemon()
        d.start()
        assert d.running is True
        d.stop()
        assert d.running is False
