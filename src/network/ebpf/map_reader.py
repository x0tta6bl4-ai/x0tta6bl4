"""
eBPF Map Reader - Read eBPF maps from userspace

This module provides utilities to read eBPF maps created by eBPF programs.
Uses bpftool or direct syscalls to read map data.
"""

import hashlib
import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_BPFT_TOOL_MAP_READER_SERVICE_NAME = "ebpf-bpftool-map-reader"
EBPF_BPFT_TOOL_MAP_READER_LAYER = "network_ebpf_bpftool_map_reader_observed_state"
EBPF_BPFT_TOOL_MAP_READER_CLAIM_BOUNDARY = (
    "Local bpftool eBPF map observation only. Events record command outcome, "
    "return code, duration, bounded output hashes, result counts, and redacted map "
    "selectors; they do not prove production traffic, packet forwarding, or that "
    "a specific BPF program is attached."
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


def _result_count(value: Any) -> int:
    if isinstance(value, dict):
        data = value.get("data")
        if hasattr(data, "__len__"):
            return len(data)
        return len(value)
    if hasattr(value, "__len__"):
        return len(value)
    return 0


class EBPFMapReader:
    """
    Reader for eBPF maps.

    Supports reading maps via:
    - bpftool (preferred, if available)
    - Direct syscalls (future enhancement)
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_BPFT_TOOL_MAP_READER_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="monitoring",
            capabilities=("security", "zero-trust"),
            extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        self.bpftool_available = self._check_bpftool()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            return EventBus(project_root=self.event_project_root)
        except Exception as exc:
            logger.error("Failed to initialize eBPF map reader EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                EBPF_BPFT_TOOL_MAP_READER_SERVICE_NAME,
            )
            coach = AgentThinkingCoach(
                agent_id=self.source_agent,
                role="monitoring",
                capabilities=("security", "zero-trust"),
                extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
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
            "task_type": "ebpf_bpftool_map_reader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local bpftool map-reader evidence, hashed map "
                "selectors, bounded output metadata, counts, and status; do "
                "not expose raw map names, map data, stdout, stderr, or counter "
                "values."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose bpftool map-reader thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _identity_metadata(self) -> Dict[str, Any]:
        identity = service_event_identity(
            service_name=EBPF_BPFT_TOOL_MAP_READER_SERVICE_NAME
        )
        return {
            "service_name": self.source_agent,
            "layer": EBPF_BPFT_TOOL_MAP_READER_LAYER,
            "spiffe_id_configured": bool(identity.get("spiffe_id")),
            "did_configured": bool(identity.get("did")),
            "wallet_address_configured": bool(identity.get("wallet_address")),
            "redacted": True,
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        start: float,
        result_count: int = 0,
        reason: str = "",
        returncode: Optional[int] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        map_name: Optional[str] = None,
        map_id: Optional[int] = None,
        selector: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "reason": reason,
                "backend": "bpftool",
                "read_only": True,
                "returncode_present": returncode is not None,
                "result_count": result_count,
                "bpftool_available": getattr(self, "bpftool_available", False),
                "map_selector": selector,
                "map_name_hash": _hash_value(map_name),
                "map_id_hash": _hash_value(map_id),
                "map_selector_redacted": True,
                "output_redacted": True,
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.map_reader",
            "stage": stage,
            "operation": operation,
            "operation_resource": "bpftool_map_observation",
            "resource": "network:ebpf:bpftool_map_reader",
            "service_name": self.source_agent,
            "layer": EBPF_BPFT_TOOL_MAP_READER_LAYER,
            "identity": self._identity_metadata(),
            "status": status,
            "reason": reason,
            "backend": "bpftool",
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "result_count": result_count,
            "bpftool_available": self.bpftool_available,
            "map_selector": selector,
            "map_name_hash": _hash_value(map_name),
            "map_id_hash": _hash_value(map_id),
            "map_selector_redacted": True,
            "payloads_redacted": True,
            "read_only": True,
            "observed_state": True,
            "safe_observation": True,
            "thinking": thinking,
            "claim_boundary": EBPF_BPFT_TOOL_MAP_READER_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish eBPF map reader observation")
            return None

    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        try:
            result = subprocess.run(
                ["bpftool", "--version"], capture_output=True, timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def list_maps(self) -> List[Dict[str, Any]]:
        """
        List all eBPF maps.

        Returns:
            List of map information dictionaries
        """
        if not self.bpftool_available:
            logger.warning("bpftool not available, cannot list maps")
            self._publish_observation(
                stage="map_list_unavailable",
                operation="list_maps",
                status="empty",
                reason="bpftool_unavailable",
                start=time.monotonic(),
            )
            return []

        start = time.monotonic()
        try:
            result = subprocess.run(
                ["bpftool", "map", "show", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                maps = json.loads(result.stdout)
                normalized_maps = maps if isinstance(maps, list) else [maps]
                self._publish_observation(
                    stage="map_list_succeeded",
                    operation="list_maps",
                    status="success",
                    reason="bpftool_map_show_succeeded",
                    start=start,
                    result_count=len(normalized_maps),
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    extra={"map_names_redacted": True},
                )
                return normalized_maps
            else:
                logger.error(f"bpftool map show failed: {result.stderr}")
                self._publish_observation(
                    stage="map_list_failed",
                    operation="list_maps",
                    status="failure",
                    reason="bpftool_map_show_failed",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    extra={"map_names_redacted": True},
                )
                return []
        except Exception as e:
            logger.error(f"Error listing maps: {e}")
            self._publish_observation(
                stage="map_list_failed",
                operation="list_maps",
                status="failure",
                reason="exception",
                start=start,
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": _hash_value(str(e)),
                    "error_message_redacted": True,
                    "map_names_redacted": True,
                },
            )
            return []

    def read_map(
        self, map_id: Optional[int] = None, map_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Read contents of an eBPF map.

        Args:
            map_id: Map ID (if known)
            map_name: Map name (if known)

        Returns:
            Dictionary with map contents
        """
        if not self.bpftool_available:
            logger.warning("bpftool not available, cannot read map")
            self._publish_observation(
                stage="map_read_unavailable",
                operation="read_map",
                status="empty",
                reason="bpftool_unavailable",
                start=time.monotonic(),
                map_name=map_name,
                map_id=map_id,
                selector="name" if map_name else "id" if map_id else "none",
            )
            return {}

        if not map_id and not map_name:
            logger.error("Either map_id or map_name must be provided")
            self._publish_observation(
                stage="map_read_invalid_request",
                operation="read_map",
                status="failure",
                reason="missing_map_selector",
                start=time.monotonic(),
                selector="none",
            )
            return {}

        start = time.monotonic()
        try:
            # Use map name if available, otherwise use ID
            map_arg = map_name if map_name else str(map_id)
            selector = "name" if map_name else "id"

            result = subprocess.run(
                ["bpftool", "map", "dump", selector, map_arg, "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                normalized_data = data if isinstance(data, dict) else {"data": data}
                self._publish_observation(
                    stage="map_read_succeeded",
                    operation="read_map",
                    status="success",
                    reason="bpftool_map_dump_succeeded",
                    start=start,
                    result_count=_result_count(normalized_data),
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    map_name=map_name,
                    map_id=map_id,
                    selector=selector,
                )
                return normalized_data
            else:
                # Try with ID if name failed
                if map_name and map_id:
                    fallback_result = subprocess.run(
                        ["bpftool", "map", "dump", "id", str(map_id), "--json"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if fallback_result.returncode == 0:
                        data = json.loads(fallback_result.stdout)
                        normalized_data = (
                            data if isinstance(data, dict) else {"data": data}
                        )
                        self._publish_observation(
                            stage="map_read_succeeded",
                            operation="read_map",
                            status="success",
                            reason="name_failed_id_succeeded",
                            start=start,
                            result_count=_result_count(normalized_data),
                            returncode=fallback_result.returncode,
                            stdout=fallback_result.stdout,
                            stderr=fallback_result.stderr,
                            map_name=map_name,
                            map_id=map_id,
                            selector="id",
                            extra={
                                "primary_selector": "name",
                                "primary_returncode": result.returncode,
                                "primary_output": _bounded_output_metadata(
                                    result.stdout,
                                    result.stderr,
                                ),
                            },
                        )
                        return normalized_data

                logger.error(f"bpftool map dump failed: {result.stderr}")
                self._publish_observation(
                    stage="map_read_failed",
                    operation="read_map",
                    status="failure",
                    reason="bpftool_map_dump_failed",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    map_name=map_name,
                    map_id=map_id,
                    selector=selector,
                )
                return {}
        except Exception as e:
            logger.error(f"Error reading map: {e}")
            self._publish_observation(
                stage="map_read_failed",
                operation="read_map",
                status="failure",
                reason="exception",
                start=start,
                map_name=map_name,
                map_id=map_id,
                selector="name" if map_name else "id",
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": _hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )
            return {}

    def read_counter_map(self, map_name: str) -> Dict[str, int]:
        """
        Read a counter map (common eBPF pattern).

        Args:
            map_name: Name of the counter map

        Returns:
            Dictionary mapping keys to counter values
        """
        map_data = self.read_map(map_name=map_name)

        if not map_data:
            self._publish_observation(
                stage="counter_map_empty",
                operation="read_counter_map",
                status="empty",
                reason="map_read_empty",
                start=time.monotonic(),
                map_name=map_name,
                selector="name",
            )
            return {}

        # Parse counter map format
        counters = {}
        if isinstance(map_data, dict) and "data" in map_data:
            for entry in map_data["data"]:
                if "key" in entry and "value" in entry:
                    key = entry["key"]
                    value = entry["value"]
                    # Convert key to string for readability
                    if isinstance(key, list):
                        key_str = "_".join(str(k) for k in key)
                    else:
                        key_str = str(key)
                    counters[key_str] = (
                        int(value) if isinstance(value, (int, str)) else value
                    )

        self._publish_observation(
            stage="counter_map_aggregated",
            operation="read_counter_map",
            status="success",
            reason="counter_entries_parsed",
            start=time.monotonic(),
            result_count=len(counters),
            map_name=map_name,
            selector="name",
            extra={"counter_values_redacted": True},
        )
        return counters

    def get_map_info(self, map_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific map.

        Args:
            map_name: Name of the map

        Returns:
            Map information dictionary or None
        """
        maps = self.list_maps()
        start = time.monotonic()
        for map_info in maps:
            if map_info.get("name") == map_name:
                self._publish_observation(
                    stage="map_info_lookup_succeeded",
                    operation="get_map_info",
                    status="success",
                    reason="map_info_found",
                    start=start,
                    result_count=1,
                    map_name=map_name,
                    selector="name",
                    extra={"map_info_redacted": True},
                )
                return map_info
        self._publish_observation(
            stage="map_info_lookup_empty",
            operation="get_map_info",
            status="empty",
            reason="map_info_not_found",
            start=start,
            map_name=map_name,
            selector="name",
            extra={"map_info_redacted": True},
        )
        return None


def read_packet_counters(
    map_name: str = "packet_counters",
    event_bus: Optional[EventBus] = None,
) -> Dict[str, int]:
    """
    Convenience function to read packet counters from eBPF map.

    Args:
        map_name: Name of the packet counter map

    Returns:
        Dictionary with protocol -> count mapping
    """
    reader = EBPFMapReader(event_bus=event_bus)
    return reader.read_counter_map(map_name)


if __name__ == "__main__":
    # CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description="Read eBPF maps")
    parser.add_argument("--list", action="store_true", help="List all maps")
    parser.add_argument("--read", type=str, help="Read map by name")
    parser.add_argument(
        "--counters", type=str, default="packet_counters", help="Read counter map"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    reader = EBPFMapReader()

    if args.list:
        maps = reader.list_maps()
        print(f"Found {len(maps)} maps:")
        for map_info in maps:
            print(f"  - {map_info.get('name', 'unnamed')} (id: {map_info.get('id')})")

    if args.read:
        data = reader.read_map(map_name=args.read)
        print(f"Map '{args.read}':")
        print(json.dumps(data, indent=2))

    if args.counters:
        counters = reader.read_counter_map(args.counters)
        print(f"Counters from '{args.counters}':")
        for key, value in counters.items():
            print(f"  {key}: {value}")
