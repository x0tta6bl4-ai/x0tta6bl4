import hashlib
import struct
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.pqc_verification_daemon import (
    PQC_VERIFICATION_DAEMON_SERVICE_NAME,
    PQCVerificationDaemon,
    PQCVerificationEvent,
    VerifiedSession,
)


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=PQC_VERIFICATION_DAEMON_SERVICE_NAME,
        limit=120,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _daemon(tmp_path, **kwargs):
    bus = EventBus(project_root=str(tmp_path))
    daemon = PQCVerificationDaemon(event_bus=bus, **kwargs)
    return daemon, bus


def _valid_event_bytes():
    data = bytearray(PQCVerificationDaemon.EVENT_SIZE)
    session_id = b"secret-session-1"
    signature = b"secret-signature"
    payload_hash = b"secret-payload-hash-000000000000"
    pubkey_id = b"secret-pubkey-01"
    data[0:16] = session_id
    struct.pack_into("<H", data, 16 + 4627, len(signature))
    data[16 : 16 + len(signature)] = signature
    data[4645:4677] = payload_hash
    data[4677:4693] = pubkey_id
    struct.pack_into("<Q", data, 4693, 123456789)
    return bytes(data), session_id, signature, payload_hash, pubkey_id


def test_bpf_map_init_publishes_redacted_map_evidence(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bpf = MagicMock()

    daemon = PQCVerificationDaemon(bpf=bpf, event_bus=bus)

    assert daemon.pqc_events_ringbuf is not None
    assert daemon.pqc_verified_sessions_map is not None
    payload = _stage_payload(bus, "pqc_verification_bpf_maps_initialized")
    assert payload["operation"] == "init_bpf_maps"
    assert payload["status"] == "success"
    assert payload["map_name_hashes"]["hashes"] == [
        hashlib.sha256(b"pqc_events").hexdigest(),
        hashlib.sha256(b"pqc_verified_sessions").hexdigest(),
    ]
    assert payload["map_names_redacted"] is True
    assert "pqc_events" not in str(payload)
    assert "pqc_verified_sessions" not in str(payload)


def test_register_public_key_publishes_redacted_evidence(tmp_path):
    daemon, bus = _daemon(tmp_path)
    pubkey_id = b"secret-pubkey-01"
    public_key = b"secret-public-key"

    daemon.register_public_key(pubkey_id, public_key)

    payload = _stage_payload(bus, "pqc_public_key_registered")
    assert payload["operation"] == "register_public_key"
    assert payload["status"] == "success"
    assert payload["pubkey_id_hash"] == hashlib.sha256(pubkey_id).hexdigest()
    assert payload["public_key_hash"] == hashlib.sha256(public_key).hexdigest()
    assert payload["identity"]["redacted"] is True
    assert pubkey_id.decode("utf-8") not in str(payload)
    assert public_key.decode("utf-8") not in str(payload)


def test_parse_event_publishes_redacted_ring_buffer_evidence(tmp_path):
    daemon, bus = _daemon(tmp_path)
    raw_event, session_id, signature, payload_hash, pubkey_id = _valid_event_bytes()

    event = daemon._parse_event(raw_event)

    assert event is not None
    payload = _stage_payload(bus, "pqc_ring_event_parsed")
    assert payload["operation"] == "parse_event"
    assert payload["parsed_summary"]["signature_len"] == len(signature)
    assert payload["session_id_hash"] == hashlib.sha256(session_id).hexdigest()
    assert payload["pubkey_id_hash"] == hashlib.sha256(pubkey_id).hexdigest()
    assert payload["signature_hash"] == hashlib.sha256(signature).hexdigest()
    assert session_id.decode("utf-8") not in str(payload)
    assert signature.decode("utf-8") not in str(payload)
    assert payload_hash.decode("utf-8") not in str(payload)
    assert pubkey_id.decode("utf-8") not in str(payload)


def test_successful_verification_and_map_update_publish_redacted_evidence(tmp_path):
    daemon, bus = _daemon(tmp_path)
    session_id = b"secret-session-1"
    pubkey_id = b"secret-pubkey-01"
    public_key = b"secret-public-key"
    signature = b"secret-signature"
    payload_hash = b"secret-payload-hash-000000000000"
    daemon.public_keys[pubkey_id] = public_key
    daemon.verify_signature = MagicMock(return_value=True)
    daemon.pqc_verified_sessions_map = {}

    daemon._verify_event(
        PQCVerificationEvent(
            session_id=session_id,
            signature=signature,
            payload_hash=payload_hash,
            pubkey_id=pubkey_id,
            timestamp=0,
        )
    )

    verify_payload = _stage_payload(bus, "pqc_verification_succeeded")
    map_payload = _stage_payload(bus, "pqc_verified_session_map_updated")
    assert verify_payload["parsed_summary"]["verified"] is True
    assert map_payload["parsed_summary"]["updated"] is True
    assert map_payload["map_name_hash"] == hashlib.sha256(
        b"pqc_verified_sessions"
    ).hexdigest()
    for secret in (session_id, pubkey_id, public_key, signature, payload_hash):
        assert secret.decode("utf-8") not in str(verify_payload)
        assert secret.decode("utf-8") not in str(map_payload)
    assert "pqc_verified_sessions" not in str(map_payload)


def test_unknown_pubkey_publishes_redacted_failure(tmp_path):
    daemon, bus = _daemon(tmp_path)
    session_id = b"secret-session-2"
    pubkey_id = b"secret-pubkey-02"

    daemon._verify_event(
        PQCVerificationEvent(
            session_id=session_id,
            signature=b"secret-signature",
            payload_hash=b"secret-payload-hash-111111111111",
            pubkey_id=pubkey_id,
            timestamp=0,
        )
    )

    payload = _stage_payload(bus, "pqc_verification_unknown_pubkey")
    assert payload["status"] == "failure"
    assert payload["parsed_summary"]["reason"] == "unknown_pubkey"
    assert payload["session_id_hash"] == hashlib.sha256(session_id).hexdigest()
    assert payload["pubkey_id_hash"] == hashlib.sha256(pubkey_id).hexdigest()
    assert session_id.decode("utf-8") not in str(payload)
    assert pubkey_id.decode("utf-8") not in str(payload)


def test_cleanup_expired_sessions_publishes_redacted_evidence(tmp_path):
    daemon, bus = _daemon(tmp_path)
    session_id = b"secret-session-3"
    daemon.pqc_verified_sessions_map = {session_id: b"secret-map-value"}
    daemon.verified_sessions[session_id] = VerifiedSession(
        session_id=session_id,
        expiration=0,
        verification_count=1,
        last_verified=0,
    )

    daemon.cleanup_expired_sessions()

    payload = _stage_payload(bus, "pqc_expired_sessions_cleanup_completed")
    assert payload["parsed_summary"]["expired_count"] == 1
    assert payload["expired_session_hashes"]["hashes"] == [
        hashlib.sha256(session_id).hexdigest()
    ]
    assert session_id.decode("utf-8") not in str(payload)
    assert "secret-map-value" not in str(payload)


def test_start_without_bcc_publishes_redacted_failure(tmp_path):
    daemon, bus = _daemon(tmp_path)

    with patch("src.network.ebpf.pqc_verification_daemon.BCC_AVAILABLE", False):
        daemon.start()

    payload = _stage_payload(bus, "pqc_verification_start_bcc_unavailable")
    assert payload["operation"] == "start"
    assert payload["status"] == "failure"
    assert payload["parsed_summary"] == {
        "started": False,
        "reason": "bcc_unavailable",
    }
