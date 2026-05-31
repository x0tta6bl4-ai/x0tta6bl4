#!/usr/bin/env python3
"""
Rate Limiter Manager for x0tta6bl4 mesh network.

Provides both eBPF-based and software fallback rate limiting.
eBPF is used when available (requires root + BCC), otherwise
a Python-based token bucket implementation is used.
"""
import ctypes
import hashlib
import logging
import os
import threading
import time
from typing import Any, Dict, List, Mapping, Optional

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME = "ebpf-rate-limiter-manager"
EBPF_RATE_LIMITER_MANAGER_LAYER = "network_ebpf_rate_limiter_observed_state"
EBPF_RATE_LIMITER_MANAGER_CLAIM_BOUNDARY = (
    "Local eBPF/software rate limiter evidence only. Events record BCC "
    "availability, root checks, BPF source load/compile attempts, configuration "
    "map mutations, software fallback transitions, PQC session-key sync counts, "
    "rate-limit checks, and stats reads with hashed peer/interface/map selectors; "
    "they do not prove production traffic shaping, remote peer identity, or TC/XDP "
    "datapath enforcement beyond the local userspace operation result."
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
    identity = service_event_identity(
        service_name=EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME
    )
    return {
        "service_name": EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME,
        "layer": EBPF_RATE_LIMITER_MANAGER_LAYER,
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


# Try to import Prometheus client (optional)
try:
    from prometheus_client import Counter

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore


class _NoopCounter:
    """Fallback counter when prometheus_client is unavailable."""

    def inc(self, amount: float = 1.0) -> None:
        return


def _build_counter(name: str, description: str):
    """Create a Prometheus counter with graceful fallback."""
    if not PROMETHEUS_AVAILABLE or Counter is None:
        return _NoopCounter()
    try:
        return Counter(name, description)
    except Exception as exc:
        logger.debug("Prometheus counter %s unavailable: %s", name, exc)
        return _NoopCounter()


PQC_PEER_SESSION_KEYS_SYNCED_TOTAL = _build_counter(
    "pqc_peer_session_keys_synced_total",
    "Total peer session keys synced into eBPF/software rate limiter state",
)
PQC_PEER_SESSION_KEY_MISS_TOTAL = _build_counter(
    "pqc_peer_session_key_miss_total",
    "Total packets denied due to missing peer PQC session key",
)

# Try to import BCC for eBPF support
try:
    from bcc import BPF
    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    BPF = None  # type: ignore
    logger.warning("BCC not available - using software fallback rate limiter")


class SoftwareRateLimiter:
    """
    Software-based token bucket rate limiter.
    
    Provides equivalent functionality to eBPF rate limiter when
    eBPF is not available (no root, BCC not installed, etc).
    
    Uses token bucket algorithm:
    - Tokens are added at a constant rate (bytes_per_sec)
    - Packets consume tokens equal to their size
    - If insufficient tokens, packet is "dropped" (simulated)
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._tokens: float = 0.0
        self._last_time: float = time.time()
        self._bytes_per_sec: int = 0  # 0 = unlimited
        self._dropped_packets: int = 0
        self._total_packets: int = 0
    
    def set_limit(self, bytes_per_sec: int) -> None:
        """Set bandwidth limit. 0 = unlimited."""
        with self._lock:
            self._bytes_per_sec = bytes_per_sec
            # Start with full bucket
            if bytes_per_sec > 0:
                self._tokens = float(bytes_per_sec)
            else:
                self._tokens = float('inf')
            self._last_time = time.time()
        
        limit_kbps = bytes_per_sec * 8 / 1024 if bytes_per_sec > 0 else float('inf')
        logger.info(f"Software rate limit set to {bytes_per_sec} bytes/sec ({limit_kbps:.1f} Kbps)")
    
    def apply_soft_lock(self) -> None:
        """Apply soft-lock: limit to 64 Kbps."""
        # 64 Kbps = 64 * 1024 / 8 = 8192 bytes/sec
        self.set_limit(64 * 1024 // 8)
    
    def check_and_consume(self, packet_size: int) -> bool:
        """
        Check if packet can be sent and consume tokens if allowed.
        
        Returns:
            True if packet allowed (tokens consumed)
            False if packet would be dropped (rate limit exceeded)
        """
        with self._lock:
            self._total_packets += 1
            
            if self._bytes_per_sec == 0:
                # Unlimited
                return True
            
            # Add tokens based on elapsed time
            now = time.time()
            elapsed = now - self._last_time
            self._last_time = now
            
            # Add tokens: rate * elapsed_time
            self._tokens += self._bytes_per_sec * elapsed
            
            # Cap tokens at max bucket size
            if self._tokens > self._bytes_per_sec:
                self._tokens = float(self._bytes_per_sec)
            
            # Check if we have enough tokens
            if self._tokens >= packet_size:
                self._tokens -= packet_size
                return True
            else:
                self._dropped_packets += 1
                return False
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        with self._lock:
            drop_rate = self._dropped_packets / max(self._total_packets, 1)
            return {
                "bytes_per_sec": self._bytes_per_sec,
                "current_tokens": self._tokens,
                "total_packets": self._total_packets,
                "dropped_packets": self._dropped_packets,
                "drop_rate": drop_rate,
                "mode": "software"
            }


class RateLimiterManager:
    """
    Rate Limiter Manager with eBPF fallback to software implementation.
    
    Attempts to use eBPF for high-performance rate limiting, falls back
    to software implementation when eBPF is unavailable.
    """
    
    def __init__(
        self,
        interface: str = "singbox_tun",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.interface = interface
        self.bpf: Optional[BPF] = None
        self._software_limiter: Optional[SoftwareRateLimiter] = None
        self._using_software_fallback: bool = False
        self._peer_session_keys: Dict[str, bytes] = {}
        self._pqc_session_map_writes: int = 0
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME
        
        self._init_eBPF_or_fallback()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF rate limiter EventBus: %s", exc)
            return None

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        read_only: bool = True,
        returncode: Optional[int] = None,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(
            self, "source_agent", EBPF_RATE_LIMITER_MANAGER_SERVICE_NAME
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.rate_limiter_manager",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:rate_limiter_manager:{operation}",
            "service_name": source_agent,
            "layer": EBPF_RATE_LIMITER_MANAGER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "output": _bounded_output_metadata(),
            "payloads_redacted": True,
            "claim_boundary": EBPF_RATE_LIMITER_MANAGER_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish eBPF rate limiter observation")
            return None

    def _ensure_pqc_state(self) -> None:
        """
        Backward-compatible lazy init for tests that bypass __init__ via __new__.
        """
        if not hasattr(self, "_peer_session_keys"):
            self._peer_session_keys = {}
        if not hasattr(self, "_pqc_session_map_writes"):
            self._pqc_session_map_writes = 0

    @staticmethod
    def _normalize_session_key(raw_key: Any) -> Optional[bytes]:
        """Normalize incoming session key representation to bytes."""
        if isinstance(raw_key, (bytes, bytearray, memoryview)):
            key_bytes = bytes(raw_key)
        elif isinstance(raw_key, str):
            cleaned = raw_key[2:] if raw_key.startswith("0x") else raw_key
            try:
                key_bytes = bytes.fromhex(cleaned)
            except ValueError:
                return None
        else:
            return None

        # 16 bytes minimum to support fast-path MAC/session key use-cases.
        if len(key_bytes) < 16:
            return None
        return key_bytes
    
    def _init_eBPF_or_fallback(self) -> None:
        """Initialize eBPF or fall back to software implementation."""
        op_start = time.monotonic()
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, using software rate limiter")
            self._publish_observation(
                stage="rate_limiter_bcc_unavailable",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"bcc_available": False, "fallback": True},
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="bcc_unavailable")
            return
            
        try:
            # Check if we have root privileges
            if os.geteuid() != 0:
                logger.warning("Not running as root, using software rate limiter")
                self._publish_observation(
                    stage="rate_limiter_root_required",
                    operation="init_ebpf_or_fallback",
                    status="failure",
                    source_mode="process",
                    start=op_start,
                    read_only=False,
                    parsed_summary={"root_required": True, "fallback": True},
                    extra={
                        "interface_hash": _hash_value(getattr(self, "interface", "")),
                        "interface_redacted": True,
                    },
                )
                self._enable_software_fallback(reason="not_root")
                return
                
            program_path = "src/network/ebpf/kernel/rate_limiter.c"
            with open(program_path, "r") as f:
                program_text = f.read()
            self._publish_observation(
                stage="rate_limiter_program_text_loaded",
                operation="init_ebpf_or_fallback",
                status="success",
                source_mode="filesystem",
                start=op_start,
                parsed_summary={"program_source": "file"},
                extra={
                    "program_path_hash": _hash_value(program_path),
                    "program_text_chars": len(program_text),
                    "program_text_sha256": _hash_value(program_text),
                    "program_path_redacted": True,
                },
            )
            self.bpf = BPF(text=program_text)
            
            # Attach to egress using TC (Traffic Control)
            self.fn = self.bpf.load_func("handle_egress", BPF.SCHED_CLS)
            logger.info("eBPF rate limiter loaded for redacted interface")
            self._publish_observation(
                stage="rate_limiter_bpf_load_succeeded",
                operation="init_ebpf_or_fallback",
                status="success",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "loaded": True,
                    "function_loaded": True,
                    "tc_attach_performed": False,
                },
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "program_path_hash": _hash_value(program_path),
                    "function_name_hash": _hash_value("handle_egress"),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                    "function_name_redacted": True,
                },
            )
            
        except PermissionError as e:
            logger.warning("Permission denied for eBPF, using software fallback")
            self._publish_observation(
                stage="rate_limiter_bpf_permission_denied",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                error=e,
                parsed_summary={"loaded": False, "fallback": True},
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="permission_denied")
        except FileNotFoundError as e:
            logger.warning("eBPF program file not found, using software fallback")
            self._publish_observation(
                stage="rate_limiter_program_text_missing",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="filesystem",
                start=op_start,
                read_only=False,
                error=e,
                parsed_summary={"loaded": False, "fallback": True},
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "program_path_hash": _hash_value(
                        "src/network/ebpf/kernel/rate_limiter.c"
                    ),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                },
            )
            self._enable_software_fallback(reason="program_missing")
        except Exception as e:
            logger.warning("Failed to load eBPF rate limiter, using software fallback")
            self._publish_observation(
                stage="rate_limiter_bpf_load_failed",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                error=e,
                parsed_summary={"loaded": False, "fallback": True},
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="bpf_load_failed")
    
    def _enable_software_fallback(self, reason: str = "unspecified") -> None:
        """Enable software rate limiter fallback."""
        op_start = time.monotonic()
        self._using_software_fallback = True
        self._software_limiter = SoftwareRateLimiter()
        self._publish_observation(
            stage="rate_limiter_software_fallback_enabled",
            operation="enable_software_fallback",
            status="success",
            source_mode="software",
            start=op_start,
            read_only=False,
            parsed_summary={"fallback": True, "reason": reason},
            extra={
                "interface_hash": _hash_value(getattr(self, "interface", "")),
                "interface_redacted": True,
            },
        )
        logger.info("Software rate limiter fallback enabled")

    def sync_peer_session_keys(self, peer_session_keys: Mapping[str, Any]) -> int:
        """
        Sync peer session keys from PQC KEM state (e.g. /mesh/kem/session).

        Args:
            peer_session_keys: Mapping peer_id -> session key bytes (or hex string)

        Returns:
            Number of accepted peer session keys.
        """
        op_start = time.monotonic()
        self._ensure_pqc_state()
        normalized: Dict[str, bytes] = {}
        rejected_peer_ids: List[str] = []
        for peer_id, raw_key in peer_session_keys.items():
            key_bytes = self._normalize_session_key(raw_key)
            if key_bytes is None:
                logger.warning("Skipping invalid session key for redacted peer")
                rejected_peer_ids.append(str(peer_id))
                continue
            normalized[str(peer_id)] = key_bytes

        self._peer_session_keys = normalized
        writes = len(normalized)
        self._pqc_session_map_writes += writes
        if writes:
            PQC_PEER_SESSION_KEYS_SYNCED_TOTAL.inc(writes)

        logger.info(
            "Synced %d peer PQC session keys into rate limiter state (mode=%s)",
            writes,
            "software" if self._using_software_fallback else "ebpf",
        )
        accepted_peer_ids = list(normalized.keys())
        self._publish_observation(
            stage="rate_limiter_peer_session_keys_synced",
            operation="sync_peer_session_keys",
            status="success",
            source_mode="software" if self._using_software_fallback else "ebpf",
            start=op_start,
            read_only=False,
            parsed_summary={
                "input_count": len(peer_session_keys),
                "accepted_count": writes,
                "rejected_count": len(rejected_peer_ids),
                "total_loaded": len(self._peer_session_keys),
                "pqc_session_map_writes": self._pqc_session_map_writes,
            },
            extra={
                "accepted_peer_hashes": _bounded_hashes(accepted_peer_ids),
                "rejected_peer_hashes": _bounded_hashes(rejected_peer_ids),
                "session_key_hashes": _bounded_hashes(list(normalized.values())),
                "peer_ids_redacted": True,
                "session_keys_redacted": True,
            },
        )
        return writes

    def has_peer_session_key(self, peer_id: str) -> bool:
        """Check whether a peer has an active PQC session key."""
        op_start = time.monotonic()
        self._ensure_pqc_state()
        present = peer_id in self._peer_session_keys
        self._publish_observation(
            stage="rate_limiter_peer_session_key_checked",
            operation="has_peer_session_key",
            status="success",
            source_mode="memory",
            start=op_start,
            parsed_summary={
                "present": present,
                "peer_session_keys_loaded": len(self._peer_session_keys),
            },
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "peer_id_redacted": True,
            },
        )
        return present

    def get_peer_session_key(self, peer_id: str) -> Optional[bytes]:
        """Return peer session key bytes if present."""
        op_start = time.monotonic()
        self._ensure_pqc_state()
        key = self._peer_session_keys.get(peer_id)
        self._publish_observation(
            stage="rate_limiter_peer_session_key_read",
            operation="get_peer_session_key",
            status="success",
            source_mode="memory",
            start=op_start,
            parsed_summary={
                "present": key is not None,
                "peer_session_keys_loaded": len(self._peer_session_keys),
            },
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "session_key_hash": _hash_value(key),
                "peer_id_redacted": True,
                "session_key_redacted": True,
            },
        )
        return key
    
    @property
    def is_using_software_fallback(self) -> bool:
        """Check if using software fallback."""
        return self._using_software_fallback
    
    def set_limit(self, bytes_per_sec: int) -> None:
        """
        Set bandwidth limit. 0 = unlimited.
        
        Args:
            bytes_per_sec: Maximum bytes per second (0 = unlimited)
        """
        op_start = time.monotonic()
        if self._using_software_fallback:
            if self._software_limiter:
                self._software_limiter.set_limit(bytes_per_sec)
                self._publish_observation(
                    stage="rate_limiter_set_limit_software_succeeded",
                    operation="set_limit",
                    status="success",
                    source_mode="software",
                    start=op_start,
                    read_only=False,
                    parsed_summary={
                        "limit_set": True,
                        "bytes_per_sec": int(bytes_per_sec),
                        "mode": "software",
                    },
                    extra={
                        "interface_hash": _hash_value(getattr(self, "interface", "")),
                        "interface_redacted": True,
                    },
                )
            return
            
        if not self.bpf:
            logger.warning("eBPF not initialized, enabling software fallback")
            self._publish_observation(
                stage="rate_limiter_set_limit_no_bpf",
                operation="set_limit",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "limit_set": False,
                    "fallback": True,
                    "bytes_per_sec": int(bytes_per_sec),
                },
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="set_limit_no_bpf")
            if self._software_limiter:
                self._software_limiter.set_limit(bytes_per_sec)
                self._publish_observation(
                    stage="rate_limiter_set_limit_software_succeeded",
                    operation="set_limit",
                    status="success",
                    source_mode="software",
                    start=op_start,
                    read_only=False,
                    parsed_summary={
                        "limit_set": True,
                        "bytes_per_sec": int(bytes_per_sec),
                        "mode": "software",
                    },
                    extra={
                        "interface_hash": _hash_value(getattr(self, "interface", "")),
                        "interface_redacted": True,
                    },
                )
            return
        
        # eBPF implementation
        try:
            config_map = self.bpf["limit_config"]
            key = ctypes.c_uint32(0)

            class Config(ctypes.Structure):
                _fields_ = [
                    ("max_bytes_per_sec", ctypes.c_uint64),
                    ("last_time", ctypes.c_uint64),
                    ("tokens", ctypes.c_uint64)
                ]

            cfg = Config()
            cfg.max_bytes_per_sec = ctypes.c_uint64(bytes_per_sec)
            cfg.last_time = ctypes.c_uint64(time.time_ns())
            cfg.tokens = ctypes.c_uint64(bytes_per_sec)  # Start with full bucket

            config_map[key] = cfg

            limit_kb = bytes_per_sec / 1024 if bytes_per_sec > 0 else float('inf')
            logger.info(
                "Bandwidth limit for redacted interface set to %.1f KB/s",
                limit_kb,
            )
            self._publish_observation(
                stage="rate_limiter_config_map_updated",
                operation="set_limit",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "limit_set": True,
                    "bytes_per_sec": int(bytes_per_sec),
                    "mode": "ebpf",
                },
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "map_name_hash": _hash_value("limit_config"),
                    "map_key_hash": _hash_value(0),
                    "interface_redacted": True,
                    "map_name_redacted": True,
                    "map_key_redacted": True,
                },
            )
        except Exception as exc:
            self._publish_observation(
                stage="rate_limiter_config_map_update_failed",
                operation="set_limit",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                error=exc,
                parsed_summary={
                    "limit_set": False,
                    "bytes_per_sec": int(bytes_per_sec),
                    "mode": "ebpf",
                },
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "map_name_hash": _hash_value("limit_config"),
                    "map_key_hash": _hash_value(0),
                    "interface_redacted": True,
                    "map_name_redacted": True,
                    "map_key_redacted": True,
                },
            )
            raise
    
    def apply_soft_lock(self) -> None:
        """
        Apply soft-lock: degrade service to 64 Kbps.
        
        This is used when subscription is overdue - limits bandwidth
        to encourage renewal while allowing basic connectivity.
        """
        # 64 Kbps = 64 * 1024 / 8 = 8192 bytes/sec
        # NOT: 64 * 1024 // 8 * 1024 (which equals 8 MB/s)
        op_start = time.monotonic()
        soft_limit = 64 * 1024 // 8  # = 8192 bytes/sec
        self.set_limit(soft_limit)
        self._publish_observation(
            stage="rate_limiter_soft_lock_applied",
            operation="apply_soft_lock",
            status="success",
            source_mode="software" if self._using_software_fallback else "ebpf",
            start=op_start,
            read_only=False,
            parsed_summary={"soft_lock": True, "bytes_per_sec": soft_limit},
            extra={
                "interface_hash": _hash_value(getattr(self, "interface", "")),
                "interface_redacted": True,
            },
        )
        logger.warning("Soft-lock applied: limited to %d bytes/sec (64 Kbps)", soft_limit)
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        op_start = time.monotonic()
        self._ensure_pqc_state()
        if self._using_software_fallback and self._software_limiter:
            stats = self._software_limiter.get_stats()
        else:
            stats = {
                "mode": "ebpf",
                "interface": self.interface,
                "initialized": self.bpf is not None,
            }

        stats.update(
            {
                "peer_session_keys_loaded": len(self._peer_session_keys),
                "pqc_session_map_writes": self._pqc_session_map_writes,
            }
        )
        self._publish_observation(
            stage="rate_limiter_stats_read",
            operation="get_stats",
            status="success",
            source_mode="software" if self._using_software_fallback else "ebpf",
            start=op_start,
            parsed_summary={
                "mode": stats.get("mode"),
                "initialized": bool(stats.get("initialized", self._software_limiter)),
                "peer_session_keys_loaded": len(self._peer_session_keys),
                "pqc_session_map_writes": self._pqc_session_map_writes,
                "total_packets": stats.get("total_packets"),
                "dropped_packets": stats.get("dropped_packets"),
                "drop_rate": stats.get("drop_rate"),
            },
            extra={
                "interface_hash": _hash_value(getattr(self, "interface", "")),
                "peer_id_hashes": _bounded_hashes(list(self._peer_session_keys.keys())),
                "interface_redacted": True,
                "peer_ids_redacted": True,
            },
        )
        return stats
    
    def check_rate_limit(
        self,
        packet_size: int = 64,
        peer_id: Optional[str] = None,
        require_pqc_session: bool = False,
    ) -> bool:
        """
        Check if packet would be rate limited (software mode only).
        
        In eBPF mode, this check is done by the kernel.
        In software mode, this allows pre-check before sending.
        
        Args:
            packet_size: Size of packet in bytes
            peer_id: Optional peer identifier for PQC session-key lookup
            require_pqc_session: If True, deny packets without peer session key
            
        Returns:
            True if packet allowed, False if would be dropped
        """
        op_start = time.monotonic()
        if require_pqc_session:
            self._ensure_pqc_state()
            if not peer_id or not self.has_peer_session_key(peer_id):
                PQC_PEER_SESSION_KEY_MISS_TOTAL.inc()
                logger.warning("Dropping packet due to missing redacted PQC session key")
                self._publish_observation(
                    stage="rate_limiter_pqc_session_key_missing",
                    operation="check_rate_limit",
                    status="failure",
                    source_mode="software" if self._using_software_fallback else "ebpf",
                    start=op_start,
                    read_only=False,
                    parsed_summary={
                        "allowed": False,
                        "packet_size": int(packet_size),
                        "require_pqc_session": True,
                        "reason": "missing_pqc_session_key",
                    },
                    extra={
                        "peer_id_hash": _hash_value(peer_id),
                        "peer_id_redacted": True,
                    },
                )
                return False

        if self._using_software_fallback and self._software_limiter:
            allowed = self._software_limiter.check_and_consume(packet_size)
            self._publish_observation(
                stage="rate_limiter_check_software_completed",
                operation="check_rate_limit",
                status="success" if allowed else "failure",
                source_mode="software",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "allowed": allowed,
                    "packet_size": int(packet_size),
                    "require_pqc_session": bool(require_pqc_session),
                },
                extra={
                    "peer_id_hash": _hash_value(peer_id),
                    "peer_id_redacted": True,
                },
            )
            return allowed
        
        # eBPF mode: kernel handles this
        self._publish_observation(
            stage="rate_limiter_check_ebpf_delegated",
            operation="check_rate_limit",
            status="success",
            source_mode="ebpf",
            start=op_start,
            parsed_summary={
                "allowed": True,
                "packet_size": int(packet_size),
                "require_pqc_session": bool(require_pqc_session),
                "kernel_handles_rate_limit": True,
            },
            extra={
                "peer_id_hash": _hash_value(peer_id),
                "peer_id_redacted": True,
            },
        )
        return True
