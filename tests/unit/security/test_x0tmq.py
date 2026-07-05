"""Tests for x0tMQ: x0tta6bl4 MAVLink Quantum — post-quantum UAV auth.

Tests cover:
- MAVLink v2 frame codec (serialize/deserialize, CRC validation)
- x0CHUNK fragmentation and reassembly
- X0SessionManager key derivation, SESSION_INIT, SIGNED_CMD, SESSION_ACK
- HKDF-SHA3-256 key derivation
"""

from __future__ import annotations

import hashlib
import hmac
import struct

import pytest

from src.security.x0tmq.frame import MavlinkV2Frame
from src.security.x0tmq.chunk import X0Chunker, X0_CHUNK_MSG_ID
from src.security.x0tmq.session import X0SessionManager, X0_SESSION_INIT_ID, X0_SIGNED_CMD_ID, X0_SESSION_ACK_ID
from src.security.x0tmq.hkdf import derive_x0tmq_keys


# ---------------------------------------------------------------------------
# Frame codec
# ---------------------------------------------------------------------------

class TestMavlinkV2Frame:
    def test_roundtrip_small_payload(self) -> None:
        payload = bytes(range(64))
        frame = MavlinkV2Frame(sys_id=1, comp_id=2, msg_id=50000, payload=payload, seq=0)
        wire = frame.serialize()
        decoded = MavlinkV2Frame.deserialize(wire)
        assert decoded is not None
        assert decoded.msg_id == 50000
        assert decoded.payload == payload
        assert decoded.sys_id == 1
        assert decoded.seq == 0

    def test_roundtrip_empty_payload(self) -> None:
        frame = MavlinkV2Frame(sys_id=1, comp_id=2, msg_id=50001, payload=b"")
        wire = frame.serialize()
        decoded = MavlinkV2Frame.deserialize(wire)
        assert decoded is not None
        assert decoded.payload == b""

    def test_crc_detects_corruption(self) -> None:
        payload = b"hello"
        frame = MavlinkV2Frame(sys_id=1, comp_id=2, msg_id=50002, payload=payload)
        wire = bytearray(frame.serialize())
        wire[-2] ^= 0xFF  # corrupt CRC
        assert MavlinkV2Frame.deserialize(bytes(wire)) is None

    def test_wrong_stx(self) -> None:
        wire = b"\x00" + b"\x00" * 11
        assert MavlinkV2Frame.deserialize(wire) is None

    def test_incompat_flags_rejected(self) -> None:
        frame = MavlinkV2Frame(sys_id=1, comp_id=2, msg_id=50000, payload=b"test", incompat_flags=0x01)
        wire = frame.serialize()
        assert MavlinkV2Frame.deserialize(wire) is None


# ---------------------------------------------------------------------------
# x0CHUNK
# ---------------------------------------------------------------------------

class TestX0Chunker:
    def test_fragment_and_reassemble(self) -> None:
        chunker = X0Chunker(sys_id=1, comp_id=2)
        original = bytes(range(256)) * 2  # 512 bytes, will span 3 chunks
        frames = chunker.fragment(session_id=42, data=original)
        assert len(frames) == 3  # 500 / 245 = 3 chunks

        for f in frames:
            assert f.msg_id == X0_CHUNK_MSG_ID
            assert len(f.payload) > 0

        reassembled = None
        for f in frames:
            result = chunker.process_chunk(f)
            if result is not None:
                reassembled = result
        assert reassembled == original

    def test_single_chunk(self) -> None:
        chunker = X0Chunker(sys_id=1, comp_id=2)
        data = b"hello world"
        frames = chunker.fragment(session_id=7, data=data)
        assert len(frames) == 1
        result = chunker.process_chunk(frames[0])
        assert result == data

    def test_wrong_msg_id_ignored(self) -> None:
        chunker = X0Chunker(sys_id=1, comp_id=2)
        # A non-chunk frame should be ignored (return None)
        frame = MavlinkV2Frame(sys_id=1, comp_id=2, msg_id=99999, payload=b"x")
        assert chunker.process_chunk(frame) is None

    def test_flush_session(self) -> None:
        chunker = X0Chunker(sys_id=1, comp_id=2)
        data = b"x" * 500
        frames = chunker.fragment(session_id=99, data=data)
        chunker.flush_session(99)
        # After flush, processing the same frames should fail
        #  (new buffer, chunk_idx collision resistant)
        result = chunker.process_chunk(frames[0])
        assert result is None  # not all chunks present

    def test_out_of_order_chunk_rejected(self) -> None:
        chunker = X0Chunker(sys_id=1, comp_id=2)
        data = b"x" * 500
        frames = chunker.fragment(session_id=10, data=data)
        # Process chunk 0 first
        chunker.process_chunk(frames[0])
        # Try to process chunk 0 again (out of order) - should be rejected
        result = chunker.process_chunk(frames[0])
        assert result is None

    def test_buffer_expiry(self) -> None:
        chunker = X0Chunker(sys_id=1, comp_id=2)
        data = b"x" * 500
        frames = chunker.fragment(session_id=20, data=data)
        # Process first chunk
        chunker.process_chunk(frames[0])
        assert len(chunker._buffers) == 1
        # Manually expire the buffer by setting timestamp far in the past
        key = (1, 2, 20)
        chunker._buffer_timestamps[key] = 0
        # Process next chunk - should evict expired buffer first
        chunker.process_chunk(frames[1])
        # Buffer should have been evicted and re-created for new chunk
        assert len(chunker._buffers) == 1


