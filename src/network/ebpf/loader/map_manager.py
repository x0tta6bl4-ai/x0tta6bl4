"""
eBPF Map Manager - Map operations and statistics

Handles:
- Reading eBPF maps via bpftool
- Updating map entries
- Collecting statistics
"""

import hashlib
import json
import logging
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_LOADER_MAP_MANAGER_SERVICE_NAME = "ebpf-loader-map-manager"
EBPF_LOADER_MAP_MANAGER_LAYER = "network_ebpf_loader_map_manager_observed_state"
EBPF_LOADER_MAP_MANAGER_CLAIM_BOUNDARY = (
    "Local modular eBPF map manager evidence only. Events record bpftool "
    "map command outcomes, return codes, duration, bounded output hashes, "
    "and redacted map/key/value selectors; they do not prove production "
    "traffic, route quality, or attached kernel program correctness."
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
    return _sha256_text(str(value))


def _bounded_output_metadata(
    stdout: Optional[Any],
    stderr: Optional[Any],
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


def _redacted_command(
    command: List[Any],
    redacted_indices: Tuple[int, ...],
) -> List[str]:
    redacted = set(redacted_indices)
    safe_command: List[str] = []
    for index, item in enumerate(command):
        if index == 0:
            safe_command.append(str(item).split("/")[-1])
        elif index in redacted:
            safe_command.append("[redacted]")
        else:
            safe_command.append(str(item))
    return safe_command


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_LOADER_MAP_MANAGER_SERVICE_NAME)
    return {
        "service_name": EBPF_LOADER_MAP_MANAGER_SERVICE_NAME,
        "layer": EBPF_LOADER_MAP_MANAGER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


class EBPFMapManager:
    """
    eBPF Map Manager - handles map operations.
    
    Responsibilities:
    - Read map entries via bpftool
    - Update map entries
    - Collect statistics from maps
    
    Example:
        >>> manager = EBPFMapManager()
        >>> stats = manager.get_stats("packet_stats")
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """Initialize the map manager."""
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_LOADER_MAP_MANAGER_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        self._bpftool_available = self._check_bpftool()
        logger.info(f"EBPFMapManager initialized (bpftool={self._bpftool_available})")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = EventBus(project_root=self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF loader map manager EventBus: %s", exc)
            return None

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose the loaded thinking profile without task data."""

        return self.thinking_coach.status()

    def _prepare_thinking_context(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        command: Optional[List[str]],
        returncode: Optional[int],
        read_only: bool,
        parsed_summary: Optional[Dict[str, Any]],
        extra: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build a redacted decision context for eBPF map observations."""

        safe_task = {
            "task_type": "ebpf_loader_map_observation",
            "goal": f"{operation}:{stage}:{status}",
            "constraints": {
                "operation": operation,
                "stage": stage,
                "status": status,
                "source_mode": "bpftool",
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "bpftool_available": getattr(self, "_bpftool_available", None),
                "command_shape": command or [],
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
            "safety_boundary": (
                "Record only local bpftool evidence, redacted map selectors, "
                "hashes, and bounded metadata; do not expose map names, keys, "
                "values, stdout, or stderr."
            ),
        }
        return self.thinking_coach.prepare_task(safe_task)

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        start: float,
        command: Optional[List[str]] = None,
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

        payload: Dict[str, Any] = {
            "component": "network.ebpf.loader.map_manager",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:loader_map_manager:{operation}",
            "service_name": self.source_agent,
            "layer": EBPF_LOADER_MAP_MANAGER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": "bpftool",
            "bpftool_available": getattr(self, "_bpftool_available", None),
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "command": command or [],
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "thinking": self._prepare_thinking_context(
                stage=stage,
                operation=operation,
                status=status,
                command=command,
                returncode=returncode,
                read_only=read_only,
                parsed_summary=parsed_summary,
                extra=extra,
            ),
            "output": _bounded_output_metadata(stdout, stderr),
            "payloads_redacted": True,
            "claim_boundary": EBPF_LOADER_MAP_MANAGER_CLAIM_BOUNDARY,
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
                self.source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF loader map manager observation")
            return None
    
    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        cmd = ["bpftool", "version"]
        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=2
            )
            available = result.returncode == 0
            self._bpftool_available = available
            self._publish_observation(
                stage=(
                    "loader_map_manager_bpftool_available"
                    if available
                    else "loader_map_manager_bpftool_unavailable"
                ),
                operation="bpftool_available",
                status="success" if available else "empty",
                start=start,
                returncode=result.returncode,
                stdout=getattr(result, "stdout", None),
                stderr=getattr(result, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=()),
                parsed_summary={"bpftool_available": available},
            )
            return available
        except FileNotFoundError as exc:
            self._bpftool_available = False
            self._publish_observation(
                stage="loader_map_manager_bpftool_unavailable",
                operation="bpftool_available",
                status="empty",
                start=start,
                command=_redacted_command(cmd, redacted_indices=()),
                error=exc,
                parsed_summary={"bpftool_available": False},
            )
            return False
        except subprocess.TimeoutExpired as exc:
            self._bpftool_available = False
            self._publish_observation(
                stage="loader_map_manager_bpftool_timeout",
                operation="bpftool_available",
                status="failure",
                start=start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=()),
                error=exc,
                parsed_summary={"bpftool_available": False},
            )
            return False
    
    def read_map(self, map_name: str) -> Dict[str, Any]:
        """
        Read eBPF map entries.
        
        Args:
            map_name: Name of the map to read
            
        Returns:
            Dict with map data
        """
        cmd = ["bpftool", "map", "dump", "name", map_name, "--json"]
        start = time.monotonic()
        if not self._bpftool_available:
            self._publish_observation(
                stage="loader_map_manager_map_read_unavailable",
                operation="bpftool_map_dump",
                status="empty",
                start=start,
                command=_redacted_command(cmd, redacted_indices=(4,)),
                parsed_summary={"result_count": 0},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                },
            )
            logger.warning("bpftool not available, cannot read map")
            return {}
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                self._publish_observation(
                    stage="loader_map_manager_map_read_failed",
                    operation="bpftool_map_dump",
                    status="failure",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=_redacted_command(cmd, redacted_indices=(4,)),
                    parsed_summary={"result_count": 0},
                    extra={
                        "map_name_hash": _hash_value(map_name),
                        "map_name_redacted": True,
                    },
                )
                logger.warning("bpftool map dump failed")
                return {}
            
            data = json.loads(result.stdout)
            
            # Parse map data
            parsed = {}
            if isinstance(data, list):
                for entry in data:
                    key = entry.get("key")
                    value = entry.get("value")
                    
                    # Convert key to string
                    if isinstance(key, list):
                        key_str = "_".join(str(k) for k in key)
                    else:
                        key_str = str(key)
                    
                    parsed[key_str] = value
            
            self._publish_observation(
                stage="loader_map_manager_map_read_succeeded",
                operation="bpftool_map_dump",
                status="success",
                start=start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=_redacted_command(cmd, redacted_indices=(4,)),
                parsed_summary={
                    "result_count": len(parsed),
                    "raw_entries": len(data) if isinstance(data, list) else 0,
                },
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                },
            )
            return parsed
            
        except json.JSONDecodeError as exc:
            self._publish_observation(
                stage="loader_map_manager_map_read_parse_failed",
                operation="bpftool_map_dump",
                status="failure",
                start=start,
                returncode=getattr(result, "returncode", None) if "result" in locals() else None,
                stdout=getattr(result, "stdout", None) if "result" in locals() else None,
                stderr=getattr(result, "stderr", None) if "result" in locals() else None,
                command=_redacted_command(cmd, redacted_indices=(4,)),
                error=exc,
                parsed_summary={"result_count": 0},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                },
            )
            logger.error("Failed to parse bpftool map dump output")
            return {}
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="loader_map_manager_map_read_timeout",
                operation="bpftool_map_dump",
                status="failure",
                start=start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                error=exc,
                parsed_summary={"result_count": 0},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                },
            )
            logger.error("bpftool map dump timed out")
            return {}
        except Exception as e:
            self._publish_observation(
                stage="loader_map_manager_map_read_error",
                operation="bpftool_map_dump",
                status="failure",
                start=start,
                command=_redacted_command(cmd, redacted_indices=(4,)),
                error=e,
                parsed_summary={"result_count": 0},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                },
            )
            logger.error("Error reading eBPF map")
            return {}
    
    def update_entry(
        self, 
        map_name: str, 
        key: str, 
        value: str
    ) -> bool:
        """
        Update an entry in an eBPF map.
        
        Args:
            map_name: Name of the map
            key: Entry key
            value: Entry value
            
        Returns:
            True if update successful
        """
        cmd = [
            "bpftool", "map", "update",
            "name", map_name,
            "key", key,
            "value", value,
        ]
        start = time.monotonic()
        if not self._bpftool_available:
            self._publish_observation(
                stage="loader_map_manager_map_update_unavailable",
                operation="bpftool_map_update",
                status="empty",
                start=start,
                command=_redacted_command(cmd, redacted_indices=(4, 6, 8)),
                read_only=False,
                parsed_summary={"updated": False},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "key_hash": _hash_value(key),
                    "value_hash": _hash_value(value),
                    "map_name_redacted": True,
                    "key_redacted": True,
                    "value_redacted": True,
                },
            )
            logger.warning("bpftool not available, cannot update map")
            return False
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                self._publish_observation(
                    stage="loader_map_manager_map_update_succeeded",
                    operation="bpftool_map_update",
                    status="success",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=_redacted_command(cmd, redacted_indices=(4, 6, 8)),
                    read_only=False,
                    parsed_summary={"updated": True},
                    extra={
                        "map_name_hash": _hash_value(map_name),
                        "key_hash": _hash_value(key),
                        "value_hash": _hash_value(value),
                        "map_name_redacted": True,
                        "key_redacted": True,
                        "value_redacted": True,
                    },
                )
                logger.debug("Updated eBPF map entry via bpftool")
                return True
            else:
                self._publish_observation(
                    stage="loader_map_manager_map_update_failed",
                    operation="bpftool_map_update",
                    status="failure",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=_redacted_command(cmd, redacted_indices=(4, 6, 8)),
                    read_only=False,
                    parsed_summary={"updated": False},
                    extra={
                        "map_name_hash": _hash_value(map_name),
                        "key_hash": _hash_value(key),
                        "value_hash": _hash_value(value),
                        "map_name_redacted": True,
                        "key_redacted": True,
                        "value_redacted": True,
                    },
                )
                logger.warning("Failed to update eBPF map entry")
                return False
                
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="loader_map_manager_map_update_timeout",
                operation="bpftool_map_update",
                status="failure",
                start=start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4, 6, 8)),
                read_only=False,
                error=exc,
                parsed_summary={"updated": False},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "key_hash": _hash_value(key),
                    "value_hash": _hash_value(value),
                    "map_name_redacted": True,
                    "key_redacted": True,
                    "value_redacted": True,
                },
            )
            logger.error("bpftool map update timed out")
            return False
        except Exception as e:
            self._publish_observation(
                stage="loader_map_manager_map_update_error",
                operation="bpftool_map_update",
                status="failure",
                start=start,
                command=_redacted_command(cmd, redacted_indices=(4, 6, 8)),
                read_only=False,
                error=e,
                parsed_summary={"updated": False},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "key_hash": _hash_value(key),
                    "value_hash": _hash_value(value),
                    "map_name_redacted": True,
                    "key_redacted": True,
                    "value_redacted": True,
                },
            )
            logger.error("Error updating eBPF map")
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get packet statistics from eBPF maps.
        
        Reads from packet_stats map if available.
        
        Returns:
            Dict with keys: total_packets, passed_packets, dropped_packets, forwarded_packets
        """
        stats = {
            "total_packets": 0,
            "passed_packets": 0,
            "dropped_packets": 0,
            "forwarded_packets": 0,
        }
        
        map_data = self.read_map("packet_stats")
        
        for key, value in map_data.items():
            try:
                key_int = int(key) if isinstance(key, (int, str)) else 0
                value_int = int(value) if isinstance(value, (int, str)) else 0
                
                if key_int == 0:
                    stats["total_packets"] = value_int
                elif key_int == 1:
                    stats["passed_packets"] = value_int
                elif key_int == 2:
                    stats["dropped_packets"] = value_int
                elif key_int == 3:
                    stats["forwarded_packets"] = value_int
            except (ValueError, TypeError):
                continue
        
        return stats
    
    def update_routes(self, routes: Dict[str, str]) -> bool:
        """
        Update mesh routing table in eBPF map.
        
        Args:
            routes: Dict mapping destination IP to next hop interface index
            
        Returns:
            True if all updates successful
        """
        route_start = time.monotonic()
        if not self._bpftool_available:
            self._publish_observation(
                stage="loader_map_manager_route_update_unavailable",
                operation="bpftool_route_update",
                status="empty",
                start=route_start,
                command=[],
                read_only=False,
                parsed_summary={"routes_total": len(routes), "routes_updated": 0},
                extra={
                    "map_name_hash": _hash_value("mesh_routes"),
                    "map_name_redacted": True,
                    "route_selectors_redacted": True,
                },
            )
            logger.warning("bpftool not available, cannot update routes")
            return False
        
        success = True
        updated = 0
        for dest_ip, next_hop_if in routes.items():
            if not self.update_entry("mesh_routes", dest_ip, next_hop_if):
                success = False
            else:
                updated += 1
        
        if success:
            logger.info(f"Updated {len(routes)} routes in eBPF map")
        self._publish_observation(
            stage=(
                "loader_map_manager_route_update_succeeded"
                if success
                else "loader_map_manager_route_update_partial_failure"
            ),
            operation="bpftool_route_update",
            status="success" if success else "failure",
            start=route_start,
            command=[],
            read_only=False,
            parsed_summary={"routes_total": len(routes), "routes_updated": updated},
            extra={
                "map_name_hash": _hash_value("mesh_routes"),
                "map_name_redacted": True,
                "route_selectors_redacted": True,
            },
        )
        
        return success
    
    def list_maps(self) -> List[Dict]:
        """
        List all eBPF maps.
        
        Returns:
            List of map information dicts
        """
        cmd = ["bpftool", "map", "list", "--json"]
        start = time.monotonic()
        if not self._bpftool_available:
            self._publish_observation(
                stage="loader_map_manager_map_list_unavailable",
                operation="bpftool_map_list",
                status="empty",
                start=start,
                command=_redacted_command(cmd, redacted_indices=()),
                parsed_summary={"result_count": 0},
                extra={"map_names_redacted": True},
            )
            return []
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                self._publish_observation(
                    stage="loader_map_manager_map_list_failed",
                    operation="bpftool_map_list",
                    status="failure",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=_redacted_command(cmd, redacted_indices=()),
                    parsed_summary={"result_count": 0},
                    extra={"map_names_redacted": True},
                )
                return []
            
            maps = json.loads(result.stdout)
            self._publish_observation(
                stage="loader_map_manager_map_list_succeeded",
                operation="bpftool_map_list",
                status="success",
                start=start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=_redacted_command(cmd, redacted_indices=()),
                parsed_summary={
                    "result_count": len(maps) if hasattr(maps, "__len__") else 0
                },
                extra={"map_names_redacted": True},
            )
            return maps
            
        except json.JSONDecodeError as exc:
            self._publish_observation(
                stage="loader_map_manager_map_list_parse_failed",
                operation="bpftool_map_list",
                status="failure",
                start=start,
                returncode=getattr(result, "returncode", None) if "result" in locals() else None,
                stdout=getattr(result, "stdout", None) if "result" in locals() else None,
                stderr=getattr(result, "stderr", None) if "result" in locals() else None,
                command=_redacted_command(cmd, redacted_indices=()),
                error=exc,
                parsed_summary={"result_count": 0},
                extra={"map_names_redacted": True},
            )
            return []
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="loader_map_manager_map_list_timeout",
                operation="bpftool_map_list",
                status="failure",
                start=start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=()),
                error=exc,
                parsed_summary={"result_count": 0},
                extra={"map_names_redacted": True},
            )
            return []
        except Exception as exc:
            self._publish_observation(
                stage="loader_map_manager_map_list_error",
                operation="bpftool_map_list",
                status="failure",
                start=start,
                command=_redacted_command(cmd, redacted_indices=()),
                error=exc,
                parsed_summary={"result_count": 0},
                extra={"map_names_redacted": True},
            )
            return []
