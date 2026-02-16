"""
eBPF Loader for x0tta6bl4
Loads and manages eBPF programs for observability

Date: February 2, 2026
Version: 1.0
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import BCC (BPF Compiler Collection)
BCC_AVAILABLE = False
try:
    from bcc import BPF

    BCC_AVAILABLE = True
    logger.info("✅ BCC available - eBPF programs can be loaded")
except ImportError as e:
    logger.warning(
        f"⚠️ BCC not available ({e}). Install with: apt-get install bpfcc-tools"
    )
    BCC_AVAILABLE = False


@dataclass
class EBPFProgram:
    """Represents a loaded eBPF program."""

    name: str
    bpf: Optional[Any]  # BPF object if BCC available
    program_path: str
    loaded: bool = False
    attached_hooks: List[str] = None

    def __post_init__(self):
        if self.attached_hooks is None:
            self.attached_hooks = []


class EBPFLoader:
    """
    Loads and manages eBPF programs.

    Responsibilities:
    - Compile eBPF programs
    - Load programs into kernel
    - Attach to hooks
    - Handle errors and fallbacks
    - Manage program lifecycle
    """

    def __init__(self, bcc_path: Optional[str] = None):
        """
        Initialize eBPF loader.

        Args:
            bcc_path: Optional path to BCC installation
        """
        self.bcc_path = bcc_path
        self.loaded_programs: Dict[str, EBPFProgram] = {}
        self.program_stats: Dict[str, Dict[str, Any]] = {}

        if not BCC_AVAILABLE:
            logger.warning(
                "⚠️ BCC not available - eBPF programs will use stub implementation"
            )

    def load_program(
        self, program_path: str, cflags: Optional[List[str]] = None
    ) -> EBPFProgram:
        """
        Load eBPF program from file.

        Args:
            program_path: Path to eBPF C source file
            cflags: Optional C compiler flags

        Returns:
            EBPFProgram object

        Raises:
            RuntimeError: If BCC not available or loading fails
        """
        if not BCC_AVAILABLE:
            logger.warning(f"⚠️ BCC not available - using stub for {program_path}")
            return EBPFProgram(
                name=Path(program_path).stem,
                bpf=None,
                program_path=program_path,
                loaded=False,
            )

        try:
            # Read eBPF program source
            with open(program_path, "r") as f:
                program_source = f.read()

            # Compile and load eBPF program
            if cflags is None:
                cflags = ["-Wno-macro-redefined", "-Wno-unused-value"]

            bpf = BPF(text=program_source, cflags=cflags)

            # Create program object
            program_name = Path(program_path).stem
            program = EBPFProgram(
                name=program_name, bpf=bpf, program_path=program_path, loaded=True
            )

            # Store loaded program
            self.loaded_programs[program_name] = program

            # Initialize stats
            self.program_stats[program_name] = {
                "loaded_at": self._get_timestamp(),
                "attached_hooks": [],
                "maps": self._get_program_maps(bpf),
                "events": 0,
            }

            logger.info(f"✅ Loaded eBPF program: {program_name}")
            return program

        except Exception as e:
            logger.error(f"❌ Failed to load eBPF program {program_path}: {e}")
            raise RuntimeError(f"Failed to load eBPF program: {e}")

    def attach_hook(self, program: EBPFProgram, hook: str, **kwargs) -> bool:
        """
        Attach eBPF program to kernel hook.

        Args:
            program: EBPFProgram object
            hook: Hook name (e.g., "sched_switch", "tc", "sys_connect")
            **kwargs: Additional hook-specific arguments

        Returns:
            True if successful, False otherwise
        """
        if not BCC_AVAILABLE or not program.bpf:
            logger.warning(
                f"⚠️ Cannot attach hook {hook} - BCC not available or program not loaded"
            )
            return False

        try:
            # Attach based on hook type
            if hook == "sched_switch":
                # Attach to sched_switch tracepoint
                program.bpf["trace_sched_switch"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "tc":
                # Attach to TC (Traffic Control)
                interface = kwargs.get("interface", "eth0")
                direction = kwargs.get("direction", "ingress")

                if direction == "ingress":
                    fn = program.bpf.load_func("tc_ingress", BPF.SCHED_CLS)
                else:
                    fn = program.bpf.load_func("tc_egress", BPF.SCHED_CLS)

                fn.attach(interface, direction)
                logger.info(f"✅ Attached to hook: {hook} ({direction} on {interface})")

            elif hook == "sys_connect":
                # Attach to sys_connect tracepoint
                program.bpf["trace_sys_enter_connect"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "sys_enter_execve":
                # Attach to sys_enter_execve tracepoint
                program.bpf["trace_sys_enter_execve"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "kmem_cache_alloc":
                # Attach to kmem_cache_alloc kprobe
                program.bpf["kprobe_kmem_cache_alloc"].attach()
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "kfree_skb":
                # Attach to kfree_skb kprobe
                program.bpf["kprobe_kfree_skb"].attach()
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "security_inode_permission":
                # Attach to security_inode_permission tracepoint
                program.bpf["trace_security_inode_permission"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "sched_process_exec":
                # Attach to sched_process_exec tracepoint
                program.bpf["trace_sched_process_exec"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "sched_process_exit":
                # Attach to sched_process_exit tracepoint
                program.bpf["trace_sched_process_exit"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "tcp_retransmit_skb":
                # Attach to tcp_retransmit_skb tracepoint
                program.bpf["trace_tcp_retransmit_skb"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "inet_sock_set_state":
                # Attach to inet_sock_set_state tracepoint
                program.bpf["trace_inet_sock_set_state"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "security_prepare_creds":
                # Attach to security_prepare_creds tracepoint
                program.bpf["trace_security_prepare_creds"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "tcp_connect":
                # Attach to tcp_connect kprobe
                program.bpf["kprobe_tcp_connect"].attach()
                logger.info(f"✅ Attached to hook: {hook}")

            elif hook == "block_rq_insert":
                # Attach to block_rq_insert tracepoint
                program.bpf["trace_block_rq_insert"].open_perf_buffer(
                    perf_cb=self._perf_event_cb
                )
                logger.info(f"✅ Attached to hook: {hook}")

            else:
                logger.warning(f"⚠️ Unknown hook type: {hook}")
                return False

            # Update program stats
            if program.name in self.program_stats:
                self.program_stats[program.name]["attached_hooks"].append(hook)

            # Update program attached hooks
            if hook not in program.attached_hooks:
                program.attached_hooks.append(hook)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to attach hook {hook}: {e}")
            return False

    def detach_hook(self, program: EBPFProgram, hook: str) -> bool:
        """
        Detach eBPF program from kernel hook.

        Args:
            program: EBPFProgram object
            hook: Hook name

        Returns:
            True if successful, False otherwise
        """
        if not BCC_AVAILABLE or not program.bpf:
            logger.warning(
                f"⚠️ Cannot detach hook {hook} - BCC not available or program not loaded"
            )
            return False

        try:
            # Detach based on hook type
            if hook == "tc":
                # TC hooks are detached when program is unloaded
                logger.info(f"✅ Detached from hook: {hook}")

            elif hook in [
                "sched_switch",
                "sys_connect",
                "sys_enter_execve",
                "kmem_cache_alloc",
                "kfree_skb",
                "security_inode_permission",
                "sched_process_exec",
                "sched_process_exit",
                "tcp_retransmit_skb",
                "inet_sock_set_state",
                "security_prepare_creds",
                "tcp_connect",
                "block_rq_insert",
            ]:
                # Tracepoints and kprobes are detached when program is unloaded
                logger.info(f"✅ Detached from hook: {hook}")

            else:
                logger.warning(f"⚠️ Unknown hook type: {hook}")
                return False

            # Update program stats
            if (
                program.name in self.program_stats
                and hook in self.program_stats[program.name]["attached_hooks"]
            ):
                self.program_stats[program.name]["attached_hooks"].remove(hook)

            # Update program attached hooks
            if hook in program.attached_hooks:
                program.attached_hooks.remove(hook)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to detach hook {hook}: {e}")
            return False

    def unload_program(self, program: EBPFProgram) -> bool:
        """
        Unload eBPF program from kernel.

        Args:
            program: EBPFProgram object

        Returns:
            True if successful, False otherwise
        """
        if not BCC_AVAILABLE or not program.bpf:
            logger.warning(
                f"⚠️ Cannot unload program - BCC not available or program not loaded"
            )
            return False

        try:
            # Detach all hooks
            for hook in list(program.attached_hooks):
                self.detach_hook(program, hook)

            # Cleanup BPF program
            program.bpf.cleanup()

            # Update program status
            program.loaded = False

            # Remove from loaded programs
            if program.name in self.loaded_programs:
                del self.loaded_programs[program.name]

            logger.info(f"✅ Unloaded eBPF program: {program.name}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to unload program {program.name}: {e}")
            return False

    def get_program_stats(self, program: EBPFProgram) -> Dict[str, Any]:
        """
        Get statistics for loaded eBPF program.

        Args:
            program: EBPFProgram object

        Returns:
            Dictionary with program statistics
        """
        if program.name not in self.program_stats:
            return {}

        stats = self.program_stats[program.name].copy()

        # Add current timestamp
        stats["current_time"] = self._get_timestamp()

        # Calculate uptime
        if "loaded_at" in stats:
            stats["uptime_ns"] = stats["current_time"] - stats["loaded_at"]

        return stats

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all loaded programs.

        Returns:
            Dictionary mapping program names to their statistics
        """
        return self.program_stats.copy()

    def _perf_event_cb(self, cpu, data, size):
        """
        Callback for perf events from eBPF programs.

        Args:
            cpu: CPU ID
            data: Event data
            size: Size of data
        """
        # Update event count in stats
        for program_name, stats in self.program_stats.items():
            if "events" in stats:
                stats["events"] += 1

    def _get_program_maps(self, bpf) -> List[str]:
        """
        Get list of maps from eBPF program.

        Args:
            bpf: BPF object

        Returns:
            List of map names
        """
        if not hasattr(bpf, "__getitem__"):
            return []

        maps = []
        for key in dir(bpf):
            if key.startswith("[") and key.endswith("]"):
                map_name = key[2:-2]
                maps.append(map_name)

        return maps

    def _get_timestamp(self) -> int:
        """Get current timestamp in nanoseconds."""
        import time

        return int(time.time() * 1e9)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - unload all programs."""
        for program in list(self.loaded_programs.values()):
            self.unload_program(program)


# Stub implementation for when BCC is not available
class StubEBPFProgram:
    """Stub eBPF program for when BCC is not available."""

    def __init__(self, name: str):
        self.name = name
        self.maps = {}

    def __getitem__(self, key):
        """Stub map access."""
        return StubEBPFMap(key, self.name)


class StubEBPFMap:
    """Stub eBPF map for when BCC is not available."""

    def __init__(self, name: str, program_name: str):
        self.name = name
        self.program_name = program_name
        self.data = {}

    def items(self):
        """Stub items iterator."""
        return self.data.items()

    def keys(self):
        """Stub keys iterator."""
        return self.data.keys()

    def values(self):
        """Stub values iterator."""
        return self.data.values()

    def get(self, key, default=None):
        """Stub get."""
        return self.data.get(key, default)

    def __getitem__(self, key):
        """Stub getitem."""
        return self.data.get(key)

    def __setitem__(self, key, value):
        """Stub setitem."""
        self.data[key] = value


def create_stub_program(program_path: str) -> EBPFProgram:
    """
    Create stub eBPF program for when BCC is not available.

    Args:
        program_path: Path to eBPF C source file

    Returns:
        EBPFProgram object with stub implementation
    """
    program_name = Path(program_path).stem
    stub_program = StubEBPFProgram(program_name)

    return EBPFProgram(
        name=program_name, bpf=stub_program, program_path=program_path, loaded=False
    )