# ---------------------------------------------------------------------------
# HKDF-SHA3-256
# ---------------------------------------------------------------------------

class TestHKDF:
    def test_deterministic_key_derivation(self) -> None:
        ss = b"\x01" * 32
        keys1 = derive_x0tmq_keys(
            ss, client_nonce=b"\x02" * 32, server_nonce=b"\x03" * 32,
            transcript_hash=b"\x04" * 32,
            client_identity_hash=b"\x05" * 32,
            server_identity_hash=b"\x06" * 32,
        )
        keys2 = derive_x0tmq_keys(
            ss, client_nonce=b"\x02" * 32, server_nonce=b"\x03" * 32,
            transcript_hash=b"\x04" * 32,
            client_identity_hash=b"\x05" * 32,
            server_identity_hash=b"\x06" * 32,
        )
        assert keys1["session_key"] == keys2["session_key"]
        assert keys1["auth_key"] == keys2["auth_key"]
        assert keys1["cmd_key"] == keys2["cmd_key"]
        assert keys1["session_id"] == keys2["session_id"]

    def test_different_inputs_produce_different_keys(self) -> None:
        ss = b"\x01" * 32
        common = dict(client_nonce=b"\x02" * 32, server_nonce=b"\x03" * 32,
                       transcript_hash=b"\x04" * 32,
                       client_identity_hash=b"\x05" * 32,
                       server_identity_hash=b"\x06" * 32)
        keys_a = derive_x0tmq_keys(ss, **common)
        keys_b = derive_x0tmq_keys(b"\x07" * 32, **common)
        assert keys_a["session_key"] != keys_b["session_key"]

    def test_key_lengths(self) -> None:
        keys = derive_x0tmq_keys(
            b"\x01" * 32, client_nonce=b"\x02" * 32, server_nonce=b"\x03" * 32,
            transcript_hash=b"\x04" * 32,
            client_identity_hash=b"\x05" * 32,
            server_identity_hash=b"\x06" * 32,
        )
        assert len(keys["session_key"]) == 32
        assert len(keys["auth_key"]) == 32
        assert len(keys["cmd_key"]) == 32


# ---------------------------------------------------------------------------
# Session manager (structural — lightweight PQC delegation)
# ---------------------------------------------------------------------------

class TestX0SessionManager:
    def test_init_smoke(self) -> None:
        mgr = X0SessionManager(sys_id=1, comp_id=2)
        assert mgr.session_id is None
        assert mgr.session_key is None

    def test_generate_mlkem_keypair(self) -> None:
        kp = X0SessionManager.generate_mlkem_keypair()
        assert kp.parameter_set == "ML-KEM-1024"
        assert len(kp.encapsulation_key) > 0
        assert len(kp.decapsulation_key) > 0

    def test_generate_mldsa_keypair_65(self) -> None:
        sk, vk = X0SessionManager.generate_mldsa_keypair_65()
        assert len(sk) > 0
        assert len(vk) > 0

    def test_telemetry_hmac(self) -> None:
        mgr = X0SessionManager(sys_id=1, comp_id=2)
        mgr.set_session_from_secret(42, b"\xab" * 32)
        tag = mgr.authenticate_telemetry(b"hello")
        assert len(tag) == 32
        assert mgr.verify_telemetry(b"hello", tag)
        assert not mgr.verify_telemetry(b"hello!", tag)
        assert not mgr.verify_telemetry(b"hello", tag[:-1] + b"\x00")

    def test_telemetry_without_session_raises(self) -> None:
        mgr = X0SessionManager(sys_id=1, comp_id=2)
        with pytest.raises(ValueError, match="not established"):
            mgr.authenticate_telemetry(b"x")

    def test_session_ack_roundtrip(self) -> None:
        mgr_gcs = X0SessionManager(sys_id=1, comp_id=2)
        mgr_uav = X0SessionManager(sys_id=3, comp_id=4)

        # Both derive the same secret
        mgr_gcs.set_session_from_secret(99, b"\xca" * 32)
        mgr_uav.set_session_from_secret(99, b"\xca" * 32)

        ack = mgr_uav.build_session_ack()
        assert ack.msg_id == X0_SESSION_ACK_ID
        assert mgr_gcs.verify_session_ack(ack)

    def test_session_ack_wrong_secret(self) -> None:
        mgr_gcs = X0SessionManager(sys_id=1, comp_id=2)
        mgr_uav = X0SessionManager(sys_id=3, comp_id=4)

        mgr_gcs.set_session_from_secret(99, b"\xca" * 32)
        mgr_uav.set_session_from_secret(99, b"\xfe" * 32)  # different secret

        ack = mgr_uav.build_session_ack()
        assert not mgr_gcs.verify_session_ack(ack)
