"""
eBPF Map Manager - Write and update eBPF maps from userspace
"""

import hashlib
import logging
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_ATTESTATION_MAP_MANAGER_SERVICE_NAME = "ebpf-attestation-map-manager"
EBPF_ATTESTATION_MAP_MANAGER_LAYER = "network_ebpf_attestation_map_observed_state"
EBPF_ATTESTATION_MAP_MANAGER_CLAIM_BOUNDARY = (
    "Local eBPF attestation map evidence only. Events record bpftool map "
    "update/delete outcomes, return codes, duration, bounded output hashes, "
    "and redacted map/IP/value selectors; they do not prove production traffic, "
    "remote peer identity, or attached kernel program correctness."
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
    identity = service_event_identity(
        service_name=EBPF_ATTESTATION_MAP_MANAGER_SERVICE_NAME
    )
    return {
        "service_name": EBPF_ATTESTATION_MAP_MANAGER_SERVICE_NAME,
        "layer": EBPF_ATTESTATION_MAP_MANAGER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


class EBPFMapManager:
    """
    Manager for eBPF maps, providing write/update capabilities.
    """

    event_bus: Optional[EventBus] = None
    event_project_root: str = "."
    source_agent = EBPF_ATTESTATION_MAP_MANAGER_SERVICE_NAME

    @classmethod
    def configure_event_bus(
        cls,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ) -> None:
        cls.event_bus = event_bus
        cls.event_project_root = event_project_root

    @classmethod
    def _event_bus_or_none(cls) -> Optional[EventBus]:
        if cls.event_bus is not None:
            return cls.event_bus
        try:
            cls.event_bus = EventBus(project_root=cls.event_project_root)
            return cls.event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF attestation map EventBus: %s", exc)
            return None

    @classmethod
    def _publish_observation(
        cls,
        *,
        stage: str,
        operation: str,
        status: str,
        start: float,
        command: Optional[List[str]] = None,
        returncode: Optional[int] = None,
        stdout: Optional[Any] = None,
        stderr: Optional[Any] = None,
        read_only: bool = False,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = cls._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.attestation_map_manager",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:attestation_map_manager:{operation}",
            "service_name": cls.source_agent,
            "layer": EBPF_ATTESTATION_MAP_MANAGER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": "bpftool",
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "command": command or [],
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "output": _bounded_output_metadata(stdout, stderr),
            "payloads_redacted": True,
            "claim_boundary": EBPF_ATTESTATION_MAP_MANAGER_CLAIM_BOUNDARY,
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
                cls.source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF attestation map observation")
            return None

    @staticmethod
    def _ip_to_hex(ip_str: str) -> str:
        """Convert IP string to hex format for bpftool."""
        try:
            # Packed binary format (network byte order)
            packed_ip = socket.inet_aton(ip_str)
            # bpftool expects hex bytes in the order they appear in memory
            return " ".join(f"0x{b:02x}" for b in packed_ip)
        except Exception as e:
            logger.error("Failed to convert redacted IP to bpftool hex: %s", e)
            return ""

    @classmethod
    def update_attestation(cls, ip_address: str, is_attested: bool = True) -> bool:
        """
        Update the attestation status of a node in the eBPF map.
        
        Args:
            ip_address: IPv4 address of the node
            is_attested: True to allow traffic, False to block
        """
        map_name = "attested_nodes_map"
        key_hex = cls._ip_to_hex(ip_address)
        value_hex = "0x01" if is_attested else "0x00"
        op_start = time.monotonic()
        
        if not key_hex:
            cls._publish_observation(
                stage="attestation_map_update_key_parse_failed",
                operation="bpftool_attestation_update",
                status="failure",
                start=op_start,
                parsed_summary={"updated": False, "is_attested": is_attested},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                    "value_redacted": True,
                },
            )
            return False

        try:
            # Use shell=True if needed for complex hex strings, but list is safer
            # We need to split the key_hex string into individual arguments for subprocess
            full_cmd = ["bpftool", "map", "update", "name", map_name, "key"] + key_hex.split() + ["value", value_hex]
            
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=5)
            command_metadata = [
                "bpftool",
                "map",
                "update",
                "name",
                map_name,
                "key",
                key_hex,
                "value",
                value_hex,
            ]
            
            if result.returncode == 0:
                cls._publish_observation(
                    stage="attestation_map_update_succeeded",
                    operation="bpftool_attestation_update",
                    status="success",
                    start=op_start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=_redacted_command(
                        command_metadata,
                        redacted_indices=(4, 6, 8),
                    ),
                    parsed_summary={"updated": True, "is_attested": is_attested},
                    extra={
                        "map_name_hash": _hash_value(map_name),
                        "ip_address_hash": _hash_value(ip_address),
                        "key_hex_hash": _hash_value(key_hex),
                        "value_hash": _hash_value(value_hex),
                        "map_name_redacted": True,
                        "ip_address_redacted": True,
                        "key_hex_redacted": True,
                        "value_redacted": True,
                    },
                )
                logger.info("Updated redacted eBPF attestation entry")
                return True
            else:
                cls._publish_observation(
                    stage=(
                        "attestation_map_update_missing_map"
                        if "not found" in result.stderr.lower()
                        else "attestation_map_update_failed"
                    ),
                    operation="bpftool_attestation_update",
                    status="failure",
                    start=op_start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=_redacted_command(
                        command_metadata,
                        redacted_indices=(4, 6, 8),
                    ),
                    parsed_summary={"updated": False, "is_attested": is_attested},
                    extra={
                        "map_name_hash": _hash_value(map_name),
                        "ip_address_hash": _hash_value(ip_address),
                        "key_hex_hash": _hash_value(key_hex),
                        "value_hash": _hash_value(value_hex),
                        "map_name_redacted": True,
                        "ip_address_redacted": True,
                        "key_hex_redacted": True,
                        "value_redacted": True,
                    },
                )
                # If map doesn't exist yet (eBPF not loaded), just log warning
                if "not found" in result.stderr.lower():
                    logger.warning(f"⚠️ eBPF map '{map_name}' not found. Is the XDP program loaded?")
                else:
                    logger.error("Failed to update eBPF attestation map")
                return False
        except subprocess.TimeoutExpired as e:
            cls._publish_observation(
                stage="attestation_map_update_timeout",
                operation="bpftool_attestation_update",
                status="failure",
                start=op_start,
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                command=[
                    "bpftool",
                    "map",
                    "update",
                    "name",
                    "[redacted]",
                    "key",
                    "[redacted]",
                    "value",
                    "[redacted]",
                ],
                error=e,
                parsed_summary={"updated": False, "is_attested": is_attested},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "key_hex_hash": _hash_value(key_hex),
                    "value_hash": _hash_value(value_hex),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                    "key_hex_redacted": True,
                    "value_redacted": True,
                },
            )
            logger.error("eBPF attestation map update timed out")
            return False
        except Exception as e:
            cls._publish_observation(
                stage="attestation_map_update_error",
                operation="bpftool_attestation_update",
                status="failure",
                start=op_start,
                command=[
                    "bpftool",
                    "map",
                    "update",
                    "name",
                    "[redacted]",
                    "key",
                    "[redacted]",
                    "value",
                    "[redacted]",
                ],
                error=e,
                parsed_summary={"updated": False, "is_attested": is_attested},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "key_hex_hash": _hash_value(key_hex),
                    "value_hash": _hash_value(value_hex),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                    "key_hex_redacted": True,
                    "value_redacted": True,
                },
            )
            logger.error("Error updating eBPF attestation map")
            return False

    @classmethod
    def remove_node(cls, ip_address: str) -> bool:
        """Remove a node from the eBPF map (defaults to blocking)."""
        map_name = "attested_nodes_map"
        key_hex = cls._ip_to_hex(ip_address)
        op_start = time.monotonic()
        
        if not key_hex:
            cls._publish_observation(
                stage="attestation_map_delete_key_parse_failed",
                operation="bpftool_attestation_delete",
                status="failure",
                start=op_start,
                parsed_summary={"deleted": False},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                },
            )
            return False

        try:
            full_cmd = ["bpftool", "map", "delete", "name", map_name, "key"] + key_hex.split()
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=5)
            command_metadata = [
                "bpftool",
                "map",
                "delete",
                "name",
                map_name,
                "key",
                key_hex,
            ]
            deleted = result.returncode == 0
            cls._publish_observation(
                stage=(
                    "attestation_map_delete_succeeded"
                    if deleted
                    else "attestation_map_delete_failed"
                ),
                operation="bpftool_attestation_delete",
                status="success" if deleted else "failure",
                start=op_start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=_redacted_command(command_metadata, redacted_indices=(4, 6)),
                parsed_summary={"deleted": deleted},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "key_hex_hash": _hash_value(key_hex),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                    "key_hex_redacted": True,
                },
            )
            return deleted
        except subprocess.TimeoutExpired as e:
            cls._publish_observation(
                stage="attestation_map_delete_timeout",
                operation="bpftool_attestation_delete",
                status="failure",
                start=op_start,
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                command=[
                    "bpftool",
                    "map",
                    "delete",
                    "name",
                    "[redacted]",
                    "key",
                    "[redacted]",
                ],
                error=e,
                parsed_summary={"deleted": False},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "key_hex_hash": _hash_value(key_hex),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                    "key_hex_redacted": True,
                },
            )
            return False
        except Exception as e:
            cls._publish_observation(
                stage="attestation_map_delete_error",
                operation="bpftool_attestation_delete",
                status="failure",
                start=op_start,
                command=[
                    "bpftool",
                    "map",
                    "delete",
                    "name",
                    "[redacted]",
                    "key",
                    "[redacted]",
                ],
                error=e,
                parsed_summary={"deleted": False},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "ip_address_hash": _hash_value(ip_address),
                    "key_hex_hash": _hash_value(key_hex),
                    "map_name_redacted": True,
                    "ip_address_redacted": True,
                    "key_hex_redacted": True,
                },
            )
            return False
