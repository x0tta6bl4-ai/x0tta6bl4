"""
eBPF Program Loader - Core Implementation (P0 Priority)

This module provides the foundational interface for loading and managing
eBPF programs in the x0tta6bl4 decentralized mesh network.

Key features:
- Load eBPF bytecode from .o files or memory
- Attach programs to network interfaces (XDP, TC, etc.)
- Validate program safety and resource limits
- Handle program lifecycle (load → attach → detach → unload)

References:
- BCC/bpftool for Linux eBPF integration
- Cilium's eBPF library patterns
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


class EBPFProgramType(Enum):
    """Supported eBPF program types for network monitoring"""
    XDP = "xdp"  # eXpress Data Path - fastest path for packet processing
    TC = "tc"    # Traffic Control - classifier/action programs
    CGROUP_SKB = "cgroup_skb"  # Socket buffer control
    SOCKET_FILTER = "socket_filter"  # Classic socket filtering


class EBPFAttachMode(Enum):
    """XDP attachment modes"""
    SKB = "skb"        # Generic mode (slowest, works everywhere)
    DRV = "drv"        # Driver mode (fast, requires driver support)
    HW = "hw"          # Hardware offload (fastest, rare support)


class EBPFLoadError(Exception):
    """Raised when eBPF program loading fails"""
    pass


class EBPFAttachError(Exception):
    """Raised when attaching eBPF program to interface fails"""
    pass


class EBPFLoader:
    """
    Core eBPF program loader and lifecycle manager.
    
    This class provides a high-level interface for:
    1. Loading compiled eBPF programs (.o files)
    2. Validating program bytecode and maps
    3. Attaching programs to network interfaces
    4. Managing program lifecycle
    
    Example:
        >>> loader = EBPFLoader()
        >>> program_id = loader.load_program("xdp_firewall.o")
        >>> loader.attach_to_interface(program_id, "eth0", EBPFProgramType.XDP)
        >>> # ... network monitoring ...
        >>> loader.detach_from_interface(program_id, "eth0")
        >>> loader.unload_program(program_id)
    """
    
    def __init__(self, programs_dir: Optional[Path] = None):
        """
        Initialize the eBPF loader.
        
        Args:
            programs_dir: Directory containing compiled eBPF .o files.
                         Defaults to src/network/ebpf/programs/
        """
        self.programs_dir = programs_dir or Path(__file__).parent / "programs"
        self.loaded_programs: Dict[str, Dict] = {}  # program_id -> metadata
        self.attached_interfaces: Dict[str, List[str]] = {}  # interface -> [program_ids]
        
        logger.info(f"eBPF Loader initialized. Programs directory: {self.programs_dir}")
    
    def load_program(
        self, 
        program_path: str, 
        program_type: EBPFProgramType = EBPFProgramType.XDP
    ) -> str:
        """
        Load an eBPF program from a compiled .o file.
        
        Args:
            program_path: Path to compiled eBPF object file (.o)
            program_type: Type of eBPF program (XDP, TC, etc.)
        
        Returns:
            program_id: Unique identifier for the loaded program
        
        Raises:
            EBPFLoadError: If loading fails (file not found, invalid bytecode, etc.)
        
        TODO:
        - Implement actual eBPF loading via bpftool or bcc
        - Add bytecode validation
        - Parse eBPF maps and verify limits
        - Handle BTF (BPF Type Format) if available
        """
        full_path = self.programs_dir / program_path
        
        if not full_path.exists():
            raise EBPFLoadError(f"eBPF program not found: {full_path}")
        
        if not full_path.suffix == ".o":
            raise EBPFLoadError(f"Invalid eBPF program file. Expected .o, got {full_path.suffix}")
        
        # Generate unique program ID
        program_id = f"{program_type.value}_{full_path.stem}_{id(self)}"
        
        # Store program metadata (placeholder for actual loading)
        self.loaded_programs[program_id] = {
            "path": str(full_path),
            "type": program_type,
            "loaded": True,
            "size_bytes": full_path.stat().st_size,
        }
        
        logger.info(f"Loaded eBPF program: {program_id} from {full_path}")
        return program_id
    
    def attach_to_interface(
        self,
        program_id: str,
        interface: str,
        mode: EBPFAttachMode = EBPFAttachMode.SKB
    ) -> bool:
        """
        Attach a loaded eBPF program to a network interface.
        
        Args:
            program_id: ID returned by load_program()
            interface: Network interface name (e.g., "eth0", "wlan0")
            mode: XDP attach mode (SKB/DRV/HW)
        
        Returns:
            True if attachment successful
        
        Raises:
            EBPFAttachError: If attachment fails
        
        TODO:
        - Implement actual interface attachment via ip link / bpftool
        - Verify interface exists and is up
        - Handle XDP mode negotiation (try HW → DRV → SKB)
        - Add support for TC attachment (ingress/egress qdisc)
        """
        if program_id not in self.loaded_programs:
            raise EBPFAttachError(f"Program not loaded: {program_id}")
        
        program_type = self.loaded_programs[program_id]["type"]
        
        # Verify interface exists (placeholder check)
        # TODO: Check /sys/class/net/{interface}/ or use pyroute2
        
        # Mark as attached
        if interface not in self.attached_interfaces:
            self.attached_interfaces[interface] = []
        
        if program_id in self.attached_interfaces[interface]:
            logger.warning(f"Program {program_id} already attached to {interface}")
            return True
        
        self.attached_interfaces[interface].append(program_id)
        self.loaded_programs[program_id]["attached_to"] = interface
        self.loaded_programs[program_id]["attach_mode"] = mode
        
        logger.info(f"Attached {program_type.value} program {program_id} to {interface} (mode: {mode.value})")
        return True
    
    def detach_from_interface(self, program_id: str, interface: str) -> bool:
        """
        Detach an eBPF program from a network interface.
        
        Args:
            program_id: ID of the program to detach
            interface: Network interface name
        
        Returns:
            True if detachment successful
        
        TODO:
        - Implement actual detachment (ip link set dev {interface} xdp off)
        - Handle TC detachment (tc filter del)
        """
        if program_id not in self.loaded_programs:
            logger.warning(f"Program {program_id} not found in loaded programs")
            return False
        
        if interface not in self.attached_interfaces:
            logger.warning(f"No programs attached to interface {interface}")
            return False
        
        if program_id in self.attached_interfaces[interface]:
            self.attached_interfaces[interface].remove(program_id)
            if "attached_to" in self.loaded_programs[program_id]:
                del self.loaded_programs[program_id]["attached_to"]
            
            logger.info(f"Detached program {program_id} from {interface}")
            return True
        
        return False
    
    def unload_program(self, program_id: str) -> bool:
        """
        Unload an eBPF program and free kernel resources.
        
        Args:
            program_id: ID of the program to unload
        
        Returns:
            True if unload successful
        
        TODO:
        - Verify program is detached from all interfaces first
        - Release BPF maps
        - Close BPF file descriptors
        """
        if program_id not in self.loaded_programs:
            logger.warning(f"Program {program_id} not loaded")
            return False
        
        # Check if still attached
        if "attached_to" in self.loaded_programs[program_id]:
            interface = self.loaded_programs[program_id]["attached_to"]
            logger.warning(f"Detaching program {program_id} from {interface} before unload")
            self.detach_from_interface(program_id, interface)
        
        del self.loaded_programs[program_id]
        logger.info(f"Unloaded program {program_id}")
        return True
    
    def list_loaded_programs(self) -> List[Dict]:
        """Return list of all currently loaded programs with metadata."""
        return [
            {"id": prog_id, **metadata}
            for prog_id, metadata in self.loaded_programs.items()
        ]
    
    def get_interface_programs(self, interface: str) -> List[str]:
        """Return list of program IDs attached to a specific interface."""
        return self.attached_interfaces.get(interface, [])
