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

import logging
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


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

    def __init__(self):
        self.attached_programs = {}  # interface -> program_info
        logger.info("XDP Hook manager initialized")

    def _check_interface_exists(self, interface: str) -> bool:
        """Check if network interface exists."""
        interface_path = Path(f"/sys/class/net/{interface}")
        return interface_path.exists()

    def _check_driver_support(self, interface: str, mode: str) -> bool:
        """
        Check if driver supports requested XDP mode.

        Returns:
            True if mode is supported or cannot be determined
        """
        if mode == "generic":
            return True  # Generic mode always works

        # For native/offload, check driver features
        # This is a simplified check - real implementation would parse ethtool -k
        try:
            # Check if interface is up
            operstate_path = Path(f"/sys/class/net/{interface}/operstate")
            if operstate_path.exists():
                operstate = operstate_path.read_text().strip()
                if operstate != "up":
                    logger.debug(
                        f"Interface {interface} is not up, may affect mode support"
                    )
        except Exception:
            pass

        return True  # Assume supported, let kernel reject if not

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
        if interface in self.attached_programs:
            logger.warning(f"XDP program already attached to {interface}")
            return False

        if not self._check_interface_exists(interface):
            logger.error(f"Network interface not found: {interface}")
            return False

        # Verify program file exists (if not a pinned path)
        if not program_path.startswith("/sys/fs/bpf/"):
            program_file = Path(program_path)
            if not program_file.exists():
                logger.error(f"XDP program not found: {program_path}")
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
            # Map mode to ip link command flag
            mode_flag = {
                "generic": "xdp",
                "native": "xdpdrv",
                "offload": "xdpoffload",
            }[attempt_mode]

            try:
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

                if result.returncode == 0:
                    # Verify attachment
                    verify_cmd = ["ip", "link", "show", "dev", interface]
                    verify_result = subprocess.run(
                        verify_cmd, capture_output=True, text=True, timeout=2
                    )

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
                        return True
                    else:
                        logger.debug(
                            f"Attachment succeeded but verification failed for {interface}"
                        )
                else:
                    logger.debug(
                        f"Failed to attach in {attempt_mode} mode: {result.stderr.strip()}"
                    )
                    continue

            except subprocess.TimeoutExpired:
                logger.warning(
                    f"ip link command timed out for {interface} in {attempt_mode} mode"
                )
                continue
            except Exception as e:
                logger.warning(f"Error attaching XDP in {attempt_mode} mode: {e}")
                continue

        logger.error(f"❌ Failed to attach XDP program to {interface} in any mode")
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
        if interface not in self.attached_programs:
            logger.warning(f"No XDP program attached to {interface}")
            return False

        if not self._check_interface_exists(interface):
            logger.warning(
                f"Interface {interface} does not exist, removing from tracking"
            )
            del self.attached_programs[interface]
            return True

        try:
            # Execute: ip link set dev {interface} xdp off
            cmd = ["ip", "link", "set", "dev", interface, "xdp", "off"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                # Verify detachment
                verify_cmd = ["ip", "link", "show", "dev", interface]
                verify_result = subprocess.run(
                    verify_cmd, capture_output=True, text=True, timeout=2
                )

                if "xdp" not in verify_result.stdout.lower():
                    del self.attached_programs[interface]
                    logger.info(f"✅ XDP program detached from {interface}")
                    return True
                else:
                    logger.warning(
                        f"Detachment command succeeded but XDP still present on {interface}"
                    )
                    # Still remove from tracking
                    del self.attached_programs[interface]
                    return False
            else:
                logger.error(f"Failed to detach XDP: {result.stderr.strip()}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"ip link detach command timed out for {interface}")
            return False
        except Exception as e:
            logger.error(f"Error detaching XDP: {e}")
            return False

    def get_attached_program(self, interface: str) -> Optional[dict]:
        """Get info about XDP program attached to interface."""
        return self.attached_programs.get(interface)

    def list_attached_interfaces(self) -> list:
        """Return list of interfaces with XDP programs attached."""
        return list(self.attached_programs.keys())
