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
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class XDPAction(Enum):
    """XDP program return codes"""
    ABORTED = 0  # Error - drop packet and trigger tracepoint
    DROP = 1     # Drop packet (fastest action)
    PASS = 2     # Pass packet to normal network stack
    TX = 3       # Transmit packet back out same interface
    REDIRECT = 4 # Redirect packet to another interface


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
    
    def attach(
        self, 
        interface: str, 
        program_path: str,
        mode: str = "generic"
    ) -> bool:
        """
        Attach XDP program to network interface.
        
        Args:
            interface: Network interface name (e.g., "eth0")
            program_path: Path to compiled XDP program (.o file)
            mode: Attach mode - "generic", "native", or "offload"
        
        Returns:
            True if attachment successful
        
        TODO:
        - Execute: ip link set dev {interface} xdp obj {program_path} sec xdp
        - For native mode: ip link set dev {interface} xdpdrv obj {program_path}
        - For offload: ip link set dev {interface} xdpoffload obj {program_path}
        - Verify driver supports requested mode
        - Handle fallback: try offload → native → generic
        """
        if interface in self.attached_programs:
            logger.warning(f"XDP program already attached to {interface}")
            return False
        
        # Placeholder: actual implementation would use pyroute2 or subprocess
        self.attached_programs[interface] = {
            "program": program_path,
            "mode": mode
        }
        
        logger.info(f"Attached XDP program {program_path} to {interface} (mode: {mode})")
        return True
    
    def detach(self, interface: str) -> bool:
        """
        Detach XDP program from interface.
        
        Args:
            interface: Network interface name
        
        Returns:
            True if detachment successful
        
        TODO:
        - Execute: ip link set dev {interface} xdp off
        """
        if interface not in self.attached_programs:
            logger.warning(f"No XDP program attached to {interface}")
            return False
        
        del self.attached_programs[interface]
        logger.info(f"Detached XDP program from {interface}")
        return True
    
    def get_attached_program(self, interface: str) -> Optional[dict]:
        """Get info about XDP program attached to interface."""
        return self.attached_programs.get(interface)
    
    def list_attached_interfaces(self) -> list:
        """Return list of interfaces with XDP programs attached."""
        return list(self.attached_programs.keys())
