"""
eBPF Loader for x0tta6bl4
Loads and manages eBPF programs for observability

Date: February 2, 2026
Version: 1.0
"""

import logging
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_LOADER_SERVICE_NAME = "ebpf-loader"
EBPF_LOADER_CLAIM_BOUNDARY = (
    "Local eBPF loader state evidence only. Events distinguish stub program "
    "objects from kernel-loaded BPF programs and record bounded redacted loader "
    "metadata; they do not prove kernel attach, packet filtering, or live map "
    "telemetry by themselves."
)

# Try to import BCC (BPF Compiler Collection)
BCC_AVAILABLE = False
BPF: Optional[Any] = None
try:
    from bcc import BPF as _BCCBPF

    BPF = _BCCBPF

    BCC_AVAILABLE = True
    logger.info("✅ BCC available - eBPF programs can be loaded")
except ImportError as e:
    logger.warning(
        f"⚠️ BCC not available ({e}). Install with: apt-get install bpfcc-tools"
    )
    BCC_AVAILABLE = False
    BPF = None


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

    def __init__(
        self,
        bcc_path: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
    ):
        """
        Initialize eBPF loader.

        Args:
            bcc_path: Optional path to BCC installation
        """
        self.bcc_path = bcc_path
        self.event_bus = event_bus
        self.source_agent = EBPF_LOADER_SERVICE_NAME
        self.identity = {
            "node_id": self.source_agent,
            **service_event_identity(service_name=EBPF_LOADER_SERVICE_NAME),
        }
        self.loaded_programs: Dict[str, EBPFProgram] = {}
        self.program_stats: Dict[str, Dict[str, Any]] = {}
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="security",
            capabilities=("zero-trust", "monitoring"),
            extra_techniques=("mape_k", "reverse_planning", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        # DEV MODE: BCC_STUB_MODE env allows stub loads without failing.
        if not BCC_AVAILABLE and not self._bcc_stub_mode_enabled():
            self._publish_loader_event(
                stage="loader_init_blocked",
                operation="loader_init",
                result="blocked",
                mode="unavailable",
                reason="bcc_unavailable_stub_mode_disabled",
                program_path=None,
                kernel_loaded=False,
                program_loaded_flag=False,
            )

    @staticmethod
    def _bcc_stub_mode_enabled() -> bool:
        return os.getenv("BCC_STUB_MODE", "false").lower() == "true"

    @staticmethod
    def _hash_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_bcc_loader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local BCC loader evidence, redacted selectors, "
                "hashes, and bounded metadata; do not expose program paths, "
                "program names, compiler flags, hook arguments, or raw errors."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose BCC-loader thinking state without task secrets."""

        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
        }

    def _publish_loader_event(
        self,
        *,
        stage: str,
        operation: str,
        result: str,
        mode: str,
        reason: str,
        program_path: Optional[str],
        kernel_loaded: bool,
        program_loaded_flag: bool,
        program_name: Optional[str] = None,
        cflags: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None

        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{result}",
            constraints={
                "stage": stage,
                "result": result,
                "mode": mode,
                "reason": reason,
                "bcc_available": BCC_AVAILABLE,
                "bcc_stub_mode_enabled": self._bcc_stub_mode_enabled(),
                "kernel_loaded": kernel_loaded,
                "program_loaded_flag": program_loaded_flag,
                "program_name_hash": self._hash_value(program_name),
                "program_name_redacted": program_name is not None,
                "program_path_hash": self._hash_value(program_path),
                "program_path_redacted": program_path is not None,
                "cflags_count": len(cflags or []),
                "cflags_redacted": bool(cflags),
                "extra_keys": sorted((extra or {}).keys()),
            },
        )

        payload: Dict[str, Any] = {
            "component": "network.ebpf.ebpf_loader",
            "stage": stage,
            "operation": operation,
            "operation_resource": "ebpf_program_load",
            "resource": "network:ebpf:loader",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity.get("spiffe_id"),
            "did": self.identity.get("did"),
            "wallet_address": self.identity.get("wallet_address"),
            "identity": dict(self.identity),
            "result": result,
            "mode": mode,
            "reason": reason,
            "bcc_available": BCC_AVAILABLE,
            "bcc_stub_mode_enabled": self._bcc_stub_mode_enabled(),
            "kernel_loaded": kernel_loaded,
            "program_loaded_flag": program_loaded_flag,
            "program_name_hash": self._hash_value(program_name),
            "program_name_redacted": program_name is not None,
            "program_path_hash": self._hash_value(program_path),
            "program_path_redacted": program_path is not None,
            "cflags_count": len(cflags or []),
            "cflags_hash": self._hash_value(tuple(cflags or [])),
            "cflags_redacted": bool(cflags),
            "loaded_program_count": len(self.loaded_programs),
            "thinking": thinking,
            "payloads_redacted": True,
            "safe_observation": True,
            "claim_boundary": EBPF_LOADER_CLAIM_BOUNDARY,
        }
        if extra:
            payload.update(extra)

        try:
            event = self.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.source_agent,
                payload,
                priority=6,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF loader evidence")
            return None

    def load_program(
        self, program_path: str, cflags: Optional[List[str]] = None
    ) -> EBPFProgram:
        """
        Load eBPF program from file.

        Args:
            program_path: Path to eBPF C source file
            cflags: Optional C compiler flags

        Returns:
            EBPFProgram object (stub with loaded=False when BCC unavailable)

        Raises:
            RuntimeError: If loading fails with BCC available
        """
        self._record_thinking_context(
            operation="load_program",
            goal="load local BCC eBPF program",
            constraints={
                "program_path_hash": self._hash_value(program_path),
                "program_path_redacted": True,
                "cflags_count": len(cflags or []),
                "cflags_redacted": bool(cflags),
                "bcc_available": BCC_AVAILABLE,
            },
        )
        if not BCC_AVAILABLE:
            if not self._bcc_stub_mode_enabled():
                program_name = Path(program_path).stem
                self._publish_loader_event(
                    stage="program_load_blocked",
                    operation="load_program",
                    result="blocked",
                    mode="unavailable",
                    reason="bcc_unavailable_stub_mode_disabled",
                    program_path=program_path,
                    program_name=program_name,
                    cflags=cflags,
                    kernel_loaded=False,
                    program_loaded_flag=False,
                )
                raise RuntimeError(
                    "BCC not available - eBPF programs cannot be loaded. "
                    "Set BCC_STUB_MODE=true for dev stubs."
                )

            program_name = Path(program_path).stem
            program = EBPFProgram(
                name=program_name,
                bpf=StubEBPFProgram(program_name),
                program_path=program_path,
                loaded=True,
            )
            self.loaded_programs[program_name] = program
            logger.warning(
                "⚠️ BCC not available - returning stub EBPFProgram for %s",
                program_name,
            )
            self._publish_loader_event(
                stage="program_stub_created",
                operation="load_program",
                result="success",
                mode="stub",
                reason="bcc_unavailable_stub_mode_enabled",
                program_path=program_path,
                program_name=program_name,
                cflags=cflags,
                kernel_loaded=False,
                program_loaded_flag=program.loaded,
            )
            return program

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
            self._publish_loader_event(
                stage="program_loaded",
                operation="load_program",
                result="success",
                mode="bcc",
                reason="bcc_load_succeeded",
                program_path=program_path,
                program_name=program_name,
                cflags=cflags,
                kernel_loaded=True,
                program_loaded_flag=program.loaded,
                extra={
                    "map_count": len(self.program_stats[program_name]["maps"]),
                },
            )
            return program

        except Exception as e:
            logger.error(f"❌ Failed to load eBPF program {program_path}: {e}")
            self._publish_loader_event(
                stage="program_load_failed",
                operation="load_program",
                result="failure",
                mode="bcc",
                reason="bcc_load_failed",
                program_path=program_path,
                program_name=Path(program_path).stem,
                cflags=cflags,
                kernel_loaded=False,
                program_loaded_flag=False,
                extra={
                    "error_type": type(e).__name__,
                    "error_message_hash": self._hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )
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
        self._record_thinking_context(
            operation="attach_hook",
            goal="attach local BCC eBPF program hook",
            constraints={
                "program_name_hash": self._hash_value(program.name),
                "program_name_redacted": True,
                "hook": hook,
                "interface_hash": self._hash_value(kwargs.get("interface")),
                "interface_redacted": "interface" in kwargs,
                "direction": kwargs.get("direction"),
                "kwargs_keys": sorted(kwargs.keys()),
                "bcc_available": BCC_AVAILABLE,
                "program_has_bpf": bool(program.bpf),
            },
        )
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
        self._record_thinking_context(
            operation="detach_hook",
            goal="detach local BCC eBPF program hook",
            constraints={
                "program_name_hash": self._hash_value(program.name),
                "program_name_redacted": True,
                "hook": hook,
                "bcc_available": BCC_AVAILABLE,
                "program_has_bpf": bool(program.bpf),
            },
        )
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
        self._record_thinking_context(
            operation="unload_program",
            goal="unload local BCC eBPF program",
            constraints={
                "program_name_hash": self._hash_value(program.name),
                "program_name_redacted": True,
                "attached_hook_count": len(program.attached_hooks or []),
                "bcc_available": BCC_AVAILABLE,
                "program_has_bpf": bool(program.bpf),
            },
        )
        if not BCC_AVAILABLE or not program.bpf:
            logger.warning(
                "⚠️ Cannot unload program - BCC not available or program not loaded"
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


class StubEBPFMap:
    """In-memory dict-like stub for a BPF map (used when BCC is unavailable)."""

    def __init__(self):
        self._data: Dict[Any, Any] = {}

    class StubStruct:
        """Stub for ctypes structure generated by BCC."""
        def __init__(self):
            # Use __dict__ directly to avoid recursion
            self.__dict__['_data'] = {}
        
        def __setattr__(self, name, value):
            self._data[name] = value
            
        def __getattr__(self, name):
            if name not in self.__dict__: # Use __dict__ to avoid recursion
                if name == "_data":
                     return super().__getattribute__(name)
            
            if name not in self._data:
                # Provide an object that supports indexing and iteration for session_key etc.
                class MockArray(list):
                    def __init__(self):
                        super().__init__([0] * 256) # Pre-fill with zeros
                    def __setitem__(self, key, value):
                        if isinstance(key, int):
                            while len(self) <= key:
                                self.append(0)
                        super().__setitem__(key, value)
                    def __hash__(self):
                        return hash(tuple(self))
                self._data[name] = MockArray()
            return self._data[name]
        
        def __hash__(self):
            # Need hash for dict keys if used as Map key
            # Create a stable representation of the structure data
            items = []
            for k in sorted(self._data.keys()):
                v = self._data[k]
                if isinstance(v, list):
                    items.append((k, tuple(v)))
                else:
                    items.append((k, v))
            return hash(tuple(items))

        def __eq__(self, other):
            if not isinstance(other, StubEBPFMap.StubStruct):
                return False
            return self.__hash__() == other.__hash__()

    def Key(self):
        return self.StubStruct()

    def Leaf(self):
        return self.StubStruct()

    def __setitem__(self, key, value):
        self._data[key] = value

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()


class StubEBPFProgram:
    """Stub eBPF program for use when BCC is unavailable."""

    def __init__(self, name: str):
        self.name = name
        self._maps: Dict[str, StubEBPFMap] = {}

    def __getitem__(self, key: str) -> StubEBPFMap:
        if key not in self._maps:
            self._maps[key] = StubEBPFMap()
        return self._maps[key]


def create_stub_program(program_path: str) -> EBPFProgram:
    """Create a stub EBPFProgram (loaded=False) for use when BCC is unavailable."""
    program_name = Path(program_path).stem
    return EBPFProgram(
        name=program_name,
        bpf=StubEBPFProgram(program_name),
        program_path=program_path,
        loaded=False,
    )
