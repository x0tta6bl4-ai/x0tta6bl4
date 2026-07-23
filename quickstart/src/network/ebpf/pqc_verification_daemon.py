#!/usr/bin/env python3
"""
PQC Verification Daemon for x0tta6bl4
Userspace offload for ML-DSA-65 signature verification.

This daemon:
1. Reads PQC verification events from eBPF ring buffer
2. Performs ML-DSA-65 signature verification using liboqs
3. Updates pqc_verified_sessions BPF map on success
4. Integrates with MAPE-K loop for anomaly reporting

Architecture:
    eBPF XDP (kernel) --[ring buffer]--> Daemon (userspace) --[BPF map]--> eBPF XDP

The XDP program sends unverified packets to userspace, daemon verifies,
and marks sessions as verified in BPF map for fast-path processing.
"""
from __future__ import annotations

import hashlib
import logging
import signal
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Try to import BCC
try:
    from bcc import BPF

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    BPF = None  # type: ignore
    logger.warning("BCC not available - daemon will run in mock mode")

# Try to import liboqs
try:
    import oqs

    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("liboqs not available - using mock verification")


PQC_VERIFICATION_DAEMON_SERVICE_NAME = "pqc-verification-daemon"
PQC_VERIFICATION_DAEMON_LAYER = "network_ebpf_pqc_verification_observed_state"
PQC_VERIFICATION_DAEMON_CLAIM_BOUNDARY = (
    "Local PQC verification daemon evidence only. Events record userspace "
    "ring-buffer handling, signature verification mode/outcome, verified-session "
    "map mutation attempts, public-key registration, cleanup, and lifecycle "
    "state with hashed session/public-key/message/map selectors; they do not "
    "prove remote peer identity, production traffic, or kernel datapath "
    "enforcement beyond the local userspace operation result."
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return _sha256_text(str(value))


def _bounded_output_metadata(
    stdout: Optional[Any] = None,
    stderr: Optional[Any] = None,
) -> Dict[str, Any]:
    safe_stdout = _normalize_text(stdout)
    safe_stderr = _normalize_text(stderr)
    return {
        "stdout_chars": len(safe_stdout),
        "stderr_chars": len(safe_stderr),
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "output_bounded": True,
        "output_redacted": True,
    }


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=PQC_VERIFICATION_DAEMON_SERVICE_NAME)
    return {
        "service_name": PQC_VERIFICATION_DAEMON_SERVICE_NAME,
        "layer": PQC_VERIFICATION_DAEMON_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _bounded_hashes(values: List[Any], limit: int = 20) -> Dict[str, Any]:
    selected = values[:limit]
    return {
        "hashes": [_hash_value(value) for value in selected],
        "count": len(values),
        "limit": limit,
        "truncated": len(values) > limit,
    }


@dataclass
class PQCVerificationEvent:
    """Event received from eBPF for PQC verification"""

    session_id: bytes  # 16 bytes
    signature: bytes  # Variable length ML-DSA-65 signature
    payload_hash: bytes  # SHA-256 of payload (32 bytes)
    pubkey_id: bytes  # 16 bytes - identifier for public key lookup
    timestamp: int  # Nanoseconds


@dataclass
class VerifiedSession:
    """A verified PQC session"""

    session_id: bytes
    expiration: int  # Unix timestamp
    verification_count: int = 0
    last_verified: float = 0


class PQCVerificationDaemon:
    """
    Userspace daemon for ML-DSA-65 signature verification.

    Offloads PQC verification from eBPF kernel space to userspace
    where liboqs can perform full CRYSTALS-Dilithium verification.
    """

    # Event format from eBPF ring buffer
    # struct pqc_event {
    #     __u8 session_id[16];
    #     __u8 signature[4627];  // ML-DSA-65 max signature size
    #     __u16 signature_len;
    #     __u8 payload_hash[32];
    #     __u8 pubkey_id[16];
    #     __u64 timestamp;
    # };
    EVENT_SIZE = 16 + 4627 + 2 + 32 + 16 + 8  # 4701 bytes

    # Session expiration time (1 hour in nanoseconds)
    SESSION_TTL_NS = 3600 * 1_000_000_000

    def __init__(
        self,
        bpf: Optional["BPF"] = None,  # Changed 'BPF' to string literal
        public_key_store: Optional[Dict[bytes, bytes]] = None,
        anomaly_callback: Optional[Callable[[str, Dict], None]] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """
        Initialize the PQC verification daemon.

        Args:
            bpf: BPF object with loaded XDP program (optional for testing)
            public_key_store: Dict mapping pubkey_id -> ML-DSA-65 public key
            anomaly_callback: Function to call on verification anomalies
        """
        self.bpf = bpf
        self.public_keys = public_key_store or {}
        self.anomaly_callback = anomaly_callback
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = PQC_VERIFICATION_DAEMON_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "causal_analysis", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        # Verified sessions cache
        self.verified_sessions: Dict[bytes, VerifiedSession] = {}

        # Statistics
        self.stats = {
            "events_received": 0,
            "verifications_success": 0,
            "verifications_failed": 0,
            "unknown_pubkey": 0,
            "expired_sessions": 0,
        }

        # ML-DSA-65 verifier
        if LIBOQS_AVAILABLE:
            self.sig = oqs.Signature("ML-DSA-65")
            logger.info("ML-DSA-65 verifier initialized via liboqs")
        else:
            self.sig = None
            logger.warning("Running in mock mode - no real PQC verification")

        # Thread pool for parallel verification
        self.executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="pqc-verify"
        )

        # Shutdown flag
        self.running = False

        # BPF maps
        self.pqc_events_ringbuf = None
        self.pqc_verified_sessions_map = None

        if self.bpf:
            self._init_bpf_maps()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize PQC verification EventBus: %s", exc)
            return None

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "pqc_verification_daemon_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local PQC verification daemon evidence, redacted "
                "selectors, hashes, counts, and bounded metadata; do not expose "
                "session IDs, signatures, payload hashes, public keys, map "
                "values, stdout, or stderr."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose PQC verification-daemon thinking state without task secrets."""

        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        read_only: bool = True,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(self, "source_agent", PQC_VERIFICATION_DAEMON_SERVICE_NAME)
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.pqc_verification_daemon",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:pqc_verification_daemon:{operation}",
            "service_name": source_agent,
            "layer": PQC_VERIFICATION_DAEMON_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "thinking": thinking,
            "output": _bounded_output_metadata(),
            "payloads_redacted": True,
            "claim_boundary": PQC_VERIFICATION_DAEMON_CLAIM_BOUNDARY,
        }
        if error is not None:
            payload["error"] = {
                "type": type(error).__name__,
                "message_hash": _hash_value(str(error)),
                "message_redacted": True,
            }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish PQC verification observation")
            return None

    def _init_bpf_maps(self):
        """Initialize BPF maps from loaded program"""
        op_start = time.monotonic()
        try:
            self.pqc_events_ringbuf = self.bpf.get_table("pqc_events")
            self.pqc_verified_sessions_map = self.bpf.get_table("pqc_verified_sessions")
            logger.info("PQC verification daemon BPF maps initialized")
            self._publish_observation(
                stage="pqc_verification_bpf_maps_initialized",
                operation="init_bpf_maps",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                parsed_summary={
                    "ring_buffer_available": self.pqc_events_ringbuf is not None,
                    "verified_session_map_available": (
                        self.pqc_verified_sessions_map is not None
                    ),
                },
                extra={
                    "map_name_hashes": _bounded_hashes(
                        ["pqc_events", "pqc_verified_sessions"]
                    ),
                    "map_names_redacted": True,
                },
            )
        except KeyError as e:
            logger.warning("PQC verification daemon BPF map not found")
            self._publish_observation(
                stage="pqc_verification_bpf_map_missing",
                operation="init_bpf_maps",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                error=e,
                parsed_summary={
                    "ring_buffer_available": self.pqc_events_ringbuf is not None,
                    "verified_session_map_available": (
                        self.pqc_verified_sessions_map is not None
                    ),
                },
                extra={
                    "map_name_hashes": _bounded_hashes(
                        ["pqc_events", "pqc_verified_sessions"]
                    ),
                    "map_names_redacted": True,
                },
            )

    def register_public_key(self, pubkey_id: bytes, public_key: bytes):
        """
        Register a peer's ML-DSA-65 public key.

        Args:
            pubkey_id: 16-byte identifier (e.g., hash of peer ID)
            public_key: ML-DSA-65 public key bytes
        """
        op_start = time.monotonic()
        if len(pubkey_id) != 16:
            self._publish_observation(
                stage="pqc_public_key_registration_invalid",
                operation="register_public_key",
                status="failure",
                source_mode="memory",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "registered": False,
                    "reason": "invalid_pubkey_id_length",
                    "pubkey_id_len": len(pubkey_id),
                    "public_key_len": len(public_key),
                },
                extra={
                    "pubkey_id_hash": _hash_value(pubkey_id),
                    "public_key_hash": _hash_value(public_key),
                    "pubkey_id_redacted": True,
                    "public_key_redacted": True,
                },
            )
            raise ValueError("pubkey_id must be 16 bytes")

        self.public_keys[pubkey_id] = public_key
        logger.info("Registered redacted PQC public key")
        self._publish_observation(
            stage="pqc_public_key_registered",
            operation="register_public_key",
            status="success",
            source_mode="memory",
            start=op_start,
            read_only=False,
            parsed_summary={
                "registered": True,
                "registered_pubkeys": len(self.public_keys),
                "public_key_len": len(public_key),
            },
            extra={
                "pubkey_id_hash": _hash_value(pubkey_id),
                "public_key_hash": _hash_value(public_key),
                "pubkey_id_redacted": True,
                "public_key_redacted": True,
            },
        )

    def verify_signature(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        """
        Verify ML-DSA-65 signature.

        Args:
            message: Message that was signed
            signature: ML-DSA-65 signature
            public_key: ML-DSA-65 public key

        Returns:
            True if signature is valid
        """
        op_start = time.monotonic()
        metadata = {
            "message_hash": _hash_value(message),
            "signature_hash": _hash_value(signature),
            "public_key_hash": _hash_value(public_key),
            "message_len": len(message),
            "signature_len": len(signature),
            "public_key_len": len(public_key),
            "message_redacted": True,
            "signature_redacted": True,
            "public_key_redacted": True,
        }
        if not LIBOQS_AVAILABLE or self.sig is None:
            # Mock verification - always succeed for testing
            logger.debug("Mock verification: accepting signature")
            self._publish_observation(
                stage="pqc_signature_mock_verified",
                operation="verify_signature",
                status="success",
                source_mode="mock",
                start=op_start,
                parsed_summary={"verified": True, "verification_mode": "mock"},
                extra=metadata,
            )
            return True

        try:
            is_valid = self.sig.verify(message, signature, public_key)
            self._publish_observation(
                stage="pqc_signature_verified",
                operation="verify_signature",
                status="success" if is_valid else "failure",
                source_mode="liboqs",
                start=op_start,
                parsed_summary={
                    "verified": bool(is_valid),
                    "verification_mode": "liboqs",
                },
                extra=metadata,
            )
            return is_valid
        except Exception as e:
            logger.error("Signature verification error: %s", type(e).__name__)
            self._publish_observation(
                stage="pqc_signature_verification_error",
                operation="verify_signature",
                status="failure",
                source_mode="liboqs",
                start=op_start,
                error=e,
                parsed_summary={"verified": False, "verification_mode": "liboqs"},
                extra=metadata,
            )
            return False

    def _process_event(self, cpu: int, data: bytes, size: int):
        """
        Process a single PQC verification event from ring buffer.

        Called by BCC's ring buffer callback mechanism.
        """
        op_start = time.monotonic()
        self.stats["events_received"] += 1

        try:
            # Parse event
            event = self._parse_event(data)
            if event is None:
                self._publish_observation(
                    stage="pqc_ring_event_parse_skipped",
                    operation="process_event",
                    status="failure",
                    source_mode="ring-buffer",
                    start=op_start,
                    parsed_summary={
                        "parsed": False,
                        "submitted": False,
                        "cpu": int(cpu),
                        "event_size": int(size),
                        "events_received": self.stats["events_received"],
                    },
                    extra={
                        "raw_event_hash": _hash_value(data),
                        "raw_event_redacted": True,
                    },
                )
                return

            # Submit to thread pool for async verification
            self.executor.submit(self._verify_event, event)
            self._publish_observation(
                stage="pqc_ring_event_submitted",
                operation="process_event",
                status="success",
                source_mode="ring-buffer",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "parsed": True,
                    "submitted": True,
                    "cpu": int(cpu),
                    "event_size": int(size),
                    "events_received": self.stats["events_received"],
                },
                extra={
                    "session_id_hash": _hash_value(event.session_id),
                    "pubkey_id_hash": _hash_value(event.pubkey_id),
                    "payload_hash_hash": _hash_value(event.payload_hash),
                    "signature_hash": _hash_value(event.signature),
                    "session_id_redacted": True,
                    "pubkey_id_redacted": True,
                    "payload_hash_redacted": True,
                    "signature_redacted": True,
                },
            )

        except Exception as e:
            logger.error("Error processing PQC ring event: %s", type(e).__name__)
            self._publish_observation(
                stage="pqc_ring_event_process_failed",
                operation="process_event",
                status="failure",
                source_mode="ring-buffer",
                start=op_start,
                error=e,
                parsed_summary={
                    "submitted": False,
                    "cpu": int(cpu),
                    "event_size": int(size),
                    "events_received": self.stats["events_received"],
                },
                extra={
                    "raw_event_hash": _hash_value(data),
                    "raw_event_redacted": True,
                },
            )

    def _parse_event(self, data: bytes) -> Optional[PQCVerificationEvent]:
        """Parse raw event bytes into PQCVerificationEvent"""
        op_start = time.monotonic()
        if len(data) < 16 + 2:  # Minimum: session_id + signature_len
            logger.warning("PQC ring event too short: %d bytes", len(data))
            self._publish_observation(
                stage="pqc_ring_event_too_short",
                operation="parse_event",
                status="failure",
                source_mode="ring-buffer",
                start=op_start,
                parsed_summary={"parsed": False, "event_size": len(data)},
                extra={
                    "raw_event_hash": _hash_value(data),
                    "raw_event_redacted": True,
                },
            )
            return None

        try:
            # Unpack header
            session_id = data[0:16]

            # Signature length at offset 16 + 4627
            sig_len_offset = 16 + 4627
            signature_len = struct.unpack(
                "<H", data[sig_len_offset : sig_len_offset + 2]
            )[0]

            # Signature (variable length, max 4627)
            signature = data[16 : 16 + signature_len]

            # Payload hash (32 bytes after signature_len)
            hash_offset = sig_len_offset + 2
            payload_hash = data[hash_offset : hash_offset + 32]

            # Pubkey ID (16 bytes after payload_hash)
            pubkey_offset = hash_offset + 32
            pubkey_id = data[pubkey_offset : pubkey_offset + 16]

            # Timestamp (8 bytes at end)
            ts_offset = pubkey_offset + 16
            timestamp = struct.unpack("<Q", data[ts_offset : ts_offset + 8])[0]

            self._publish_observation(
                stage="pqc_ring_event_parsed",
                operation="parse_event",
                status="success",
                source_mode="ring-buffer",
                start=op_start,
                parsed_summary={
                    "parsed": True,
                    "event_size": len(data),
                    "signature_len": int(signature_len),
                    "payload_hash_len": len(payload_hash),
                    "timestamp_present": bool(timestamp),
                },
                extra={
                    "session_id_hash": _hash_value(session_id),
                    "pubkey_id_hash": _hash_value(pubkey_id),
                    "payload_hash_hash": _hash_value(payload_hash),
                    "signature_hash": _hash_value(signature),
                    "session_id_redacted": True,
                    "pubkey_id_redacted": True,
                    "payload_hash_redacted": True,
                    "signature_redacted": True,
                },
            )
            return PQCVerificationEvent(
                session_id=session_id,
                signature=signature,
                payload_hash=payload_hash,
                pubkey_id=pubkey_id,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error("PQC ring event parsing error: %s", type(e).__name__)
            self._publish_observation(
                stage="pqc_ring_event_parse_failed",
                operation="parse_event",
                status="failure",
                source_mode="ring-buffer",
                start=op_start,
                error=e,
                parsed_summary={"parsed": False, "event_size": len(data)},
                extra={
                    "raw_event_hash": _hash_value(data),
                    "raw_event_redacted": True,
                },
            )
            return None

    def _verify_event(self, event: PQCVerificationEvent):
        """
        Verify a PQC event and update BPF map on success.

        This runs in a thread pool worker.
        """
        op_start = time.monotonic()
        session_id_hex = event.session_id.hex()
        pubkey_id_hex = event.pubkey_id.hex()

        logger.debug("Verifying redacted PQC session/public-key pair")
        metadata = {
            "session_id_hash": _hash_value(event.session_id),
            "pubkey_id_hash": _hash_value(event.pubkey_id),
            "payload_hash_hash": _hash_value(event.payload_hash),
            "signature_hash": _hash_value(event.signature),
            "session_id_redacted": True,
            "pubkey_id_redacted": True,
            "payload_hash_redacted": True,
            "signature_redacted": True,
        }

        # Look up public key
        public_key = self.public_keys.get(event.pubkey_id)
        if public_key is None:
            self.stats["unknown_pubkey"] += 1
            logger.warning("Unknown redacted PQC public key ID")
            self._publish_observation(
                stage="pqc_verification_unknown_pubkey",
                operation="verify_event",
                status="failure",
                source_mode="memory",
                start=op_start,
                parsed_summary={
                    "verified": False,
                    "reason": "unknown_pubkey",
                    "unknown_pubkey": self.stats["unknown_pubkey"],
                    "registered_pubkeys": len(self.public_keys),
                },
                extra=metadata,
            )

            # Report anomaly
            if self.anomaly_callback:
                self.anomaly_callback(
                    "unknown_pubkey",
                    {"session_id": session_id_hex, "pubkey_id": pubkey_id_hex},
                )
            return

        # Verify signature
        # The message that was signed is the payload hash
        is_valid = self.verify_signature(
            message=event.payload_hash, signature=event.signature, public_key=public_key
        )

        if is_valid:
            self.stats["verifications_success"] += 1
            logger.info("Signature verified for redacted PQC session")

            # Update verified sessions cache
            expiration = time.time_ns() + self.SESSION_TTL_NS

            if event.session_id in self.verified_sessions:
                self.verified_sessions[event.session_id].verification_count += 1
                self.verified_sessions[event.session_id].last_verified = time.time()
            else:
                self.verified_sessions[event.session_id] = VerifiedSession(
                    session_id=event.session_id,
                    expiration=expiration,
                    verification_count=1,
                    last_verified=time.time(),
                )

            # Update BPF map
            self._update_bpf_verified_session(event.session_id, expiration)
            self._publish_observation(
                stage="pqc_verification_succeeded",
                operation="verify_event",
                status="success",
                source_mode="liboqs" if LIBOQS_AVAILABLE else "mock",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "verified": True,
                    "verifications_success": self.stats["verifications_success"],
                    "active_sessions": len(self.verified_sessions),
                    "session_ttl_ns": self.SESSION_TTL_NS,
                },
                extra={
                    **metadata,
                    "expiration_hash": _hash_value(expiration),
                    "expiration_redacted": True,
                },
            )

        else:
            self.stats["verifications_failed"] += 1
            logger.warning("Signature verification failed for redacted PQC session")
            self._publish_observation(
                stage="pqc_verification_failed",
                operation="verify_event",
                status="failure",
                source_mode="liboqs" if LIBOQS_AVAILABLE else "mock",
                start=op_start,
                parsed_summary={
                    "verified": False,
                    "verifications_failed": self.stats["verifications_failed"],
                    "active_sessions": len(self.verified_sessions),
                },
                extra=metadata,
            )

            # Report anomaly
            if self.anomaly_callback:
                self.anomaly_callback(
                    "verification_failed",
                    {"session_id": session_id_hex, "pubkey_id": pubkey_id_hex},
                )

    def _update_bpf_verified_session(self, session_id: bytes, expiration: int):
        """Update BPF map with verified session"""
        op_start = time.monotonic()
        if self.pqc_verified_sessions_map is None:
            logger.debug("BPF map not available, skipping update")
            self._publish_observation(
                stage="pqc_verified_session_map_missing",
                operation="update_bpf_verified_session",
                status="success",
                source_mode="memory",
                start=op_start,
                parsed_summary={"updated": False, "reason": "map_uninitialized"},
                extra={
                    "session_id_hash": _hash_value(session_id),
                    "expiration_hash": _hash_value(expiration),
                    "session_id_redacted": True,
                    "expiration_redacted": True,
                },
            )
            return

        try:
            # Pack expiration as __u64
            exp_bytes = struct.pack("<Q", expiration)
            self.pqc_verified_sessions_map[session_id] = exp_bytes
            logger.debug("Updated verified-session BPF map for redacted session")
            self._publish_observation(
                stage="pqc_verified_session_map_updated",
                operation="update_bpf_verified_session",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={"updated": True, "expiration_bytes": len(exp_bytes)},
                extra={
                    "session_id_hash": _hash_value(session_id),
                    "expiration_hash": _hash_value(expiration),
                    "expiration_value_hash": _hash_value(exp_bytes),
                    "map_name_hash": _hash_value("pqc_verified_sessions"),
                    "session_id_redacted": True,
                    "expiration_redacted": True,
                    "map_name_redacted": True,
                },
            )
        except Exception as e:
            logger.error("Failed to update verified-session BPF map: %s", type(e).__name__)
            self._publish_observation(
                stage="pqc_verified_session_map_update_failed",
                operation="update_bpf_verified_session",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                error=e,
                parsed_summary={"updated": False},
                extra={
                    "session_id_hash": _hash_value(session_id),
                    "expiration_hash": _hash_value(expiration),
                    "map_name_hash": _hash_value("pqc_verified_sessions"),
                    "session_id_redacted": True,
                    "expiration_redacted": True,
                    "map_name_redacted": True,
                },
            )

    def cleanup_expired_sessions(self):
        """Remove expired sessions from cache and BPF map"""
        op_start = time.monotonic()
        now = time.time_ns()
        expired = []

        for session_id, session in self.verified_sessions.items():
            if session.expiration < now:
                expired.append(session_id)

        for session_id in expired:
            del self.verified_sessions[session_id]

            # Remove from BPF map
            if self.pqc_verified_sessions_map:
                try:
                    del self.pqc_verified_sessions_map[session_id]
                except KeyError:
                    self._publish_observation(
                        stage="pqc_verified_session_cleanup_key_missing",
                        operation="cleanup_expired_sessions",
                        status="success",
                        source_mode="bcc-map",
                        start=op_start,
                        read_only=False,
                        parsed_summary={"deleted": False, "reason": "key_missing"},
                        extra={
                            "session_id_hash": _hash_value(session_id),
                            "session_id_redacted": True,
                        },
                    )

        if expired:
            self.stats["expired_sessions"] += len(expired)
            logger.info("Cleaned up %d expired PQC sessions", len(expired))
        self._publish_observation(
            stage="pqc_expired_sessions_cleanup_completed",
            operation="cleanup_expired_sessions",
            status="success",
            source_mode="memory",
            start=op_start,
            read_only=False,
            parsed_summary={
                "expired_count": len(expired),
                "active_sessions": len(self.verified_sessions),
                "expired_sessions_total": self.stats["expired_sessions"],
                "map_available": self.pqc_verified_sessions_map is not None,
            },
            extra={
                "expired_session_hashes": _bounded_hashes(expired),
                "session_ids_redacted": True,
            },
        )

    def get_stats(self) -> Dict[str, int]:
        """Get daemon statistics"""
        op_start = time.monotonic()
        stats = {
            **self.stats,
            "active_sessions": len(self.verified_sessions),
            "registered_pubkeys": len(self.public_keys),
        }
        self._publish_observation(
            stage="pqc_verification_stats_read",
            operation="get_stats",
            status="success",
            source_mode="memory",
            start=op_start,
            parsed_summary=dict(stats),
            extra={
                "session_id_hashes": _bounded_hashes(list(self.verified_sessions.keys())),
                "pubkey_id_hashes": _bounded_hashes(list(self.public_keys.keys())),
                "session_ids_redacted": True,
                "pubkey_ids_redacted": True,
            },
        )
        return stats

    def start(self):
        """Start the daemon's main loop"""
        op_start = time.monotonic()
        if not BCC_AVAILABLE:
            logger.error("Cannot start daemon without BCC")
            self._publish_observation(
                stage="pqc_verification_start_bcc_unavailable",
                operation="start",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"started": False, "reason": "bcc_unavailable"},
            )
            return

        if self.pqc_events_ringbuf is None:
            logger.error("Ring buffer not initialized")
            self._publish_observation(
                stage="pqc_verification_start_no_ring_buffer",
                operation="start",
                status="failure",
                source_mode="ring-buffer",
                start=op_start,
                read_only=False,
                parsed_summary={"started": False, "reason": "ring_buffer_uninitialized"},
            )
            return

        self.running = True
        logger.info("PQC Verification Daemon starting...")

        # Register ring buffer callback
        self.pqc_events_ringbuf.open_ring_buffer(self._process_event)
        self._publish_observation(
            stage="pqc_verification_daemon_started",
            operation="start",
            status="success",
            source_mode="ring-buffer",
            start=op_start,
            read_only=False,
            parsed_summary={
                "started": True,
                "ring_buffer_opened": True,
                "cleanup_thread_enabled": True,
            },
        )

        # Cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        # Main event loop
        try:
            while self.running:
                self.pqc_events_ringbuf.ring_buffer_poll(timeout=1000)
        except KeyboardInterrupt:
            logger.info("Received interrupt, shutting down...")
        except Exception as exc:
            self._publish_observation(
                stage="pqc_verification_ring_buffer_poll_failed",
                operation="start",
                status="failure",
                source_mode="ring-buffer",
                start=op_start,
                read_only=False,
                error=exc,
                parsed_summary={"started": self.running, "poll_failed": True},
            )
            raise
        finally:
            self.stop()

    def _cleanup_loop(self):
        """Periodically clean up expired sessions"""
        while self.running:
            time.sleep(60)  # Every minute
            self.cleanup_expired_sessions()

    def stop(self):
        """Stop the daemon"""
        op_start = time.monotonic()
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("PQC Verification Daemon stopped")
        logger.info(f"Final stats: {self.get_stats()}")
        self._publish_observation(
            stage="pqc_verification_daemon_stopped",
            operation="stop",
            status="success",
            source_mode="memory",
            start=op_start,
            read_only=False,
            parsed_summary={
                "stopped": True,
                "active_sessions": len(self.verified_sessions),
                "registered_pubkeys": len(self.public_keys),
            },
        )


