#!/usr/bin/env python3
"""
PQC XDP Loader for x0tta6bl4
Loads and manages XDP PQC verification programs with zero-trust security.

Integrates with EBPFPQCGateway for cryptographic session management.
"""

import logging
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

try:
    from bcc import BPF as _BCCBPF

    BPF: Optional[Any] = _BCCBPF
    BCC_AVAILABLE = True
except ImportError:
    BPF = None
    BCC_AVAILABLE = False

from ...security.ebpf_pqc_gateway import get_pqc_gateway
from .dataplane_logic_contract import DataplaneFormalState, DataplaneLogicContract
from .loader import EBPFLoader

logger = logging.getLogger(__name__)

PQC_XDP_LOADER_SERVICE_NAME = "pqc-xdp-loader"
PQC_XDP_LOADER_LAYER = "network_ebpf_pqc_xdp_loader_observed_state"
PQC_XDP_LOADER_CLAIM_BOUNDARY = (
    "Local PQC XDP loader evidence only. Events record BCC compile/load/map/attach "
    "attempts, map write/read counts, gateway sync outcomes, cleanup attempts, "
    "duration, and hashed selectors; they do not prove live kernel datapath "
    "enforcement, production traffic, remote peer identity, or cryptographic "
    "session validity beyond the local userspace operation result."
)

try:
    from prometheus_client import Counter

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore


class _NoopCounter:
    def inc(self, amount: float = 1.0) -> None:
        return


def _build_counter(name: str, description: str):
    if not PROMETHEUS_AVAILABLE or Counter is None:
        return _NoopCounter()
    try:
        return Counter(name, description)
    except Exception as exc:
        logger.debug("Prometheus counter %s unavailable: %s", name, exc)
        return _NoopCounter()


