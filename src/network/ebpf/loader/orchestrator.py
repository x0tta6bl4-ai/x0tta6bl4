"""
eBPF Loader Orchestrator - High-level coordination

Provides a unified interface for eBPF program management,
coordinating ProgramLoader, AttachManager, and MapManager.

This is the main entry point for eBPF operations.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.agent_thinking import AgentThinkingCoach

from .program_loader import EBPFProgramLoader, EBPFProgramType, EBPFLoadError
from .attach_manager import EBPFAttachManager, EBPFAttachMode, EBPFAttachError
from .map_manager import EBPFMapManager

logger = logging.getLogger(__name__)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()

# Monitoring metrics
try:
    from src.monitoring import record_ebpf_compilation, record_ebpf_event
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    
    def record_ebpf_event(*args, **kwargs):
        pass
    
    def record_ebpf_compilation(*args, **kwargs):
        pass


class EBPFLoaderOrchestrator:
    """
    eBPF Loader Orchestrator - unified interface for eBPF operations.
    
    This class provides backward compatibility with the original EBPFLoader
    while using the new modular architecture internally.
    
    Example:
        >>> loader = EBPFLoaderOrchestrator()
        >>> program_id = loader.load_program("xdp_firewall.o")
        >>> loader.attach_to_interface(program_id, "eth0")
        >>> stats = loader.get_stats()
        >>> loader.cleanup()
    """
    
    def __init__(self, programs_dir: Optional[Path] = None):
        """
        Initialize the eBPF loader orchestrator.
        
        Args:
            programs_dir: Directory containing compiled eBPF .o files.
        """
        self.program_loader = EBPFProgramLoader(programs_dir)
        self.attach_manager = EBPFAttachManager()
        self.map_manager = EBPFMapManager()
        self.programs_dir = self.program_loader.programs_dir

        # Backward compatibility aliases
        self.loaded_programs = self.program_loader.loaded_programs
        self.attached_interfaces = self.attach_manager.attached_interfaces
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ebpf-loader-orchestrator",
            role="coordinator",
            capabilities=("security", "zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        
        logger.info("EBPFLoaderOrchestrator initialized")

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_loader_orchestration",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Coordinate only local eBPF loader actions with redacted "
                "selectors; do not expose program paths, interface names, route "
                "selectors, stdout, stderr, or raw program IDs."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose orchestration thinking state without task secrets."""

        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
            "components": {
                "program_loader": self.program_loader.get_thinking_status(),
                "attach_manager": self.attach_manager.get_thinking_status(),
                "map_manager": self.map_manager.get_thinking_status(),
            },
        }
    
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
            EBPFLoadError: If loading fails
        """
        self._record_thinking_context(
            operation="load_program",
            goal="load local eBPF program through program loader",
            constraints={
                "program_path_hash": _hash_value(program_path),
                "program_path_redacted": True,
                "program_type": program_type.value,
            },
        )
        program_id, metadata = self.program_loader.load(program_path, program_type)
        
        # Record metrics
        size_kb = metadata.get("size_bytes", 0) / 1024.0
        record_ebpf_event("program_load", program_type.value)
        record_ebpf_compilation(0, size_kb, program_type.value)
        
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
            interface: Network interface name (e.g., "eth0")
            mode: XDP attach mode (SKB/DRV/HW)
            
        Returns:
            True if attachment successful
            
        Raises:
            EBPFAttachError: If attachment fails
        """
        self._record_thinking_context(
            operation="attach_to_interface",
            goal="attach loaded eBPF program to local interface",
            constraints={
                "program_id_hash": _hash_value(program_id),
                "interface_hash": _hash_value(interface),
                "program_id_redacted": True,
                "interface_redacted": True,
                "mode": mode.value,
            },
        )
        metadata = self.program_loader.get_program(program_id)
        if not metadata:
            raise EBPFAttachError(f"Program not loaded: {program_id}")
        
        program_type = metadata["type"]
        program_path = metadata.get("pinned_path") or metadata["path"]
        
        if program_type == EBPFProgramType.XDP:
            success = self.attach_manager.attach_xdp(
                program_path, interface, mode, program_id
            )
        elif program_type == EBPFProgramType.TC:
            success = self.attach_manager.attach_tc(
                program_path, interface, program_id
            )
        else:
            raise EBPFAttachError(
                f"Unsupported program type for attachment: {program_type}"
            )
        
        if success:
            metadata["attached_to"] = interface
            metadata["attach_mode"] = mode
            record_ebpf_event("program_attach", program_type.value)
        
        return success
    
    def detach_from_interface(self, program_id: str, interface: str) -> bool:
        """
        Detach an eBPF program from a network interface.
        
        Args:
            program_id: ID of the program to detach
            interface: Network interface name
            
        Returns:
            True if detachment successful
        """
        self._record_thinking_context(
            operation="detach_from_interface",
            goal="detach loaded eBPF program from local interface",
            constraints={
                "program_id_hash": _hash_value(program_id),
                "interface_hash": _hash_value(interface),
                "program_id_redacted": True,
                "interface_redacted": True,
            },
        )
        metadata = self.program_loader.get_program(program_id)
        if not metadata:
            logger.warning(f"Program {program_id} not found")
            return False
        
        attachments = self.attach_manager.get_interface_attachments(interface)
        attachment = None
        for att in attachments:
            if att.get("program_id") == program_id:
                attachment = att
                break
        
        if not attachment:
            logger.warning(f"Program {program_id} not attached to {interface}")
            return False
        
        program_type = attachment.get("type")
        
        if program_type == "xdp":
            success = self.attach_manager.detach_xdp(interface)
        elif program_type == "tc":
            success = self.attach_manager.detach_tc(interface)
        else:
            logger.error(f"Unknown program type: {program_type}")
            return False
        
        if success:
            self.attach_manager.remove_attachment(interface, program_id)
            if "attached_to" in metadata:
                del metadata["attached_to"]
            record_ebpf_event("program_detach", program_type)
        
        return success
    
    def unload_program(self, program_id: str) -> bool:
        """
        Unload an eBPF program and free kernel resources.
        
        Args:
            program_id: ID of the program to unload
            
        Returns:
            True if unload successful
        """
        self._record_thinking_context(
            operation="unload_program",
            goal="unload local eBPF program and clear resources",
            constraints={
                "program_id_hash": _hash_value(program_id),
                "program_id_redacted": True,
                "attached_interface_count": len(self.attach_manager.attached_interfaces),
            },
        )
        # Check if program is still attached
        for interface, attachments in self.attach_manager.attached_interfaces.items():
            for att in attachments:
                if att.get("program_id") == program_id:
                    logger.warning(
                        f"Program {program_id} still attached to {interface}. "
                        f"Auto-detaching before unload."
                    )
                    self.detach_from_interface(program_id, interface)
                    break
        
        success = self.program_loader.unload(program_id)
        
        if success:
            record_ebpf_event("program_unload", "unknown")
        
        return success
    
    def list_loaded_programs(self) -> List[Dict]:
        """Return list of all currently loaded programs with metadata."""
        return [
            {"id": prog_id, **metadata}
            for prog_id, metadata in self.program_loader.loaded_programs.items()
        ]
    
    def get_interface_programs(self, interface: str) -> List[str]:
        """Return list of program IDs attached to a specific interface."""
        attachments = self.attach_manager.get_interface_attachments(interface)
        return [att.get("program_id") for att in attachments if att.get("program_id")]
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics from loaded eBPF programs.
        
        Returns:
            Dict with keys: total_packets, passed_packets, dropped_packets, forwarded_packets
        """
        self._record_thinking_context(
            operation="get_stats",
            goal="read aggregate packet statistics from eBPF maps",
            constraints={"read_only": True},
        )
        return self.map_manager.get_stats()
    
    def update_routes(self, routes: Dict[str, str]) -> bool:
        """
        Update mesh routing table in eBPF map.
        
        Args:
            routes: Dict mapping destination IP to next hop interface index
            
        Returns:
            True if update successful
        """
        self._record_thinking_context(
            operation="update_routes",
            goal="update mesh route selectors in local eBPF map",
            constraints={
                "route_count": len(routes),
                "route_selectors_redacted": True,
            },
        )
        return self.map_manager.update_routes(routes)
    
    def cleanup(self) -> None:
        """
        Clean up all loaded eBPF programs and detach from interfaces.
        """
        self._record_thinking_context(
            operation="cleanup",
            goal="detach and unload all tracked local eBPF programs",
            constraints={
                "loaded_program_count": len(self.program_loader.loaded_programs),
                "interface_count": len(self.attach_manager.attached_interfaces),
                "selectors_redacted": True,
            },
        )
        logger.info("Cleaning up eBPF programs...")
        
        # Detach from all interfaces
        for interface in list(self.attach_manager.attached_interfaces.keys()):
            attachments = list(self.attach_manager.get_interface_attachments(interface))
            for attachment in attachments:
                program_id = attachment.get("program_id")
                if program_id:
                    try:
                        self.detach_from_interface(program_id, interface)
                    except Exception as e:
                        logger.warning(f"Failed to detach {program_id}: {e}")
        
        # Unload all programs
        for program_id in list(self.program_loader.loaded_programs.keys()):
            try:
                self.unload_program(program_id)
            except Exception as e:
                logger.warning(f"Failed to unload {program_id}: {e}")
        
        logger.info("eBPF cleanup complete")
    
    def load_programs(self) -> List[str]:
        """
        Load all eBPF programs from the programs directory.
        
        Returns:
            List of loaded program IDs
        """
        loaded_ids = []
        
        programs_dir = self.program_loader.programs_dir
        self._record_thinking_context(
            operation="load_programs",
            goal="discover and load local eBPF object files",
            constraints={
                "programs_dir_exists": programs_dir.exists(),
                "programs_dir_hash": _hash_value(programs_dir),
                "programs_dir_redacted": True,
            },
        )
        if not programs_dir.exists():
            logger.warning(f"Programs directory does not exist: {programs_dir}")
            return loaded_ids
        
        # Find all .o files
        program_files = list(programs_dir.glob("*.o"))
        
        if not program_files:
            logger.info(f"No eBPF programs found in {programs_dir}")
            return loaded_ids
        
        for program_file in program_files:
            try:
                # Determine program type from filename
                if "xdp" in program_file.stem.lower():
                    program_type = EBPFProgramType.XDP
                elif "tc" in program_file.stem.lower():
                    program_type = EBPFProgramType.TC
                else:
                    program_type = EBPFProgramType.XDP  # Default
                
                program_id = self.load_program(program_file.name, program_type)
                loaded_ids.append(program_id)
                
            except EBPFLoadError as e:
                logger.error(f"Failed to load {program_file.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading {program_file.name}: {e}")
        
        logger.info(f"Loaded {len(loaded_ids)} eBPF programs")
        return loaded_ids


# Backward compatibility alias
EBPFLoader = EBPFLoaderOrchestrator
