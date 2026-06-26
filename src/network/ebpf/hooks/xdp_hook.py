"""
XDP Hook Implementation - Fast packet processing at driver level

XDP (eXpress Data Path) provides the fastest packet processing path in Linux,
running eBPF programs at the network driver level before sk_buff allocation.

Use cases:
- DDoS mitigation (drop packets early)
- Load balancing
- Packet filtering
- Traffic sampling
"""
from __future__ import annotations

import logging
import hashlib
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_XDP_MODE_FLAGS = {
    "generic": "xdp",
    "native": "xdpdrv",
    "offload": "xdpoffload",
}


class XDPAction(Enum):
    """XDP program return codes"""

    ABORTED = 0  # Error - drop packet and trigger tracepoint
    DROP = 1  # Drop packet (fastest action)
    PASS = 2  # Pass packet to normal network stack
    TX = 3  # Transmit packet back out same interface
    REDIRECT = 4  # Redirect packet to another interface


class XDPHook:
    """
    Manages XDP eBPF program attachment to network interfaces.

    XDP programs run in 3 modes:
    - Generic (SKB): Slowest, works on any driver
    - Native (DRV): Fast, requires driver support
    - Offload (HW): Fastest, runs on NIC hardware

    Example:
        >>> hook = XDPHook()
        >>> hook.attach("eth0", "xdp_firewall.o", mode="native")
        >>> hook.detach("eth0")
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.attached_programs = {}  # interface -> program_info
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_XDP_HOOK_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("monitoring", "zero-trust", "ops"),
            extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        logger.info("XDP Hook manager initialized")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = EventBus(project_root=self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize XDP hook EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                EBPF_XDP_HOOK_SERVICE_NAME,
            )
            coach = AgentThinkingCoach(
                agent_id=self.source_agent,
                role="security",
                capabilities=("monitoring", "zero-trust", "ops"),
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
            "task_type": "ebpf_xdp_hook_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local XDP hook evidence, redacted command shapes, "
                "hashed interface/program selectors, return codes, counts, and "
                "status; do not expose raw interface names, program paths, stdout, "
                "stderr, or sysfs paths."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose XDP hook thinking state without task secrets."""

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
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "command_present": bool(command),
                "command_length": len(command or []),
                "command_redacted": bool(command),
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
                "output_redacted": True,
            },
        )
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.hooks.xdp_hook",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:xdp_hook:{operation}",
            "service_name": self.source_agent,
            "layer": EBPF_XDP_HOOK_LAYER,
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
            "output": _bounded_output_metadata(stdout, stderr),
            "thinking": thinking,
            "payloads_redacted": True,
            "claim_boundary": EBPF_XDP_HOOK_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish XDP hook observation")
            return None

    def _check_interface_exists(self, interface: str) -> bool:
        """Check if network interface exists."""
        check_start = time.monotonic()
        interface_path = Path(f"/sys/class/net/{interface}")
        exists = interface_path.exists()
        self._publish_observation(
            stage="xdp_interface_exists_checked",
            operation="check_interface_exists",
            status="success" if exists else "failure",
            source_mode="sysfs",
            start=check_start,
            parsed_summary={"interface_exists": exists},
            extra={
                "interface_hash": _hash_value(interface),
                "interface_path_hash": _hash_value(interface_path),
                "interface_redacted": True,
            },
        )
        return exists

    def _check_driver_support(self, interface: str, mode: str) -> bool:
        """
        Check if driver supports requested XDP mode.

        Returns:
            True if the requested mode can be attempted
        """
        if mode not in _XDP_MODE_FLAGS:
            logger.error("Unsupported XDP mode requested: %s", mode)
            return False

        if mode == "generic":
            self._publish_observation(
                stage="xdp_driver_support_generic_allowed",
                operation="check_driver_support",
                status="success",
                source_mode="static_capability",
                start=check_start,
                parsed_summary={"supported": True, "mode": mode},
                extra={
                    "interface_hash": _hash_value(interface),
                    "interface_redacted": True,
                    "required_flag": _XDP_MODE_FLAGS[mode],
                },
            )
            return True  # Generic mode always works

        if not self._check_interface_exists(interface):
            logger.error("Cannot check XDP support, interface not found: %s", interface)
            return False

        # For native/offload, first verify that the installed iproute2 supports
        # the required mode flag. The actual driver support is still confirmed by
        # the kernel attach attempt below.
        try:
            operstate_path = Path(f"/sys/class/net/{interface}/operstate")
            if operstate_path.exists():
                operstate_present = True
                operstate = operstate_path.read_text().strip()
                operstate_up = operstate == "up"
                if operstate != "up":
                    logger.debug(
                        f"Interface {interface} is not up, may affect mode support"
                    )
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["ip", "link", "help"],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception as e:
            logger.warning("Cannot verify ip link XDP mode support: %s", e)
            return False

        help_text = f"{result.stdout}\n{result.stderr}".lower()
        required_flag = _XDP_MODE_FLAGS[mode]
        if required_flag not in help_text:
            logger.debug(
                "ip link does not advertise %s support for %s mode",
                required_flag,
                mode,
            )
            return False

        return True

    def attach(self, interface: str, program_path: str, mode: str = "generic") -> bool:
        """
        Attach XDP program to network interface.

        Implements:
        - Real attachment via ip link commands
        - Auto-detect best available mode (HW → DRV → SKB)
        - Fallback if requested mode not supported

        Args:
            interface: Network interface name (e.g., "eth0")
            program_path: Path to compiled XDP program (.o file) or pinned path
            mode: Attach mode - "generic", "native", or "offload"

        Returns:
            True if attachment successful
        """
        op_start = time.monotonic()
        program_is_pinned = program_path.startswith("/sys/fs/bpf/")
        selector_metadata = {
            "interface_hash": _hash_value(interface),
            "program_path_hash": _hash_value(program_path),
            "interface_redacted": True,
            "program_path_redacted": True,
            "program_path_pinned": program_is_pinned,
            "requested_mode": mode,
        }

        if interface in self.attached_programs:
            logger.warning(f"XDP program already attached to {interface}")
            self._publish_observation(
                stage="xdp_attach_already_tracked",
                operation="attach",
                status="failure",
                source_mode="memory",
                start=op_start,
                read_only=False,
                parsed_summary={"attached": False, "reason": "already_tracked"},
                extra=selector_metadata,
            )
            return False

        if not self._check_interface_exists(interface):
            logger.error(f"Network interface not found: {interface}")
            self._publish_observation(
                stage="xdp_attach_interface_missing",
                operation="attach",
                status="failure",
                source_mode="sysfs",
                start=op_start,
                read_only=False,
                parsed_summary={"attached": False, "reason": "interface_missing"},
                extra=selector_metadata,
            )
            return False

        # Verify program file exists (if not a pinned path)
        if not program_is_pinned:
            program_file = Path(program_path)
            if not program_file.exists():
                logger.error(f"XDP program not found: {program_path}")
                self._publish_observation(
                    stage="xdp_attach_program_missing",
                    operation="attach",
                    status="failure",
                    source_mode="filesystem",
                    start=op_start,
                    read_only=False,
                    parsed_summary={"attached": False, "reason": "program_missing"},
                    extra=selector_metadata,
                )
                return False

        # Try modes in order: requested → HW → DRV → generic
        mode_order = [mode]
        if mode != "offload":
            mode_order.append("offload")
        if mode != "native":
            mode_order.append("native")
        if mode != "generic":
            mode_order.append("generic")

        # Remove duplicates while preserving order
        mode_order = list(dict.fromkeys(mode_order))

        for attempt_mode in mode_order:
            if not self._check_driver_support(interface, attempt_mode):
                logger.debug(
                    "Skipping XDP %s mode on %s: support check failed",
                    attempt_mode,
                    interface,
                )
                continue

            # Map mode to ip link command flag
            mode_flag = _XDP_MODE_FLAGS[attempt_mode]

            try:
                command_start = time.monotonic()
                # Execute: ip link set dev {interface} {mode_flag} obj {program_path} sec xdp
                cmd = [
                    "ip",
                    "link",
                    "set",
                    "dev",
                    interface,
                    mode_flag,
                    "obj",
                    program_path,
                    "sec",
                    "xdp",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                command_metadata = _redacted_command(cmd, redacted_indices=(4, 7))

                if result.returncode == 0:
                    self._publish_observation(
                        stage="xdp_attach_command_succeeded",
                        operation="attach",
                        status="success",
                        source_mode="ip-link",
                        start=command_start,
                        command=command_metadata,
                        returncode=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        read_only=False,
                        parsed_summary={
                            "attached": False,
                            "attempt_mode": attempt_mode,
                            "mode_flag": mode_flag,
                            "verification_pending": True,
                        },
                        extra=selector_metadata,
                    )
                    # Verify attachment
                    verify_start = time.monotonic()
                    verify_cmd = ["ip", "link", "show", "dev", interface]
                    try:
                        verify_result = subprocess.run(
                            verify_cmd, capture_output=True, text=True, timeout=2
                        )
                    except subprocess.TimeoutExpired as e:
                        self._publish_observation(
                            stage="xdp_attach_verify_timeout",
                            operation="attach_verify",
                            status="failure",
                            source_mode="ip-link",
                            start=verify_start,
                            command=[
                                "ip",
                                "link",
                                "show",
                                "dev",
                                "[redacted]",
                            ],
                            stdout=getattr(e, "stdout", None)
                            or getattr(e, "output", None),
                            stderr=getattr(e, "stderr", None),
                            read_only=True,
                            error=e,
                            parsed_summary={
                                "attached": False,
                                "attempt_mode": attempt_mode,
                                "mode_flag": mode_flag,
                            },
                            extra=selector_metadata,
                        )
                        continue
                    except Exception as e:
                        self._publish_observation(
                            stage="xdp_attach_verify_error",
                            operation="attach_verify",
                            status="failure",
                            source_mode="ip-link",
                            start=verify_start,
                            command=[
                                "ip",
                                "link",
                                "show",
                                "dev",
                                "[redacted]",
                            ],
                            read_only=True,
                            error=e,
                            parsed_summary={
                                "attached": False,
                                "attempt_mode": attempt_mode,
                                "mode_flag": mode_flag,
                            },
                            extra=selector_metadata,
                        )
                        continue

                    if "xdp" in verify_result.stdout.lower():
                        self.attached_programs[interface] = {
                            "program": program_path,
                            "mode": attempt_mode,
                            "actual_mode": attempt_mode,
                        }
                        logger.info(
                            f"✅ XDP program attached to {interface} "
                            f"(requested: {mode}, actual: {attempt_mode})"
                        )
                        self._publish_observation(
                            stage="xdp_attach_verify_succeeded",
                            operation="attach_verify",
                            status="success",
                            source_mode="ip-link",
                            start=verify_start,
                            command=_redacted_command(verify_cmd, redacted_indices=(4,)),
                            returncode=verify_result.returncode,
                            stdout=verify_result.stdout,
                            stderr=verify_result.stderr,
                            read_only=True,
                            parsed_summary={
                                "attached": True,
                                "requested_mode": mode,
                                "actual_mode": attempt_mode,
                                "mode_flag": mode_flag,
                            },
                            extra=selector_metadata,
                        )
                        return True
                    else:
                        logger.debug(
                            f"Attachment succeeded but verification failed for {interface}"
                        )
                        self._publish_observation(
                            stage="xdp_attach_verify_failed",
                            operation="attach_verify",
                            status="failure",
                            source_mode="ip-link",
                            start=verify_start,
                            command=_redacted_command(verify_cmd, redacted_indices=(4,)),
                            returncode=verify_result.returncode,
                            stdout=verify_result.stdout,
                            stderr=verify_result.stderr,
                            read_only=True,
                            parsed_summary={
                                "attached": False,
                                "attempt_mode": attempt_mode,
                                "mode_flag": mode_flag,
                            },
                            extra=selector_metadata,
                        )
                else:
                    logger.debug(
                        f"Failed to attach in {attempt_mode} mode: {result.stderr.strip()}"
                    )
                    self._publish_observation(
                        stage="xdp_attach_command_failed",
                        operation="attach",
                        status="failure",
                        source_mode="ip-link",
                        start=command_start,
                        command=command_metadata,
                        returncode=result.returncode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        read_only=False,
                        parsed_summary={
                            "attached": False,
                            "attempt_mode": attempt_mode,
                            "mode_flag": mode_flag,
                        },
                        extra=selector_metadata,
                    )
                    continue

            except subprocess.TimeoutExpired as e:
                self._publish_observation(
                    stage="xdp_attach_command_timeout",
                    operation="attach",
                    status="failure",
                    source_mode="ip-link",
                    start=command_start,
                    command=[
                        "ip",
                        "link",
                        "set",
                        "dev",
                        "[redacted]",
                        mode_flag,
                        "obj",
                        "[redacted]",
                        "sec",
                        "xdp",
                    ],
                    stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                    stderr=getattr(e, "stderr", None),
                    read_only=False,
                    error=e,
                    parsed_summary={
                        "attached": False,
                        "attempt_mode": attempt_mode,
                        "mode_flag": mode_flag,
                    },
                    extra=selector_metadata,
                )
                logger.warning(
                    f"ip link command timed out for {interface} in {attempt_mode} mode"
                )
                continue
            except Exception as e:
                self._publish_observation(
                    stage="xdp_attach_command_error",
                    operation="attach",
                    status="failure",
                    source_mode="ip-link",
                    start=command_start,
                    command=[
                        "ip",
                        "link",
                        "set",
                        "dev",
                        "[redacted]",
                        mode_flag,
                        "obj",
                        "[redacted]",
                        "sec",
                        "xdp",
                    ],
                    read_only=False,
                    error=e,
                    parsed_summary={
                        "attached": False,
                        "attempt_mode": attempt_mode,
                        "mode_flag": mode_flag,
                    },
                    extra=selector_metadata,
                )
                logger.warning(f"Error attaching XDP in {attempt_mode} mode: {e}")
                continue

        logger.error(f"❌ Failed to attach XDP program to {interface} in any mode")
        self._publish_observation(
            stage="xdp_attach_all_modes_failed",
            operation="attach",
            status="failure",
            source_mode="ip-link",
            start=op_start,
            read_only=False,
            parsed_summary={
                "attached": False,
                "attempted_modes": mode_order,
            },
            extra=selector_metadata,
        )
        return False

    def detach(self, interface: str) -> bool:
        """
        Detach XDP program from interface.

        Implements:
        - Real detachment via ip link set dev {interface} xdp off
        - Verification of detachment

        Args:
            interface: Network interface name

        Returns:
            True if detachment successful
        """
        op_start = time.monotonic()
        selector_metadata = {
            "interface_hash": _hash_value(interface),
            "interface_redacted": True,
        }

        if interface not in self.attached_programs:
            logger.warning(f"No XDP program attached to {interface}")
            self._publish_observation(
                stage="xdp_detach_not_tracked",
                operation="detach",
                status="failure",
                source_mode="memory",
                start=op_start,
                read_only=False,
                parsed_summary={"detached": False, "reason": "not_tracked"},
                extra=selector_metadata,
            )
            return False

        if not self._check_interface_exists(interface):
            logger.warning(
                f"Interface {interface} does not exist, removing from tracking"
            )
            del self.attached_programs[interface]
            self._publish_observation(
                stage="xdp_detach_interface_missing_removed_tracking",
                operation="detach",
                status="success",
                source_mode="sysfs",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "detached": True,
                    "reason": "interface_missing_removed_tracking",
                },
                extra=selector_metadata,
            )
            return True

        try:
            command_start = time.monotonic()
            # Execute: ip link set dev {interface} xdp off
            cmd = ["ip", "link", "set", "dev", interface, "xdp", "off"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            command_metadata = _redacted_command(cmd, redacted_indices=(4,))

            if result.returncode == 0:
                self._publish_observation(
                    stage="xdp_detach_command_succeeded",
                    operation="detach",
                    status="success",
                    source_mode="ip-link",
                    start=command_start,
                    command=command_metadata,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    read_only=False,
                    parsed_summary={
                        "detached": False,
                        "verification_pending": True,
                    },
                    extra=selector_metadata,
                )
                # Verify detachment
                verify_start = time.monotonic()
                verify_cmd = ["ip", "link", "show", "dev", interface]
                try:
                    verify_result = subprocess.run(
                        verify_cmd, capture_output=True, text=True, timeout=2
                    )
                except subprocess.TimeoutExpired as e:
                    self._publish_observation(
                        stage="xdp_detach_verify_timeout",
                        operation="detach_verify",
                        status="failure",
                        source_mode="ip-link",
                        start=verify_start,
                        command=[
                            "ip",
                            "link",
                            "show",
                            "dev",
                            "[redacted]",
                        ],
                        stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                        stderr=getattr(e, "stderr", None),
                        read_only=True,
                        error=e,
                        parsed_summary={"detached": False},
                        extra=selector_metadata,
                    )
                    return False
                except Exception as e:
                    self._publish_observation(
                        stage="xdp_detach_verify_error",
                        operation="detach_verify",
                        status="failure",
                        source_mode="ip-link",
                        start=verify_start,
                        command=[
                            "ip",
                            "link",
                            "show",
                            "dev",
                            "[redacted]",
                        ],
                        read_only=True,
                        error=e,
                        parsed_summary={"detached": False},
                        extra=selector_metadata,
                    )
                    return False

                if "xdp" not in verify_result.stdout.lower():
                    del self.attached_programs[interface]
                    logger.info(f"✅ XDP program detached from {interface}")
                    self._publish_observation(
                        stage="xdp_detach_verify_succeeded",
                        operation="detach_verify",
                        status="success",
                        source_mode="ip-link",
                        start=verify_start,
                        command=_redacted_command(verify_cmd, redacted_indices=(4,)),
                        returncode=verify_result.returncode,
                        stdout=verify_result.stdout,
                        stderr=verify_result.stderr,
                        read_only=True,
                        parsed_summary={"detached": True},
                        extra=selector_metadata,
                    )
                    return True
                else:
                    logger.warning(
                        f"Detachment command succeeded but XDP still present on {interface}"
                    )
                    # Still remove from tracking
                    del self.attached_programs[interface]
                    self._publish_observation(
                        stage="xdp_detach_verify_failed",
                        operation="detach_verify",
                        status="failure",
                        source_mode="ip-link",
                        start=verify_start,
                        command=_redacted_command(verify_cmd, redacted_indices=(4,)),
                        returncode=verify_result.returncode,
                        stdout=verify_result.stdout,
                        stderr=verify_result.stderr,
                        read_only=True,
                        parsed_summary={"detached": False},
                        extra=selector_metadata,
                    )
                    return False
            else:
                logger.error(f"Failed to detach XDP: {result.stderr.strip()}")
                self._publish_observation(
                    stage="xdp_detach_command_failed",
                    operation="detach",
                    status="failure",
                    source_mode="ip-link",
                    start=command_start,
                    command=command_metadata,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    read_only=False,
                    parsed_summary={"detached": False},
                    extra=selector_metadata,
                )
                return False

        except subprocess.TimeoutExpired as e:
            self._publish_observation(
                stage="xdp_detach_command_timeout",
                operation="detach",
                status="failure",
                source_mode="ip-link",
                start=command_start,
                command=[
                    "ip",
                    "link",
                    "set",
                    "dev",
                    "[redacted]",
                    "xdp",
                    "off",
                ],
                stdout=getattr(e, "stdout", None) or getattr(e, "output", None),
                stderr=getattr(e, "stderr", None),
                read_only=False,
                error=e,
                parsed_summary={"detached": False},
                extra=selector_metadata,
            )
            logger.error(f"ip link detach command timed out for {interface}")
            return False
        except Exception as e:
            self._publish_observation(
                stage="xdp_detach_command_error",
                operation="detach",
                status="failure",
                source_mode="ip-link",
                start=command_start,
                command=[
                    "ip",
                    "link",
                    "set",
                    "dev",
                    "[redacted]",
                    "xdp",
                    "off",
                ],
                read_only=False,
                error=e,
                parsed_summary={"detached": False},
                extra=selector_metadata,
            )
            logger.error(f"Error detaching XDP: {e}")
            return False

    def get_attached_program(self, interface: str) -> Optional[dict]:
        """Get info about XDP program attached to interface."""
        return self.attached_programs.get(interface)

    def list_attached_interfaces(self) -> list:
        """Return list of interfaces with XDP programs attached."""
        return list(self.attached_programs.keys())

