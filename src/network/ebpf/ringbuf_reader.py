"""
Ring Buffer Reader for eBPF Events

High-throughput reader for eBPF ring buffer events.
Supports both ring buffer and perf event output.
"""
from __future__ import annotations

import hashlib
import logging
import struct
import subprocess
import time
from typing import Any, Callable, Dict, Optional

from src.coordination.events import EventBus, EventType
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity
from src.core.security.subprocess_validator import safe_run

logger = logging.getLogger(__name__)

try:
    from bcc import BPF, PerfSWConfig, PerfType

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    logger.warning("bcc not available, ring buffer reading will be limited")

EBPF_RINGBUF_READER_SERVICE_NAME = "ebpf-ringbuf-reader"
EBPF_RINGBUF_READER_LAYER = "network_ebpf_ringbuf_observed_state"
EBPF_RINGBUF_READER_CLAIM_BOUNDARY = (
    "Local eBPF ring/perf event reader evidence only. Events record map existence "
    "checks, BCC availability, reader lifecycle, parse/handler failures, duration, "
    "and bounded output hashes with redacted map/event selectors; they do not prove "
    "production traffic, packet forwarding, or attached kernel program correctness."
)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _sha256_text(str(value))


def _bounded_output_metadata(
    stdout: Optional[str],
    stderr: Optional[str],
) -> Dict[str, Any]:
    safe_stdout = stdout or ""
    safe_stderr = stderr or ""
    return {
        "stdout_chars": len(safe_stdout),
        "stderr_chars": len(safe_stderr),
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "output_bounded": True,
        "output_redacted": True,
    }


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_RINGBUF_READER_SERVICE_NAME)
    return {
        "service_name": EBPF_RINGBUF_READER_SERVICE_NAME,
        "layer": EBPF_RINGBUF_READER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _build_thinking_coach(agent_id: str) -> AgentThinkingCoach:
    return AgentThinkingCoach(
        agent_id=agent_id,
        role="monitoring",
        capabilities=("security", "zero-trust"),
        extra_techniques=("mape_k", "causal_analysis", "graphsage", "reverse_planning"),
    )


class RingBufferReader:
    """
    Reads events from eBPF ring buffer maps.

    Provides high-throughput event consumption for:
    - Network packet events
    - Syscall latency events
    - Custom application events
    """

    def __init__(
        self,
        map_name: str = "net_events",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """
        Initialize ring buffer reader.

        Args:
            map_name: Name of the ring buffer map in eBPF program
        """
        self.map_name = map_name
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_RINGBUF_READER_SERVICE_NAME
        self.running = False
        self.event_handlers: Dict[str, Callable] = {}
        self.thinking_coach = _build_thinking_coach(self.source_agent)
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        logger.info(f"RingBufferReader initialized for map: {map_name}")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            return EventBus(project_root=self.event_project_root)
        except Exception as exc:
            logger.error("Failed to initialize eBPF ringbuf EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                EBPF_RINGBUF_READER_SERVICE_NAME,
            )
            coach = _build_thinking_coach(self.source_agent)
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
            "task_type": "ebpf_ringbuf_reader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local ring/perf reader evidence, hashed map and "
                "event selectors, handler counts, event sizes, CPU IDs, and "
                "status; do not expose raw map names, event types, event payloads, "
                "stdout, stderr, or handler errors."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose ring-buffer reader thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        start: float,
        reason: str = "",
        backend: str = "",
        returncode: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        event_size_bytes: Optional[int] = None,
        cpu_id: Optional[int] = None,
        handler_event_type: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "reason": reason,
                "backend": backend,
                "read_only": True,
                "returncode_present": returncode is not None,
                "map_name_hash": _hash_value(getattr(self, "map_name", None)),
                "map_name_redacted": True,
                "handler_event_type_hash": _hash_value(handler_event_type),
                "handler_event_type_redacted": handler_event_type is not None,
                "handler_count": len(getattr(self, "event_handlers", {})),
                "event_size_bytes": event_size_bytes,
                "cpu_id": cpu_id,
                "bcc_available": BCC_AVAILABLE,
                "output_redacted": True,
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.ringbuf_reader",
            "stage": stage,
            "operation": operation,
            "operation_resource": "ebpf_ringbuf_observation",
            "resource": "network:ebpf:ringbuf_reader",
            "service_name": self.source_agent,
            "layer": EBPF_RINGBUF_READER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "reason": reason,
            "backend": backend,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "map_name_hash": _hash_value(self.map_name),
            "map_name_redacted": True,
            "handler_event_type_hash": _hash_value(handler_event_type),
            "handler_event_type_redacted": handler_event_type is not None,
            "handler_count": len(self.event_handlers),
            "event_size_bytes": event_size_bytes,
            "cpu_id": cpu_id,
            "bcc_available": BCC_AVAILABLE,
            "payloads_redacted": True,
            "read_only": True,
            "observed_state": True,
            "safe_observation": True,
            "thinking": thinking,
            "claim_boundary": EBPF_RINGBUF_READER_CLAIM_BOUNDARY,
            "output": _bounded_output_metadata(stdout, stderr),
        }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF ringbuf observation")
            return None

    def register_handler(self, event_type: str, handler: Callable):
        """
        Register event handler.

        Args:
            event_type: Type of event (e.g., "packet", "syscall")
            handler: Callback function(event_data) -> None
        """
        self.event_handlers[event_type] = handler
        logger.debug(f"Registered handler for event type: {event_type}")

    def read_via_bpftool(self) -> Optional[Dict[str, Any]]:
        """
        Read ring buffer events using bpftool.

        Note: bpftool doesn't directly support ring buffer reading,
        but we can use it to inspect maps and use alternative methods.

        Returns:
            Event data or None
        """
        # Ring buffers are typically read via:
        # 1. libbpf ring buffer API (C) - recommended for production
        # 2. bcc Python bindings - use read_via_bcc() instead
        # 3. Custom userspace reader via libbpf-rs or similar

        # For bpftool, we can at least verify the map exists
        start = time.monotonic()
        try:
            # Check if map exists: bpftool map show name <map_name>
            result = safe_run(
                ["bpftool", "map", "show", "name", self.map_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                logger.debug(
                    f"Ring buffer map '{self.map_name}' exists (use read_via_bcc() for actual reading)"
                )
                self._publish_observation(
                    stage="ringbuf_map_exists",
                    operation="read_via_bpftool",
                    status="success",
                    reason="bpftool_map_show_succeeded",
                    backend="bpftool",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    extra={"bpftool_can_read_events": False},
                )
                # Return metadata about the map
                return {
                    "map_name": self.map_name,
                    "exists": True,
                    "note": "Use read_via_bcc() for actual event reading",
                }
            else:
                logger.debug(f"Ring buffer map '{self.map_name}' not found")
                self._publish_observation(
                    stage="ringbuf_map_missing",
                    operation="read_via_bpftool",
                    status="empty",
                    reason="bpftool_map_show_failed",
                    backend="bpftool",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    extra={"bpftool_can_read_events": False},
                )
                return None
        except FileNotFoundError:
            logger.debug("bpftool not available")
            self._publish_observation(
                stage="ringbuf_bpftool_unavailable",
                operation="read_via_bpftool",
                status="empty",
                reason="bpftool_unavailable",
                backend="bpftool",
                start=start,
                extra={"bpftool_can_read_events": False},
            )
            return None
        except Exception as e:
            logger.debug(f"Error checking ring buffer map: {e}")
            self._publish_observation(
                stage="ringbuf_bpftool_failed",
                operation="read_via_bpftool",
                status="failure",
                reason="exception",
                backend="bpftool",
                start=start,
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": _hash_value(str(e)),
                    "error_message_redacted": True,
                    "bpftool_can_read_events": False,
                },
            )
            return None

    def read_via_bcc(self, bpf_program) -> None:
        """
        Read ring buffer events using BCC.

        Args:
            bpf_program: BCC BPF program instance
        """
        start = time.monotonic()
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, cannot read ring buffer")
            self._publish_observation(
                stage="ringbuf_bcc_unavailable",
                operation="read_via_bcc",
                status="empty",
                reason="bcc_unavailable",
                backend="bcc",
                start=start,
            )
            return

        try:
            # Open ring buffer
            ring_buffer = bpf_program.get_table(self.map_name)

            # Poll for events
            def process_event(cpu, data, size):
                """Process ring buffer event."""
                try:
                    # Parse event based on structure
                    # This is simplified - real implementation would match C struct
                    event_format = "IIHBBQ"
                    event_size = struct.calcsize(event_format)
                    event = struct.unpack(event_format, data[:event_size])

                    event_data = {
                        "ifindex": event[0],
                        "len": event[1],
                        "protocol": event[2],
                        "direction": event[3],
                        "timestamp": event[5],
                    }

                    # Call registered handlers
                    for event_type, handler in self.event_handlers.items():
                        try:
                            handler(event_data)
                        except Exception as e:
                            logger.error(f"Event handler error: {e}")
                            self._publish_observation(
                                stage="ringbuf_handler_failed",
                                operation="process_event",
                                status="failure",
                                reason="handler_exception",
                                backend="bcc",
                                start=time.monotonic(),
                                event_size_bytes=size,
                                cpu_id=cpu,
                                handler_event_type=event_type,
                                extra={
                                    "error_type": type(e).__name__,
                                    "error_message_hash": _hash_value(str(e)),
                                    "error_message_redacted": True,
                                    "event_payload_redacted": True,
                                },
                            )

                except Exception as e:
                    logger.error(f"Failed to parse ring buffer event: {e}")
                    self._publish_observation(
                        stage="ringbuf_event_parse_failed",
                        operation="process_event",
                        status="failure",
                        reason="parse_exception",
                        backend="bcc",
                        start=time.monotonic(),
                        event_size_bytes=size,
                        cpu_id=cpu,
                        extra={
                            "error_type": type(e).__name__,
                            "error_message_hash": _hash_value(str(e)),
                            "error_message_redacted": True,
                            "event_payload_redacted": True,
                        },
                    )

            # Start polling
            ring_buffer.open_ring_buffer(process_event)

            logger.info("Ring buffer reader started")
            self._publish_observation(
                stage="ringbuf_bcc_opened",
                operation="read_via_bcc",
                status="success",
                reason="ring_buffer_opened",
                backend="bcc",
                start=start,
            )

            # Poll loop (would run in separate thread in production)
            while self.running:
                ring_buffer.poll(timeout=100)  # 100ms timeout

        except Exception as e:
            logger.error(f"Ring buffer reading failed: {e}")
            self._publish_observation(
                stage="ringbuf_bcc_failed",
                operation="read_via_bcc",
                status="failure",
                reason="exception",
                backend="bcc",
                start=start,
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": _hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )

    def start(self):
        """Start reading ring buffer events."""
        self.running = True
        logger.info("Ring buffer reader started")

    def stop(self):
        """Stop reading ring buffer events."""
        self.running = False
        logger.info("Ring buffer reader stopped")


class PerfEventReader:
    """
    Reads events from eBPF perf event output.

    Alternative to ring buffer for very high throughput.
    """

    def __init__(
        self,
        event_type: str = "packet_events",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.event_type = event_type
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_RINGBUF_READER_SERVICE_NAME
        self.running = False
        self.thinking_coach = _build_thinking_coach(self.source_agent)
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        logger.info(f"PerfEventReader initialized for: {event_type}")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            return EventBus(project_root=self.event_project_root)
        except Exception as exc:
            logger.error("Failed to initialize eBPF perf EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                EBPF_RINGBUF_READER_SERVICE_NAME,
            )
            coach = _build_thinking_coach(self.source_agent)
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
            "task_type": "ebpf_perf_event_reader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local perf-event reader evidence, hashed event "
                "selectors, event sizes, CPU IDs, backend status, and error "
                "metadata; do not expose raw event types, event payloads, or "
                "handler errors."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose perf-event reader thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        start: float,
        reason: str = "",
        backend: str = "bcc",
        event_size_bytes: Optional[int] = None,
        cpu_id: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "reason": reason,
                "backend": backend,
                "read_only": True,
                "event_type_hash": _hash_value(getattr(self, "event_type", None)),
                "event_type_redacted": True,
                "event_size_bytes": event_size_bytes,
                "cpu_id": cpu_id,
                "bcc_available": BCC_AVAILABLE,
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.ringbuf_reader.perf_event",
            "stage": stage,
            "operation": operation,
            "operation_resource": "ebpf_perf_event_observation",
            "resource": "network:ebpf:perf_event_reader",
            "service_name": self.source_agent,
            "layer": EBPF_RINGBUF_READER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "reason": reason,
            "backend": backend,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "event_type_hash": _hash_value(self.event_type),
            "event_type_redacted": True,
            "event_size_bytes": event_size_bytes,
            "cpu_id": cpu_id,
            "bcc_available": BCC_AVAILABLE,
            "payloads_redacted": True,
            "read_only": True,
            "observed_state": True,
            "safe_observation": True,
            "thinking": thinking,
            "claim_boundary": EBPF_RINGBUF_READER_CLAIM_BOUNDARY,
        }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF perf observation")
            return None

    def read_via_bcc(self, bpf_program) -> None:
        """Read perf events using BCC."""
        start = time.monotonic()
        if not BCC_AVAILABLE:
            logger.warning("BCC not available")
            self._publish_observation(
                stage="perf_bcc_unavailable",
                operation="read_via_bcc",
                status="empty",
                reason="bcc_unavailable",
                start=start,
            )
            return

        try:
            # Open perf event
            bpf_program["events"].open_perf_buffer(self._process_perf_event)
            self._publish_observation(
                stage="perf_bcc_opened",
                operation="read_via_bcc",
                status="success",
                reason="perf_buffer_opened",
                start=start,
            )

            # Poll loop
            while self.running:
                bpf_program.perf_buffer_poll(timeout=100)

        except Exception as e:
            logger.error(f"Perf event reading failed: {e}")
            self._publish_observation(
                stage="perf_bcc_failed",
                operation="read_via_bcc",
                status="failure",
                reason="exception",
                start=start,
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": _hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )

    def _process_perf_event(self, cpu, data, size):
        """Process perf event."""
        # Similar to ring buffer processing
        logger.debug(f"Perf event: cpu={cpu}, size={size}")
        self._publish_observation(
            stage="perf_event_seen",
            operation="process_perf_event",
            status="success",
            reason="perf_event_callback",
            start=time.monotonic(),
            event_size_bytes=size,
            cpu_id=cpu,
            extra={"event_payload_redacted": True},
        )


# Example usage
if __name__ == "__main__":
    reader = RingBufferReader("net_events")

    def handle_packet_event(event):
        print(f"Packet event: {event}")

    reader.register_handler("packet", handle_packet_event)
    reader.start()

    # In production, this would run in a separate thread
    # and integrate with MAPE-K Monitor phase