PQC_EBPF_SESSION_MAP_WRITES_TOTAL = _build_counter(
    "pqc_ebpf_session_map_writes_total",
    "Total pqc_sessions map writes performed by PQCXDPLoader",
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
    identity = service_event_identity(service_name=PQC_XDP_LOADER_SERVICE_NAME)
    return {
        "service_name": PQC_XDP_LOADER_SERVICE_NAME,
        "layer": PQC_XDP_LOADER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _key_hashes(keys: List[Any]) -> List[Optional[str]]:
    return [_hash_value(key) for key in keys]


def _safe_stat_summary(stats: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for key, value in stats.items():
        if isinstance(value, (bool, int, float)):
            summary[key] = value
        else:
            summary[key] = _hash_value(value)
    return summary


class PQCXDPLoader(EBPFLoader):
    """
    PQC-aware XDP Loader with zero-trust capabilities.

    Extends EBPFLoader with PQC session management and verification.
    """

    def __init__(
        self,
        interface: str = "eth0",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.interface = interface
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = PQC_XDP_LOADER_SERVICE_NAME
        self.logic_contract = DataplaneLogicContract(interface=interface)
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        if not BCC_AVAILABLE:
            self._publish_observation(
                stage="pqc_xdp_loader_bcc_unavailable",
                operation="initialize",
                status="failure",
                source_mode="bcc",
                start=time.monotonic(),
                parsed_summary={"bcc_available": False},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            raise RuntimeError("BCC required for PQC XDP loader")

        super().__init__(
            Path(__file__).parent / "kernel",
            event_bus=event_bus,
            event_project_root=event_project_root,
        )
        self.source_agent = PQC_XDP_LOADER_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        self._last_thinking_context = None

        self.pqc_gateway = get_pqc_gateway()
        self.pqc_sessions_map = None
        self.pqc_stats_map = None

        self.load_pqc_programs()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize PQC XDP loader EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            coach = AgentThinkingCoach(
                agent_id=getattr(self, "source_agent", PQC_XDP_LOADER_SERVICE_NAME),
                role="security",
                capabilities=("zero-trust", "monitoring"),
                extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
            )
            self.thinking_coach = coach
        return coach

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "pqc_xdp_loader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local PQC XDP loader evidence, redacted selectors, "
                "hashes, counts, formal proof fragments, and bounded metadata; "
                "do not expose interfaces, program text, session keys, peer IDs, "
                "stdout, or stderr."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose PQC XDP loader thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _logic_contract_or_default(self) -> DataplaneLogicContract:
        if not hasattr(self, "logic_contract") or self.logic_contract is None:
            self.logic_contract = DataplaneLogicContract(
                interface=getattr(self, "interface", "unknown")
            )
        return self.logic_contract

    def _redacted_dataplane_proof(self) -> Dict[str, Any]:
        proof = self._logic_contract_or_default().get_dataplane_proof_fragment()
        return {
            "schema": proof.get("schema"),
            "interface_hash": _hash_value(proof.get("interface")),
            "interface_redacted": True,
            "current_state": proof.get("current_state"),
            "violation_hashes": _key_hashes(proof.get("violations", [])),
            "violation_count": len(proof.get("violations", [])),
            "violations_redacted": True,
            "claim_boundary": proof.get("claim_boundary"),
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        returncode: Optional[int] = None,
        stdout: Optional[Any] = None,
        stderr: Optional[Any] = None,
        read_only: bool = True,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(self, "source_agent", PQC_XDP_LOADER_SERVICE_NAME)
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "interface_hash": _hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.pqc_xdp_loader",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:pqc_xdp_loader:{operation}",
            "service_name": source_agent,
            "layer": PQC_XDP_LOADER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "formal_dataplane_proof": self._redacted_dataplane_proof(),
            "parsed_summary": parsed_summary or {},
            "thinking": thinking,
            "output": _bounded_output_metadata(stdout, stderr),
            "payloads_redacted": True,
            "claim_boundary": PQC_XDP_LOADER_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish PQC XDP loader observation")
            return None

    def load_pqc_programs(self):
        """Load PQC XDP verification program"""
        op_start = time.monotonic()
        interface = getattr(self, "interface", "unknown")
        if not BCC_AVAILABLE:
            logger.warning(
                "BCC not available. Skipping BPF program loading in PQCXDPLoader."
            )
            self.bpf = None
            self.pqc_sessions_map = None
            self.pqc_stats_map = None
            self._publish_observation(
                stage="pqc_xdp_load_bcc_unavailable",
                operation="load_pqc_programs",
                status="failure",
                source_mode="bcc",
                start=op_start,
                parsed_summary={"loaded": False, "bcc_available": False},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            return

        program_path = self.programs_dir / "xdp_pqc_verify.c"
        program_metadata = {
            "interface_hash": _hash_value(interface),
            "program_path_hash": _hash_value(program_path),
            "program_dir_hash": _hash_value(self.programs_dir),
            "interface_redacted": True,
            "program_path_redacted": True,
        }

        if not program_path.exists():
            self._publish_observation(
                stage="pqc_xdp_program_missing",
                operation="load_pqc_programs",
                status="failure",
                source_mode="filesystem",
                start=op_start,
                parsed_summary={"loaded": False, "reason": "program_missing"},
                extra=program_metadata,
            )
            raise FileNotFoundError(f"PQC XDP program not found: {program_path}")

        with open(program_path, "r") as f:
            bpf_text = f.read()
        program_metadata.update(
            {
                "bpf_text_chars": len(bpf_text),
                "bpf_text_sha256": _hash_value(bpf_text),
            }
        )

        # Transition to COMPILING
        self.logic_contract.transition_to(DataplaneFormalState.COMPILING, {})
        if self.logic_contract.current_state == DataplaneFormalState.LOAD_FAILURE:
            return

        # Compile and load BPF program
        include_path = str(self.programs_dir)
        compile_start = time.monotonic()
        try:
            self.bpf = BPF(text=bpf_text, cflags=[f"-I{include_path}"])
        except Exception as exc:
            self.logic_contract.transition_to(
                DataplaneFormalState.LOAD_FAILURE, {"error": str(exc)}
            )
            self._publish_observation(
                stage="pqc_xdp_bpf_compile_failed",
                operation="bcc_compile",
                status="failure",
                source_mode="bcc",
                start=compile_start,
                error=exc,
                parsed_summary={"compiled": False},
                extra={
                    **program_metadata,
                    "cflags_count": 1,
                    "cflags_hash": _hash_value(f"-I{include_path}"),
                    "cflags_redacted": True,
                },
            )
            raise

        # Transition to STAGED
        self.logic_contract.transition_to(DataplaneFormalState.STAGED, {})

        self._publish_observation(
            stage="pqc_xdp_bpf_compile_succeeded",
            operation="bcc_compile",
            status="success",
            source_mode="bcc",
            start=compile_start,
            parsed_summary={"compiled": True},
            extra={
                **program_metadata,
                "cflags_count": 1,
                "cflags_hash": _hash_value(f"-I{include_path}"),
                "cflags_redacted": True,
            },
        )

        # Get PQC-specific maps
        maps_start = time.monotonic()
        try:
            self.pqc_sessions_map = self.bpf.get_table("pqc_sessions")
            self.pqc_stats_map = self.bpf.get_table("pqc_stats")
        except Exception as exc:
            self.logic_contract.transition_to(
                DataplaneFormalState.LOAD_FAILURE, {"error": str(exc)}
            )
            self._publish_observation(
                stage="pqc_xdp_map_lookup_failed",
                operation="get_bpf_tables",
                status="failure",
                source_mode="bcc",
                start=maps_start,
                error=exc,
                parsed_summary={"maps_loaded": False},
                extra={
                    **program_metadata,
                    "map_names_hash": _hash_value("pqc_sessions,pqc_stats"),
                    "map_names_redacted": True,
                },
            )
            raise
        self._publish_observation(
            stage="pqc_xdp_map_lookup_succeeded",
            operation="get_bpf_tables",
            status="success",
            source_mode="bcc",
            start=maps_start,
            parsed_summary={
                "maps_loaded": True,
                "sessions_map_present": self.pqc_sessions_map is not None,
                "stats_map_present": self.pqc_stats_map is not None,
            },
            extra={
                **program_metadata,
                "map_names_hash": _hash_value("pqc_sessions,pqc_stats"),
                "map_names_redacted": True,
            },
        )

        # Transition to ATTACHING (with D1 check)
        self.logic_contract.transition_to(
            DataplaneFormalState.ATTACHING, {"bcc_ready": self.bpf is not None}
        )
        if self.logic_contract.current_state == DataplaneFormalState.LOAD_FAILURE:
            return

        # Attach XDP program
        attach_start = time.monotonic()
        try:
            fn = self.bpf.load_func("xdp_pqc_verify_prog", BPF.XDP)
            self.bpf.attach_xdp(self.interface, fn, 0)
        except Exception as exc:
            self.logic_contract.transition_to(
                DataplaneFormalState.LOAD_FAILURE, {"error": str(exc)}
            )
            self._publish_observation(
                stage="pqc_xdp_attach_failed",
                operation="attach_xdp",
                status="failure",
                source_mode="bcc",
                start=attach_start,
                read_only=False,
                error=exc,
                parsed_summary={"attached": False, "xdp_flags": 0},
                extra={
                    **program_metadata,
                    "function_name_hash": _hash_value("xdp_pqc_verify_prog"),
                    "function_name_redacted": True,
                },
            )
            raise

        # Final transition to ATTACHED
        self.logic_contract.transition_to(
            DataplaneFormalState.ATTACHED, {"map_sync_failed": False}
        )

        self._publish_observation(
            stage="pqc_xdp_attach_succeeded",
            operation="attach_xdp",
            status="success",
            source_mode="bcc",
            start=attach_start,
            read_only=False,
            parsed_summary={"attached": True, "xdp_flags": 0},
            extra={
                **program_metadata,
                "function_name_hash": _hash_value("xdp_pqc_verify_prog"),
                "function_name_redacted": True,
            },
        )

        logger.info(f"✅ Loaded PQC XDP verification on interface {self.interface}")

    def update_pqc_sessions(self, sessions_data: Dict[str, Dict]):
        """
        Update PQC sessions map with current cryptographic sessions.

        Args:
            sessions_data: Dict[session_id, session_info]
        """
        op_start = time.monotonic()
        session_keys = list(sessions_data.keys())
        session_metadata = {
            "session_count": len(sessions_data),
            "session_key_hashes": _key_hashes(session_keys),
            "session_keys_redacted": True,
            "session_values_redacted": True,
        }

        if not self.pqc_sessions_map:
            logger.warning("pqc_sessions_map is not initialized. Skipping update.")
            self._publish_observation(
                stage="pqc_sessions_update_no_map",
                operation="update_pqc_sessions",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={"updated": False, "reason": "map_uninitialized"},
                extra=session_metadata,
            )
            return

        # Clear existing sessions
        existing_keys = list(self.pqc_sessions_map.keys())
        deleted_count = 0
        delete_failures = 0
        for key in existing_keys:
            try:
                del self.pqc_sessions_map[key]
                deleted_count += 1
            except Exception as exc:
                delete_failures += 1
                logger.error(
                    "Failed to delete redacted PQC session map key: %s",
                    type(exc).__name__,
                )

        logger.debug(
            "update_pqc_sessions called with %d redacted sessions.",
            len(sessions_data),
        )
        # Add current sessions
        write_count = 0
        write_failures = 0
        for session_id_bytes, session_info in sessions_data.items():
            logger.debug(
                "Processing redacted PQC session map entry hash=%s",
                _hash_value(session_id_bytes),
            )
            # In a real BCC implementation, we would pack this into a C types struct.
            # For now, we pass the dict/value relying on BCC or mock behavior.
            try:
                self.pqc_sessions_map[session_id_bytes] = session_info
                write_count += 1
            except Exception as e:
                write_failures += 1
                logger.error("Failed to update redacted PQC session map entry")
        if write_count:
            PQC_EBPF_SESSION_MAP_WRITES_TOTAL.inc(write_count)

        succeeded = write_failures == 0 and delete_failures == 0
        self._publish_observation(
            stage=(
                "pqc_sessions_update_succeeded"
                if succeeded
                else "pqc_sessions_update_partial_failure"
            ),
            operation="update_pqc_sessions",
            status="success" if succeeded else "failure",
            source_mode="bcc-map",
            start=op_start,
            read_only=False,
            parsed_summary={
                "updated": succeeded,
                "deleted_count": deleted_count,
                "delete_failures": delete_failures,
                "write_count": write_count,
                "write_failures": write_failures,
            },
            extra={
                **session_metadata,
                "existing_key_count": len(existing_keys),
                "existing_key_hashes": _key_hashes(existing_keys),
                "existing_keys_redacted": True,
            },
        )

    def get_pqc_stats(self) -> Dict[str, int]:
        """Get PQC verification statistics"""
        op_start = time.monotonic()
        if not self.pqc_stats_map:
            self._publish_observation(
                stage="pqc_stats_read_no_map",
                operation="get_pqc_stats",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                parsed_summary={
                    "stats_available": False,
                    "reason": "map_uninitialized",
                },
                extra={
                    "map_name_hash": _hash_value("pqc_stats"),
                    "map_name_redacted": True,
                },
            )
            return {}

        stats = {}
        missing_key = False
        try:
            stats["total_packets"] = self.pqc_stats_map[0] or 0
            stats["verified_packets"] = self.pqc_stats_map[1] or 0
            stats["failed_verification"] = self.pqc_stats_map[2] or 0
            stats["no_session"] = self.pqc_stats_map[3] or 0
            stats["expired_session"] = self.pqc_stats_map[4] or 0
            stats["decrypted_packets"] = self.pqc_stats_map[5] or 0
        except KeyError:
            missing_key = True

        self._publish_observation(
            stage=(
                "pqc_stats_read_partial" if missing_key else "pqc_stats_read_succeeded"
            ),
            operation="get_pqc_stats",
            status="success",
            source_mode="bcc-map",
            start=op_start,
            parsed_summary={
                "stats_available": True,
                "missing_key": missing_key,
                "stat_keys": sorted(stats.keys()),
                "stats": _safe_stat_summary(stats),
            },
            extra={
                "map_name_hash": _hash_value("pqc_stats"),
                "map_name_redacted": True,
            },
        )

        return stats

    def sync_with_gateway(self):
        """Sync eBPF maps with PQC gateway sessions"""
        op_start = time.monotonic()
        try:
            gateway_data = self.pqc_gateway.get_ebpf_map_data()
        except Exception as exc:
            self._publish_observation(
                stage="pqc_gateway_sync_read_failed",
                operation="sync_with_gateway",
                status="failure",
                source_mode="pqc-gateway",
                start=op_start,
                error=exc,
                parsed_summary={"synced": False},
            )
            raise

        logger.debug(
            "gateway_data received from PQC gateway with %d redacted entries.",
            len(gateway_data),
        )
        self._publish_observation(
            stage="pqc_gateway_sync_read_succeeded",
            operation="sync_with_gateway",
            status="success",
            source_mode="pqc-gateway",
            start=op_start,
            parsed_summary={
                "gateway_entries": len(gateway_data),
                "synced": False,
            },
            extra={
                "gateway_session_key_hashes": _key_hashes(list(gateway_data.keys())),
                "gateway_data_redacted": True,
            },
        )
        self.update_pqc_sessions(gateway_data)

    def create_pqc_session(self, peer_id: str) -> Optional[str]:
        """
        Create new PQC session and update eBPF maps.

        Returns:
            session_id if successful
        """
        op_start = time.monotonic()
        try:
            session = self.pqc_gateway.create_session(peer_id)
            self.sync_with_gateway()
            self._publish_observation(
                stage="pqc_session_create_succeeded",
                operation="create_pqc_session",
                status="success",
                source_mode="pqc-gateway",
                start=op_start,
                read_only=False,
                parsed_summary={"created": True},
                extra={
                    "peer_id_hash": _hash_value(peer_id),
                    "session_id_hash": _hash_value(session.session_id),
                    "peer_id_redacted": True,
                    "session_id_redacted": True,
                },
            )
            return session.session_id
        except Exception as e:
            self._publish_observation(
                stage="pqc_session_create_failed",
                operation="create_pqc_session",
                status="failure",
                source_mode="pqc-gateway",
                start=op_start,
                read_only=False,
                error=e,
                parsed_summary={"created": False},
                extra={
                    "peer_id_hash": _hash_value(peer_id),
                    "peer_id_redacted": True,
                },
            )
            logger.error("Failed to create redacted PQC session")
            return None

    def verify_pqc_packet(self, packet_data: bytes) -> bool:
        """
        Verify PQC packet (for testing/debugging).

        In production, this is done in XDP.
        """
        # This would implement userspace verification
        # For now, return True for testing
        self._publish_observation(
            stage="pqc_packet_verify_stubbed",
            operation="verify_pqc_packet",
            status="success",
            source_mode="userspace-stub",
            start=time.monotonic(),
            parsed_summary={"verified": True, "stubbed": True},
            extra={
                "packet_bytes": len(packet_data),
                "packet_sha256": _hash_value(packet_data),
                "packet_redacted": True,
            },
        )
        return True

    def cleanup(self):
        """Clean up PQC XDP programs"""
        op_start = time.monotonic()
        if self.bpf:
            try:
                self.bpf.remove_xdp(self.interface, 0)
                self.bpf.cleanup()
            except Exception as exc:
                self._publish_observation(
                    stage="pqc_xdp_cleanup_failed",
                    operation="cleanup",
                    status="failure",
                    source_mode="bcc",
                    start=op_start,
                    read_only=False,
                    error=exc,
                    parsed_summary={"cleanup": False, "xdp_removed": False},
                    extra={
                        "interface_hash": _hash_value(self.interface),
                        "interface_redacted": True,
                    },
                )
                raise
            self._publish_observation(
                stage="pqc_xdp_cleanup_succeeded",
                operation="cleanup",
                status="success",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"cleanup": True, "xdp_removed": True},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "interface_redacted": True,
                },
            )
        else:
            self._publish_observation(
                stage="pqc_xdp_cleanup_skipped_no_bpf",
                operation="cleanup",
                status="success",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"cleanup": True, "reason": "bpf_uninitialized"},
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "interface_redacted": True,
                },
            )
        logger.info("Cleaned up PQC XDP programs")


# Integration with mesh networking
def integrate_pqc_with_mesh(mesh_router, pqc_loader: PQCXDPLoader):
    """
    Integrate PQC verification with mesh routing.

    Args:
        mesh_router: MeshRouter instance
        pqc_loader: PQCXDPLoader instance
    """
    # Monkey patch mesh router to use PQC
    original_send = mesh_router._send_packet

    def pqc_send_packet(self, packet, destination):
        # Encrypt packet with PQC before sending
        session_id = pqc_loader.create_pqc_session(destination.node_id)
        if session_id:
            encrypted = pqc_loader.pqc_gateway.encrypt_payload(session_id, packet)
            if encrypted:
                return original_send(encrypted, destination)
        return original_send(packet, destination)

    mesh_router._send_packet = pqc_send_packet.__get__(
        mesh_router, mesh_router.__class__
    )

    logger.info("Integrated PQC encryption with mesh routing")


# Prometheus metrics integration
def setup_pqc_metrics(pqc_loader: PQCXDPLoader):
    """Set up Prometheus metrics for PQC operations"""
    try:
        from prometheus_client import Counter, Gauge

        PQC_SESSIONS = Gauge("pqc_active_sessions", "Number of active PQC sessions")
        PQC_VERIFICATION_RATE = Gauge(
            "pqc_verification_rate", "PQC packet verification rate"
        )
        PQC_FAILED_VERIFICATIONS = Counter(
            "pqc_failed_verifications_total", "Total failed PQC verifications"
        )

        def update_metrics():
            stats = pqc_loader.get_pqc_stats()
            total = stats.get("total_packets", 0)
            verified = stats.get("verified_packets", 0)

            PQC_SESSIONS.set(len(pqc_loader.pqc_gateway.sessions))
            if total > 0:
                PQC_VERIFICATION_RATE.set(verified / total)
            PQC_FAILED_VERIFICATIONS.inc(stats.get("failed_verification", 0))

        # Update every 30 seconds
        import threading

        def metrics_loop():
            while True:
                update_metrics()
                time.sleep(30)

        thread = threading.Thread(target=metrics_loop, daemon=True)
        thread.start()

        logger.info("PQC Prometheus metrics enabled")

    except ImportError:
        logger.warning("prometheus_client not available, PQC metrics disabled")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="x0tta6bl4 PQC XDP Loader")
    parser.add_argument("--interface", "-i", default="eth0", help="Network interface")
    parser.add_argument("--test-session", help="Test PQC session creation")

    args = parser.parse_args()

    loader = PQCXDPLoader(args.interface)

    if args.test_session:
        session_id = loader.create_pqc_session(args.test_session)
        if session_id:
            print(f"Created PQC session: {session_id}")
            stats = loader.get_pqc_stats()
            print(f"PQC stats: {stats}")
        else:
            print("Failed to create session")
    else:
        # Run sync loop
        try:
            while True:
                loader.sync_with_gateway()
                stats = loader.get_pqc_stats()
                print(f"PQC Stats: {stats}")
                time.sleep(10)
        except KeyboardInterrupt:
            loader.cleanup()
