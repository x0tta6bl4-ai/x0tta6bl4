"""
eBPF Attach Manager - Interface attachment management

Handles:
- XDP attachment (SKB/DRV/HW modes)
- TC attachment (ingress/egress)
- Attachment verification
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.core.security.subprocess_validator import safe_run
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_LOADER_ATTACH_MANAGER_SERVICE_NAME = "ebpf-loader-attach-manager"
EBPF_LOADER_ATTACH_MANAGER_LAYER = "network_ebpf_loader_attach_manager_observed_state"
EBPF_LOADER_ATTACH_MANAGER_CLAIM_BOUNDARY = (
    "Local modular eBPF attach manager evidence only. Events record ip/tc "
    "command outcomes, interface verification, return codes, duration, bounded "
    "output hashes, and redacted interface/program selectors; they do not prove "
    "production traffic, remote peer behavior, route quality, or attached kernel "
    "program correctness beyond the local command and verification result."
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
    identity = service_event_identity(service_name=EBPF_LOADER_ATTACH_MANAGER_SERVICE_NAME)
    return {
        "service_name": EBPF_LOADER_ATTACH_MANAGER_SERVICE_NAME,
        "layer": EBPF_LOADER_ATTACH_MANAGER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


class EBPFAttachMode(Enum):
    """XDP attachment modes"""
    SKB = "skb"  # Generic mode (slowest, works everywhere)
    DRV = "drv"  # Driver mode (fast, requires driver support)
    HW = "hw"  # Hardware offload (fastest, rare support)


class EBPFAttachError(Exception):
    """Raised when attaching eBPF program to interface fails"""
    pass


class EBPFAttachManager:
    """
    eBPF Attach Manager - handles program attachment to interfaces.
    
    Responsibilities:
    - Attach XDP programs to interfaces
    - Attach TC programs to interfaces
    - Verify attachments
    - Track attached programs
    
    Example:
        >>> manager = EBPFAttachManager()
        >>> manager.attach_xdp("/sys/fs/bpf/prog", "eth0", EBPFAttachMode.SKB)
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """Initialize the attach manager."""
        self.attached_interfaces: Dict[str, List[Dict]] = {}
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_LOADER_ATTACH_MANAGER_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        logger.info("EBPFAttachManager initialized")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = EventBus(project_root=self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF attach manager EventBus: %s", exc)
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
        source_mode: str,
        command: Optional[List[str]],
        returncode: Optional[int],
        read_only: bool,
        parsed_summary: Optional[Dict[str, Any]],
        extra: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build a redacted decision context for eBPF attach observations."""

        safe_task = {
            "task_type": "ebpf_loader_attach_observation",
            "goal": f"{operation}:{stage}:{status}",
            "constraints": {
                "operation": operation,
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "command_shape": command or [],
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
            "safety_boundary": (
                "Record only local command evidence, redacted selectors, hashes, "
                "and bounded metadata; do not expose interface names, program "
                "paths, stdout, stderr, or raw program IDs."
            ),
        }
        return self.thinking_coach.prepare_task(safe_task)

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
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
            "component": "network.ebpf.loader.attach_manager",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:loader_attach_manager:{operation}",
            "service_name": self.source_agent,
            "layer": EBPF_LOADER_ATTACH_MANAGER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
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
                source_mode=source_mode,
                command=command,
                returncode=returncode,
                read_only=read_only,
                parsed_summary=parsed_summary,
                extra=extra,
            ),
            "output": _bounded_output_metadata(stdout, stderr),
            "payloads_redacted": True,
            "claim_boundary": EBPF_LOADER_ATTACH_MANAGER_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish eBPF attach manager observation")
            return None
    
    def verify_interface(self, interface: str) -> bool:
        """
        Verify network interface exists and is up.
        
        Args:
            interface: Network interface name
            
        Returns:
            True if interface is valid and up
            
        Raises:
            EBPFAttachError: If interface not found or cannot be brought up
        """
        interface_path = Path(f"/sys/class/net/{interface}")
        if not interface_path.exists():
            verify_start = time.monotonic()
            self._publish_observation(
                stage="loader_attach_manager_interface_missing",
                operation="verify_interface",
                status="failure",
                source_mode="sysfs",
                start=verify_start,
                parsed_summary={"interface_exists": False, "interface_up": False},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            raise EBPFAttachError(f"Network interface not found: {interface}")
        
        # Check if interface is up
        operstate_path = interface_path / "operstate"
        if operstate_path.exists():
            operstate = operstate_path.read_text().strip()
            if operstate != "up":
                logger.warning(f"Interface {interface} is not up (state: {operstate})")
                # Try to bring interface up
                cmd = ["ip", "link", "set", "dev", interface, "up"]
                bring_up_start = time.monotonic()
                try:
                    result = safe_run(
                        cmd,
                        check=True,
                        capture_output=True,
                        timeout=5,
                    )
                    self._publish_observation(
                        stage="loader_attach_manager_interface_bring_up_succeeded",
                        operation="interface_bring_up",
                        status="success",
                        source_mode="ip_link",
                        start=bring_up_start,
                        returncode=getattr(result, "returncode", 0),
                        stdout=getattr(result, "stdout", None),
                        stderr=getattr(result, "stderr", None),
                        command=_redacted_command(cmd, redacted_indices=(4,)),
                        read_only=False,
                        parsed_summary={
                            "interface_exists": True,
                            "interface_up_before": False,
                        },
                        extra={
                            "interface_hash": _hash_value(interface),
                            "interface_redacted": True,
                        },
                    )
                    logger.info(f"✅ Brought interface {interface} up")
                except subprocess.CalledProcessError as e:
                    self._publish_observation(
                        stage="loader_attach_manager_interface_bring_up_failed",
                        operation="interface_bring_up",
                        status="failure",
                        source_mode="ip_link",
                        start=bring_up_start,
                        returncode=getattr(e, "returncode", None),
                        stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                        stderr=getattr(e, "stderr", None),
                        command=_redacted_command(cmd, redacted_indices=(4,)),
                        read_only=False,
                        error=e,
                        parsed_summary={
                            "interface_exists": True,
                            "interface_up_before": False,
                        },
                        extra={
                            "interface_hash": _hash_value(interface),
                            "interface_redacted": True,
                        },
                    )
                    raise EBPFAttachError(f"Failed to bring interface up: {e}")
        
        return True
    
    def attach_xdp(
        self, 
        program_path: str, 
        interface: str, 
        mode: EBPFAttachMode = EBPFAttachMode.SKB,
        program_id: Optional[str] = None
    ) -> bool:
        """
        Attach XDP program to interface.
        
        Tries modes in order: HW → DRV → SKB (fallback)
        
        Args:
            program_path: Path to pinned program or .o file
            interface: Network interface name
            mode: XDP attach mode
            program_id: Optional program ID for tracking
            
        Returns:
            True if attachment successful
            
        Raises:
            EBPFAttachError: If attachment fails
        """
        # Verify interface
        self.verify_interface(interface)
        
        # Determine modes to try
        modes_to_try = []
        if mode == EBPFAttachMode.HW:
            modes_to_try = ["offload", "drv", "skb"]
        elif mode == EBPFAttachMode.DRV:
            modes_to_try = ["drv", "skb"]
        else:
            modes_to_try = ["skb"]
        
        for xdp_mode in modes_to_try:
            try:
                # Use ip link to attach XDP program
                cmd = [
                    "ip", "link", "set", "dev", interface,
                    "xdp", "obj", str(program_path),
                    "sec", ".text",
                ]
                
                if xdp_mode != "skb":
                    cmd.extend(["mode", xdp_mode])
                
                attach_start = time.monotonic()
                result = subprocess.run(
                    cmd, check=True, capture_output=True, text=True, timeout=10
                )
                
                # Verify attachment
                verified = self._verify_xdp_attachment(interface)
                self._publish_observation(
                    stage=(
                        "loader_attach_manager_xdp_attach_succeeded"
                        if verified
                        else "loader_attach_manager_xdp_attach_verify_failed"
                    ),
                    operation="xdp_attach",
                    status="success" if verified else "failure",
                    source_mode="ip_link",
                    start=attach_start,
                    returncode=getattr(result, "returncode", 0),
                    stdout=getattr(result, "stdout", None),
                    stderr=getattr(result, "stderr", None),
                    command=_redacted_command(cmd, redacted_indices=(4, 7)),
                    read_only=False,
                    parsed_summary={"verified": verified, "xdp_mode": xdp_mode},
                    extra={
                        "interface_hash": _hash_value(interface),
                        "program_path_hash": _hash_value(program_path),
                        "program_id_hash": _hash_value(program_id),
                        "interface_redacted": True,
                        "program_path_redacted": True,
                        "program_id_redacted": True,
                    },
                )
                if verified:
                    logger.info(f"✅ XDP attached in {xdp_mode} mode to {interface}")
                    
                    # Track attachment
                    if interface not in self.attached_interfaces:
                        self.attached_interfaces[interface] = []
                    
                    self.attached_interfaces[interface].append({
                        "program_id": program_id,
                        "type": "xdp",
                        "mode": xdp_mode,
                        "attached_at": time.time(),
                    })
                    
                    return True
                    
            except subprocess.CalledProcessError as e:
                self._publish_observation(
                    stage="loader_attach_manager_xdp_attach_failed",
                    operation="xdp_attach",
                    status="failure",
                    source_mode="ip_link",
                    start=attach_start if "attach_start" in locals() else time.monotonic(),
                    returncode=getattr(e, "returncode", None),
                    stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                    stderr=getattr(e, "stderr", None),
                    command=_redacted_command(cmd, redacted_indices=(4, 7)),
                    read_only=False,
                    error=e,
                    parsed_summary={"verified": False, "xdp_mode": xdp_mode},
                    extra={
                        "interface_hash": _hash_value(interface),
                        "program_path_hash": _hash_value(program_path),
                        "program_id_hash": _hash_value(program_id),
                        "interface_redacted": True,
                        "program_path_redacted": True,
                        "program_id_redacted": True,
                    },
                )
                logger.debug(f"Failed to attach in {xdp_mode} mode: {e.stderr}")
                continue
            except subprocess.TimeoutExpired as e:
                self._publish_observation(
                    stage="loader_attach_manager_xdp_attach_timeout",
                    operation="xdp_attach",
                    status="failure",
                    source_mode="ip_link",
                    start=attach_start if "attach_start" in locals() else time.monotonic(),
                    stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                    stderr=getattr(e, "stderr", None),
                    command=_redacted_command(cmd, redacted_indices=(4, 7)),
                    read_only=False,
                    error=e,
                    parsed_summary={"verified": False, "xdp_mode": xdp_mode},
                    extra={
                        "interface_hash": _hash_value(interface),
                        "program_path_hash": _hash_value(program_path),
                        "program_id_hash": _hash_value(program_id),
                        "interface_redacted": True,
                        "program_path_redacted": True,
                        "program_id_redacted": True,
                    },
                )
                continue
        
        raise EBPFAttachError(
            f"Failed to attach XDP program to {interface} in any mode"
        )
    
    def attach_tc(
        self, 
        program_path: str, 
        interface: str,
        program_id: Optional[str] = None
    ) -> bool:
        """
        Attach TC program to interface (ingress).
        
        Args:
            program_path: Path to .o file
            interface: Network interface name
            program_id: Optional program ID for tracking
            
        Returns:
            True if attachment successful
            
        Raises:
            EBPFAttachError: If attachment fails
        """
        # Verify interface
        self.verify_interface(interface)
        
        try:
            # Create qdisc if not exists
            qdisc_cmd = ["tc", "qdisc", "add", "dev", interface, "clsact"]
            qdisc_start = time.monotonic()
            qdisc_result = safe_run(
                qdisc_cmd,
                check=False,  # May already exist
                capture_output=True,
                timeout=5,
            )
            self._publish_observation(
                stage=(
                    "loader_attach_manager_tc_qdisc_succeeded"
                    if getattr(qdisc_result, "returncode", 0) == 0
                    else "loader_attach_manager_tc_qdisc_failed"
                ),
                operation="tc_qdisc_add",
                status=(
                    "success"
                    if getattr(qdisc_result, "returncode", 0) == 0
                    else "failure"
                ),
                source_mode="tc",
                start=qdisc_start,
                returncode=getattr(qdisc_result, "returncode", None),
                stdout=getattr(qdisc_result, "stdout", None),
                stderr=getattr(qdisc_result, "stderr", None),
                command=_redacted_command(qdisc_cmd, redacted_indices=(4,)),
                read_only=False,
                parsed_summary={"qdisc": "clsact"},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            
            # Attach TC program
            cmd = [
                "tc", "filter", "add", "dev", interface,
                "ingress", "bpf", "da", "obj", str(program_path),
                "sec", ".text",
            ]
            
            attach_start = time.monotonic()
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, timeout=10
            )
            self._publish_observation(
                stage="loader_attach_manager_tc_attach_succeeded",
                operation="tc_attach",
                status="success",
                source_mode="tc",
                start=attach_start,
                returncode=getattr(result, "returncode", 0),
                stdout=getattr(result, "stdout", None),
                stderr=getattr(result, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4, 9)),
                read_only=False,
                parsed_summary={"direction": "ingress"},
                extra={
                    "interface_hash": _hash_value(interface),
                    "program_path_hash": _hash_value(program_path),
                    "program_id_hash": _hash_value(program_id),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                    "program_id_redacted": True,
                },
            )
            
            logger.info(f"✅ TC program attached to {interface}")
            
            # Track attachment
            if interface not in self.attached_interfaces:
                self.attached_interfaces[interface] = []
            
            self.attached_interfaces[interface].append({
                "program_id": program_id,
                "type": "tc",
                "attached_at": time.time(),
            })
            
            return True
            
        except subprocess.CalledProcessError as e:
            failed_cmd = cmd if "cmd" in locals() else qdisc_cmd
            redacted_indices = (4, 9) if "cmd" in locals() else (4,)
            self._publish_observation(
                stage="loader_attach_manager_tc_attach_failed",
                operation="tc_attach",
                status="failure",
                source_mode="tc",
                start=attach_start if "attach_start" in locals() else time.monotonic(),
                returncode=getattr(e, "returncode", None),
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                command=_redacted_command(failed_cmd, redacted_indices=redacted_indices),
                read_only=False,
                error=e,
                parsed_summary={"direction": "ingress"},
                extra={
                    "interface_hash": _hash_value(interface),
                    "program_path_hash": _hash_value(program_path),
                    "program_id_hash": _hash_value(program_id),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                    "program_id_redacted": True,
                },
            )
            raise EBPFAttachError(f"Failed to attach TC program: {e.stderr}")
    
    def detach_xdp(self, interface: str) -> bool:
        """
        Detach XDP program from interface.
        
        Args:
            interface: Network interface name
            
        Returns:
            True if detachment successful
        """
        cmd = ["ip", "link", "set", "dev", interface, "xdp", "off"]
        detach_start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._publish_observation(
                stage="loader_attach_manager_xdp_detach_succeeded",
                operation="xdp_detach",
                status="success",
                source_mode="ip_link",
                start=detach_start,
                returncode=getattr(result, "returncode", 0),
                stdout=getattr(result, "stdout", None),
                stderr=getattr(result, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                read_only=False,
                parsed_summary={"detached": True},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            
            logger.info(f"✅ XDP detached from {interface}")
            return True
            
        except subprocess.CalledProcessError as e:
            self._publish_observation(
                stage="loader_attach_manager_xdp_detach_failed",
                operation="xdp_detach",
                status="failure",
                source_mode="ip_link",
                start=detach_start,
                returncode=getattr(e, "returncode", None),
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                read_only=False,
                error=e,
                parsed_summary={"detached": False},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            raise EBPFAttachError(f"Failed to detach XDP: {e.stderr}")
    
    def detach_tc(self, interface: str) -> bool:
        """
        Detach TC program from interface.
        
        Args:
            interface: Network interface name
            
        Returns:
            True if detachment successful
        """
        cmd = ["tc", "filter", "del", "dev", interface, "ingress"]
        detach_start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._publish_observation(
                stage="loader_attach_manager_tc_detach_succeeded",
                operation="tc_detach",
                status="success",
                source_mode="tc",
                start=detach_start,
                returncode=getattr(result, "returncode", 0),
                stdout=getattr(result, "stdout", None),
                stderr=getattr(result, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                read_only=False,
                parsed_summary={"detached": True, "direction": "ingress"},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            
            logger.info(f"✅ TC detached from {interface}")
            return True
            
        except subprocess.CalledProcessError as e:
            self._publish_observation(
                stage="loader_attach_manager_tc_detach_failed",
                operation="tc_detach",
                status="failure",
                source_mode="tc",
                start=detach_start,
                returncode=getattr(e, "returncode", None),
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                read_only=False,
                error=e,
                parsed_summary={"detached": False, "direction": "ingress"},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            raise EBPFAttachError(f"Failed to detach TC: {e.stderr}")
    
    def _verify_xdp_attachment(self, interface: str) -> bool:
        """Verify XDP program is attached to interface."""
        cmd = ["ip", "link", "show", "dev", interface]
        verify_start = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Check for xdp attachment
            output = result.stdout.lower()
            verified = "xdp" in output and "xdp off" not in output
            self._publish_observation(
                stage=(
                    "loader_attach_manager_xdp_verify_succeeded"
                    if verified
                    else "loader_attach_manager_xdp_verify_not_observed"
                ),
                operation="verify_xdp_attachment",
                status="success" if verified else "empty",
                source_mode="ip_link",
                start=verify_start,
                returncode=getattr(result, "returncode", 0),
                stdout=result.stdout,
                stderr=getattr(result, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                parsed_summary={"verified": verified, "xdp_off_seen": "xdp off" in output},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            return verified
            
        except subprocess.CalledProcessError as e:
            self._publish_observation(
                stage="loader_attach_manager_xdp_verify_failed",
                operation="verify_xdp_attachment",
                status="failure",
                source_mode="ip_link",
                start=verify_start,
                returncode=getattr(e, "returncode", None),
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                command=_redacted_command(cmd, redacted_indices=(4,)),
                error=e,
                parsed_summary={"verified": False},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                },
            )
            return False
    
    def get_interface_attachments(self, interface: str) -> List[Dict]:
        """Get all attachments for an interface."""
        return self.attached_interfaces.get(interface, [])
    
    def remove_attachment(self, interface: str, program_id: str) -> bool:
        """Remove attachment tracking for a program."""
        if interface not in self.attached_interfaces:
            return False
        
        attachments = self.attached_interfaces[interface]
        for i, att in enumerate(attachments):
            if att.get("program_id") == program_id:
                attachments.pop(i)
                if not attachments:
                    del self.attached_interfaces[interface]
                return True
        
        return False