class MockPQCVerificationDaemon(PQCVerificationDaemon):
    """
    Mock daemon for testing without BCC/kernel support.

    Simulates the verification workflow for unit testing and development.
    """

    def __init__(self, **kwargs):
        # Remove bpf from kwargs if present
        kwargs.pop("bpf", None)
        super().__init__(bpf=None, **kwargs)

        self.pending_events = []
        self._mock_mode = True  # Force mock mode

    def verify_signature(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        """Mock verification - always returns True"""
        logger.debug("Mock verification: accepting signature")
        return True

    def submit_event(self, event: PQCVerificationEvent):
        """Submit event for verification (test helper)"""
        op_start = time.monotonic()
        self.pending_events.append(event)
        self._verify_event(event)
        self._publish_observation(
            stage="pqc_mock_event_submitted",
            operation="submit_event",
            status="success",
            source_mode="mock",
            start=op_start,
            read_only=False,
            parsed_summary={"submitted": True, "pending_events": len(self.pending_events)},
            extra={
                "session_id_hash": _hash_value(event.session_id),
                "pubkey_id_hash": _hash_value(event.pubkey_id),
                "payload_hash_hash": _hash_value(event.payload_hash),
                "signature_hash": _hash_value(event.signature),
                "session_id_redacted": True,
                "pubkey_id_redacted": True,
                "payload_hash_redacted": True,
                "signature_redacted": True,
            },
        )

    def start(self):
        """Start in mock mode"""
        op_start = time.monotonic()
        logger.info("Mock PQC Verification Daemon started")
        self.running = True
        self._publish_observation(
            stage="pqc_mock_daemon_started",
            operation="start",
            status="success",
            source_mode="mock",
            start=op_start,
            read_only=False,
            parsed_summary={"started": True},
        )

    def stop(self):
        """Stop mock daemon"""
        op_start = time.monotonic()
        self.running = False
        logger.info(f"Mock daemon stopped. Stats: {self.get_stats()}")
        self._publish_observation(
            stage="pqc_mock_daemon_stopped",
            operation="stop",
            status="success",
            source_mode="mock",
            start=op_start,
            read_only=False,
            parsed_summary={
                "stopped": True,
                "pending_events": len(self.pending_events),
                "active_sessions": len(self.verified_sessions),
            },
        )


def create_daemon_from_bpf(
    bpf: "BPF", pqc_gateway=None
) -> PQCVerificationDaemon:  # Changed 'BPF' to string literal
    """
    Factory function to create daemon from existing BPF object.

    Args:
        bpf: BPF object with loaded PQC XDP program
        pqc_gateway: Optional EBPFPQCGateway for public key registration

    Returns:
        Configured PQCVerificationDaemon
    """
    daemon = PQCVerificationDaemon(bpf=bpf)

    # Register public keys from gateway if available
    if pqc_gateway:
        for session_id, session in pqc_gateway.sessions.items():
            if session.dsa_public_key:
                # Use hash of peer_id as pubkey_id
                pubkey_id = hashlib.sha256(session.peer_id.encode()).digest()[:16]
                daemon.register_public_key(pubkey_id, session.dsa_public_key)

    return daemon


def main():
    """Main entry point for running daemon standalone"""
    import argparse

    parser = argparse.ArgumentParser(description="x0tta6bl4 PQC Verification Daemon")
    parser.add_argument("--interface", "-i", default="eth0", help="Network interface")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    parser.add_argument(
        "--stats-interval", type=int, default=30, help="Stats print interval"
    )

    args = parser.parse_args()

    if args.mock or not BCC_AVAILABLE:
        logger.info("Running in mock mode")
        daemon = MockPQCVerificationDaemon()

        # Add some test public keys
        test_pubkey_id = hashlib.sha256(b"test-peer").digest()[:16]
        daemon.register_public_key(test_pubkey_id, b"mock-public-key")

        daemon.start()

        # Simulate events for testing
        import secrets

        for i in range(5):
            event = PQCVerificationEvent(
                session_id=secrets.token_bytes(16),
                signature=secrets.token_bytes(100),  # Mock signature
                payload_hash=hashlib.sha256(f"test-payload-{i}".encode()).digest(),
                pubkey_id=test_pubkey_id,
                timestamp=time.time_ns(),
            )
            daemon.submit_event(event)
            time.sleep(0.5)

        print(f"Final stats: {daemon.get_stats()}")
        daemon.stop()

    else:
        # Real mode with BCC
        from .pqc_xdp_loader import PQCXDPLoader

        loader = PQCXDPLoader(interface=args.interface)
        daemon = create_daemon_from_bpf(loader.bpf, loader.pqc_gateway)

        # Setup signal handlers
        def signal_handler(sig, frame):
            daemon.stop()
            loader.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Stats printer
        def stats_printer():
            while daemon.running:
                time.sleep(args.stats_interval)
                stats = daemon.get_stats()
                logger.info(f"Stats: {stats}")

        stats_thread = threading.Thread(target=stats_printer, daemon=True)
        stats_thread.start()

        # Run daemon
        daemon.start()


if __name__ == "__main__":
    main()

