"""
eBPF Program Loader - ELF parsing and program loading

Handles:
- ELF section parsing (.text, .maps, .BTF)
- Program loading via bpftool
- Program lifecycle management
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

EBPF_LOADER_PROGRAM_LOADER_SERVICE_NAME = "ebpf-loader-program-loader"
EBPF_LOADER_PROGRAM_LOADER_LAYER = "network_ebpf_loader_program_loader_observed_state"
EBPF_LOADER_PROGRAM_LOADER_CLAIM_BOUNDARY = (
    "Local modular eBPF program loader evidence only. Events record bpftool "
    "availability and program-load command outcomes, return codes, duration, "
    "bounded output hashes, and redacted program/BPFFS selectors; they do not "
    "prove production traffic, remote peer behavior, or attached kernel program "
    "correctness beyond the local command result."
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
            safe_command.append(Path(str(item)).name)
        elif index in redacted:
            safe_command.append("[redacted]")
        else:
            safe_command.append(str(item))
    return safe_command


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(
        service_name=EBPF_LOADER_PROGRAM_LOADER_SERVICE_NAME
    )
    return {
        "service_name": EBPF_LOADER_PROGRAM_LOADER_SERVICE_NAME,
        "layer": EBPF_LOADER_PROGRAM_LOADER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }

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
    
    def __init__(
        self,
        programs_dir: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """
        Initialize the program loader.
        
        Args:
            programs_dir: Directory containing compiled eBPF .o files.
        """
        self.programs_dir = programs_dir or Path(__file__).parent.parent / "programs"
        self.loaded_programs: Dict[str, Dict] = {}
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_LOADER_PROGRAM_LOADER_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        
        logger.info(f"EBPFProgramLoader initialized. Programs directory: {self.programs_dir}")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = EventBus(project_root=self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF program loader EventBus: %s", exc)
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
        """Build a redacted decision context for eBPF program-loader observations."""

        safe_task = {
            "task_type": "ebpf_loader_program_observation",
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
                "Record only local bpftool loader evidence, redacted program "
                "selectors, hashes, and bounded metadata; do not expose program "
                "paths, BPFFS paths, stdout, stderr, or raw program IDs."
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
            "component": "network.ebpf.loader.program_loader",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:loader_program_loader:{operation}",
            "service_name": self.source_agent,
            "layer": EBPF_LOADER_PROGRAM_LOADER_LAYER,
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
            "claim_boundary": EBPF_LOADER_PROGRAM_LOADER_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish eBPF program loader observation")
            return None
    
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
        which_cmd = ["which", "bpftool"]
        which_start = time.monotonic()
        try:
            # Check if bpftool is available
            result = safe_run(which_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self._publish_observation(
                    stage="loader_program_loader_bpftool_unavailable",
                    operation="bpftool_available",
                    status="empty",
                    source_mode="which",
                    start=which_start,
                    returncode=result.returncode,
                    stdout=getattr(result, "stdout", None),
                    stderr=getattr(result, "stderr", None),
                    command=_redacted_command(which_cmd, redacted_indices=()),
                    parsed_summary={"bpftool_available": False},
                    extra={
                        "program_path_hash": _hash_value(program_path),
                        "program_path_redacted": True,
                    },
                )
                logger.debug("bpftool not found, falling back to alternative methods")
                return None, None
            self._publish_observation(
                stage="loader_program_loader_bpftool_available",
                operation="bpftool_available",
                status="success",
                source_mode="which",
                start=which_start,
                returncode=result.returncode,
                stdout=getattr(result, "stdout", None),
                stderr=getattr(result, "stderr", None),
                command=_redacted_command(which_cmd, redacted_indices=()),
                parsed_summary={"bpftool_available": True},
                extra={
                    "program_path_hash": _hash_value(program_path),
                    "program_path_redacted": True,
                },
            )
            
            # Load program using bpftool
            bpffs_path = Path(f"/sys/fs/bpf/x0tta6bl4_{program_path.stem}")
            bpffs_path.parent.mkdir(parents=True, exist_ok=True)
            
            cmd = ["bpftool", "prog", "load", str(program_path), str(bpffs_path)]
            load_start = time.monotonic()
            result = safe_run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                self._publish_observation(
                    stage="loader_program_loader_bpftool_load_succeeded",
                    operation="bpftool_prog_load",
                    status="success",
                    source_mode="bpftool",
                    start=load_start,
                    returncode=result.returncode,
                    stdout=getattr(result, "stdout", None),
                    stderr=getattr(result, "stderr", None),
                    command=_redacted_command(cmd, redacted_indices=(3, 4)),
                    read_only=False,
                    parsed_summary={"pinned": True, "program_type": program_type.value},
                    extra={
                        "program_path_hash": _hash_value(program_path),
                        "bpffs_path_hash": _hash_value(bpffs_path),
                        "program_path_redacted": True,
                        "bpffs_path_redacted": True,
                    },
                )
                logger.info(f"Program loaded via bpftool to {bpffs_path}")
                return None, str(bpffs_path)
            else:
                self._publish_observation(
                    stage="loader_program_loader_bpftool_load_failed",
                    operation="bpftool_prog_load",
                    status="failure",
                    source_mode="bpftool",
                    start=load_start,
                    returncode=result.returncode,
                    stdout=getattr(result, "stdout", None),
                    stderr=getattr(result, "stderr", None),
                    command=_redacted_command(cmd, redacted_indices=(3, 4)),
                    read_only=False,
                    parsed_summary={"pinned": False, "program_type": program_type.value},
                    extra={
                        "program_path_hash": _hash_value(program_path),
                        "bpffs_path_hash": _hash_value(bpffs_path),
                        "program_path_redacted": True,
                        "bpffs_path_redacted": True,
                    },
                )
                logger.warning("bpftool program load failed")
                return None, None
                
        except FileNotFoundError as exc:
            self._publish_observation(
                stage="loader_program_loader_bpftool_unavailable",
                operation="bpftool_prog_load",
                status="failure",
                source_mode="bpftool",
                start=which_start,
                command=_redacted_command(which_cmd, redacted_indices=()),
                error=exc,
                parsed_summary={
                    "bpftool_available": False,
                    "program_type": program_type.value,
                },
                extra={
                    "program_path_hash": _hash_value(program_path),
                    "program_path_redacted": True,
                },
            )
            logger.debug("bpftool not found")
            return None, None
        except subprocess.TimeoutExpired as exc:
            command = cmd if "cmd" in locals() else which_cmd
            redacted_indices = (3, 4) if "cmd" in locals() else ()
            self._publish_observation(
                stage="loader_program_loader_bpftool_load_timeout",
                operation="bpftool_prog_load",
                status="failure",
                source_mode="bpftool",
                start=load_start if "load_start" in locals() else which_start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=_redacted_command(command, redacted_indices=redacted_indices),
                error=exc,
                parsed_summary={"program_type": program_type.value},
                extra={
                    "program_path_hash": _hash_value(program_path),
                    "program_path_redacted": True,
                },
            )
            logger.error("bpftool load timed out")
            return None, None
        except Exception as e:
            command = cmd if "cmd" in locals() else which_cmd
            redacted_indices = (3, 4) if "cmd" in locals() else ()
            self._publish_observation(
                stage="loader_program_loader_bpftool_load_error",
                operation="bpftool_prog_load",
                status="failure",
                source_mode="bpftool",
                start=load_start if "load_start" in locals() else which_start,
                command=_redacted_command(command, redacted_indices=redacted_indices),
                error=e,
                parsed_summary={"program_type": program_type.value},
                extra={
                    "program_path_hash": _hash_value(program_path),
                    "program_path_redacted": True,
                },
            )
            logger.warning("bpftool program load error")
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

