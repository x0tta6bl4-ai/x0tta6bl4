"""
eBPF Attach Manager - Interface attachment management

Handles:
- XDP attachment (SKB/DRV/HW modes)
- TC attachment (ingress/egress)
- Attachment verification
"""

import logging
import subprocess
import time
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from src.core.subprocess_validator import safe_run

logger = logging.getLogger(__name__)


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
    
    def __init__(self):
        """Initialize the attach manager."""
        self.attached_interfaces: Dict[str, List[Dict]] = {}
        logger.info("EBPFAttachManager initialized")
    
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
            raise EBPFAttachError(f"Network interface not found: {interface}")
        
        # Check if interface is up
        operstate_path = interface_path / "operstate"
        if operstate_path.exists():
            operstate = operstate_path.read_text().strip()
            if operstate != "up":
                logger.warning(f"Interface {interface} is not up (state: {operstate})")
                # Try to bring interface up
                try:
                    safe_run(
                        ["ip", "link", "set", "dev", interface, "up"],
                        check=True,
                        capture_output=True,
                        timeout=5,
                    )
                    logger.info(f"✅ Brought interface {interface} up")
                except subprocess.CalledProcessError as e:
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
                
                result = subprocess.run(
                    cmd, check=True, capture_output=True, text=True, timeout=10
                )
                
                # Verify attachment
                if self._verify_xdp_attachment(interface):
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
                logger.debug(f"Failed to attach in {xdp_mode} mode: {e.stderr}")
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
            safe_run(
                ["tc", "qdisc", "add", "dev", interface, "clsact"],
                check=False,  # May already exist
                capture_output=True,
                timeout=5,
            )
            
            # Attach TC program
            cmd = [
                "tc", "filter", "add", "dev", interface,
                "ingress", "bpf", "da", "obj", str(program_path),
                "sec", ".text",
            ]
            
            result = subprocess.run(
                cmd, check=True, capture_output=True, text=True, timeout=10
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
            raise EBPFAttachError(f"Failed to attach TC program: {e.stderr}")
    
    def detach_xdp(self, interface: str) -> bool:
        """
        Detach XDP program from interface.
        
        Args:
            interface: Network interface name
            
        Returns:
            True if detachment successful
        """
        try:
            result = subprocess.run(
                ["ip", "link", "set", "dev", interface, "xdp", "off"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            logger.info(f"✅ XDP detached from {interface}")
            return True
            
        except subprocess.CalledProcessError as e:
            raise EBPFAttachError(f"Failed to detach XDP: {e.stderr}")
    
    def detach_tc(self, interface: str) -> bool:
        """
        Detach TC program from interface.
        
        Args:
            interface: Network interface name
            
        Returns:
            True if detachment successful
        """
        try:
            result = subprocess.run(
                ["tc", "filter", "del", "dev", interface, "ingress"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            logger.info(f"✅ TC detached from {interface}")
            return True
            
        except subprocess.CalledProcessError as e:
            raise EBPFAttachError(f"Failed to detach TC: {e.stderr}")
    
    def _verify_xdp_attachment(self, interface: str) -> bool:
        """Verify XDP program is attached to interface."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", "dev", interface],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Check for xdp attachment
            output = result.stdout.lower()
            return "xdp" in output and "xdp off" not in output
            
        except subprocess.CalledProcessError:
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
