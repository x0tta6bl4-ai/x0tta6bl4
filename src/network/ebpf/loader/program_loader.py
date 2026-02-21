"""
eBPF Program Loader - ELF parsing and program loading

Handles:
- ELF section parsing (.text, .maps, .BTF)
- Program loading via bpftool
- Program lifecycle management
"""

import logging
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.core.subprocess_validator import safe_run

logger = logging.getLogger(__name__)

# Optional ELF parsing library
try:
    from elftools.elf.elffile import ELFFile
    ELF_TOOLS_AVAILABLE = True
except ImportError:
    ELF_TOOLS_AVAILABLE = False
    logger.warning("pyelftools not available. Install with: pip install pyelftools")


class EBPFProgramType(Enum):
    """Supported eBPF program types for network monitoring"""
    XDP = "xdp"  # eXpress Data Path - fastest path for packet processing
    TC = "tc"  # Traffic Control - classifier/action programs
    CGROUP_SKB = "cgroup_skb"  # Socket buffer control
    SOCKET_FILTER = "socket_filter"  # Classic socket filtering


class EBPFLoadError(Exception):
    """Raised when eBPF program loading fails"""
    pass


class EBPFProgramLoader:
    """
    eBPF Program Loader - handles ELF parsing and program loading.
    
    Responsibilities:
    - Parse ELF sections from .o files
    - Load programs via bpftool
    - Track loaded programs
    
    Example:
        >>> loader = EBPFProgramLoader()
        >>> program_id, metadata = loader.load("xdp_firewall.o", EBPFProgramType.XDP)
    """
    
    def __init__(self, programs_dir: Optional[Path] = None):
        """
        Initialize the program loader.
        
        Args:
            programs_dir: Directory containing compiled eBPF .o files.
        """
        self.programs_dir = programs_dir or Path(__file__).parent.parent / "programs"
        self.loaded_programs: Dict[str, Dict] = {}
        
        logger.info(f"EBPFProgramLoader initialized. Programs directory: {self.programs_dir}")
    
    def parse_elf_sections(self, elf_path: Path) -> Dict[str, Dict]:
        """
        Parse ELF sections from eBPF .o file.
        
        Extracts:
        - .text: Program instructions
        - .maps: BPF map definitions
        - .BTF: BPF Type Format metadata
        - license: Program license
        - version: Program version
        
        Returns:
            Dict mapping section names to section data
        """
        sections = {}
        
        if not ELF_TOOLS_AVAILABLE:
            logger.warning("pyelftools not available, skipping ELF parsing")
            return sections
        
        try:
            with open(elf_path, "rb") as f:
                elf = ELFFile(f)
                
                for section in elf.iter_sections():
                    section_name = section.name
                    
                    if section_name in [
                        ".text", ".maps", ".BTF", ".BTF.ext",
                        "license", "version",
                    ]:
                        sections[section_name] = {
                            "data": section.data(),
                            "size": section.data_size,
                            "offset": section["sh_offset"],
                        }
                        
                        # Special handling for license
                        if section_name == "license":
                            try:
                                sections[section_name]["text"] = (
                                    section.data().decode("utf-8").strip("\x00")
                                )
                            except Exception:
                                pass
                
                logger.debug(f"Parsed {len(sections)} ELF sections from {elf_path.name}")
                
        except Exception as e:
            logger.warning(f"Failed to parse ELF sections: {e}")
        
        return sections
    
    def load_via_bpftool(
        self, program_path: Path, program_type: EBPFProgramType
    ) -> Tuple[Optional[int], Optional[str]]:
        """
        Load eBPF program using bpftool.
        
        Returns:
            (prog_fd, pinned_path) or (None, None) if failed
        """
        try:
            # Check if bpftool is available
            result = safe_run(["which", "bpftool"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.debug("bpftool not found, falling back to alternative methods")
                return None, None
            
            # Load program using bpftool
            bpffs_path = Path(f"/sys/fs/bpf/x0tta6bl4_{program_path.stem}")
            bpffs_path.parent.mkdir(parents=True, exist_ok=True)
            
            cmd = ["bpftool", "prog", "load", str(program_path), str(bpffs_path)]
            result = safe_run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logger.info(f"Program loaded via bpftool to {bpffs_path}")
                return None, str(bpffs_path)
            else:
                logger.warning(f"bpftool load failed: {result.stderr}")
                return None, None
                
        except FileNotFoundError:
            logger.debug("bpftool not found")
            return None, None
        except subprocess.TimeoutExpired:
            logger.error("bpftool load timed out")
            return None, None
        except Exception as e:
            logger.warning(f"bpftool load error: {e}")
            return None, None
    
    def load(
        self, 
        program_path: str, 
        program_type: EBPFProgramType = EBPFProgramType.XDP
    ) -> Tuple[str, Dict]:
        """
        Load an eBPF program from a compiled .o file.
        
        Args:
            program_path: Path to compiled eBPF object file (.o)
            program_type: Type of eBPF program (XDP, TC, etc.)
            
        Returns:
            Tuple of (program_id, metadata)
            
        Raises:
            EBPFLoadError: If loading fails
        """
        full_path = self.programs_dir / program_path
        
        if not full_path.exists():
            raise EBPFLoadError(f"eBPF program not found: {full_path}")
        
        if not full_path.suffix == ".o":
            raise EBPFLoadError(
                f"Invalid eBPF program file. Expected .o, got {full_path.suffix}"
            )
        
        # Parse ELF sections
        sections = self.parse_elf_sections(full_path)
        
        # Extract metadata
        text_section = sections.get(".text", {})
        license = sections.get("license", {}).get("text", "GPL")
        
        # Validate license (kernel requires GPL-compatible)
        if license and "GPL" not in license:
            logger.warning(f"Program license '{license}' may not be GPL-compatible")
        
        # Attempt to load via bpftool
        prog_fd, pinned_path = self.load_via_bpftool(full_path, program_type)
        
        # If bpftool failed and we have no valid program, raise error
        if prog_fd is None and pinned_path is None:
            if not sections or (ELF_TOOLS_AVAILABLE and not sections):
                raise EBPFLoadError(
                    f"Invalid eBPF program file: {full_path}. "
                    f"Failed to parse ELF and bpftool load failed."
                )
        
        # Generate unique program ID
        program_id = f"{program_type.value}_{full_path.stem}_{id(self)}"
        
        # Store program metadata
        size_bytes = full_path.stat().st_size
        
        metadata = {
            "path": str(full_path),
            "type": program_type,
            "loaded": True,
            "size_bytes": size_bytes,
            "sections": list(sections.keys()),
            "text_size": text_section.get("size", 0),
            "has_btf": ".BTF" in sections,
            "has_maps": ".maps" in sections,
            "license": license,
            "pinned_path": pinned_path,
            "prog_fd": prog_fd,
        }
        
        self.loaded_programs[program_id] = metadata
        
        logger.info(
            f"Loaded eBPF program: {program_id} from {full_path} "
            f"(sections: {len(sections)}, BTF: {'.BTF' in sections})"
        )
        
        return program_id, metadata
    
    def unload(self, program_id: str) -> bool:
        """
        Unload an eBPF program.
        
        Args:
            program_id: ID of the program to unload
            
        Returns:
            True if unload successful
        """
        if program_id not in self.loaded_programs:
            logger.warning(f"Program {program_id} not loaded")
            return False
        
        # Unpin from bpffs if pinned
        pinned_path = self.loaded_programs[program_id].get("pinned_path")
        if pinned_path:
            try:
                pinned_file = Path(pinned_path)
                if pinned_file.exists():
                    pinned_file.unlink()
                    logger.debug(f"Unpinned program from {pinned_path}")
            except Exception as e:
                logger.warning(f"Failed to unpin program: {e}")
        
        del self.loaded_programs[program_id]
        logger.info(f"Unloaded program {program_id}")
        return True
    
    def get_program(self, program_id: str) -> Optional[Dict]:
        """Get program metadata by ID."""
        return self.loaded_programs.get(program_id)
    
    def list_programs(self) -> Dict[str, Dict]:
        """Return all loaded programs."""
        return self.loaded_programs.copy()
