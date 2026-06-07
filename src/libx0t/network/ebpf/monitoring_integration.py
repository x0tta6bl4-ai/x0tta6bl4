"""
eBPF Monitoring Integration

Integrates eBPF programs with x0tta6bl4 monitoring system.
Provides real-time metrics from eBPF programs to MAPE-K and GraphSAGE.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)

# Optional imports
try:
    from .loader import (EBPFAttachMode, EBPFLoader,
                                         EBPFProgramType)
    from .map_reader import EBPFMapReader
    from .metrics_exporter import EBPFMetricsExporter

    EBPF_AVAILABLE = True
except ImportError:
    EBPF_AVAILABLE = False
    EBPFLoader = None
    EBPFProgramType = None
    EBPFAttachMode = None
    EBPFMapReader = None
    EBPFMetricsExporter = None
    logger.warning("⚠️ eBPF modules not available")

try:
    from .graphsage_streaming import EBPFGraphSAGEStreaming

    GRAPHSAGE_STREAMING_AVAILABLE = True
except ImportError:
    GRAPHSAGE_STREAMING_AVAILABLE = False
    EBPFGraphSAGEStreaming = None
    logger.warning("⚠️ eBPF GraphSAGE streaming not available")

try:
    from .cilium_integration import (CiliumLikeIntegration,
                                                     FlowDirection, FlowEvent,
                                                     FlowVerdict)

    CILIUM_INTEGRATION_AVAILABLE = True
except ImportError:
    CILIUM_INTEGRATION_AVAILABLE = False
    CiliumLikeIntegration = None
    FlowEvent = None
    FlowDirection = None
    FlowVerdict = None
    logger.warning("⚠️ Cilium-like integration not available")


class EBPFMonitoringIntegration:
    """
    Integration layer for eBPF monitoring in x0tta6bl4.

    Provides:
    - Real-time metrics from eBPF programs
    - Integration with MAPE-K monitoring
    - Integration with GraphSAGE anomaly detection
    - Metrics export to Prometheus
    """

    def __init__(
        self,
        interface: str = "eth0",
        enable_xdp_counter: bool = True,
        enable_graphsage_streaming: bool = True,
        enable_cilium_integration: bool = True,
    ):
        """
        Initialize eBPF monitoring integration.

        Args:
            interface: Network interface to monitor
            enable_xdp_counter: Enable XDP packet counter
            enable_graphsage_streaming: Enable GraphSAGE streaming
            enable_cilium_integration: Enable Cilium-like integration
        """
        if not EBPF_AVAILABLE:
            raise ImportError("eBPF modules not available. Install dependencies.")

        self.interface = interface
        self.source_agent = "libx0t-ebpf-monitoring-integration"
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="monitoring",
            capabilities=("security", "zero-trust"),
            extra_techniques=("reverse_planning",),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        self._record_thinking_context(
            operation="init",
            goal="initialize libx0t eBPF monitoring integration",
            constraints={
                "interface_hash": self._hash_value(interface),
                "interface_redacted": True,
                "enable_xdp_counter": enable_xdp_counter,
                "enable_graphsage_streaming": enable_graphsage_streaming,
                "enable_cilium_integration": enable_cilium_integration,
                "local_integration_is_not_dataplane_proof": True,
            },
        )
        self.loader = EBPFLoader()
        self.map_reader = EBPFMapReader()
        self.metrics_exporter = EBPFMetricsExporter()

        self.loaded_programs: Dict[str, str] = {}  # program_name -> program_id
        self.enabled_programs: List[str] = []

        # GraphSAGE streaming
        self.graphsage_streaming = None
        if enable_graphsage_streaming and GRAPHSAGE_STREAMING_AVAILABLE:
            try:
                self.graphsage_streaming = EBPFGraphSAGEStreaming()
                logger.info("✅ eBPF GraphSAGE streaming enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize GraphSAGE streaming: {e}")

        # Cilium-like integration
        self.cilium_integration = None
        if enable_cilium_integration and CILIUM_INTEGRATION_AVAILABLE:
            try:
                self.cilium_integration = CiliumLikeIntegration(
                    interface=interface,
                    enable_flow_observability=True,
                    enable_policy_enforcement=True,
                )
                logger.info("✅ Cilium-like integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Cilium-like integration: {e}")

        # Load XDP counter if enabled
        if enable_xdp_counter:
            self._load_xdp_counter()

        logger.info(f"✅ eBPF Monitoring Integration initialized for {interface}")

    @staticmethod
    def _hash_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return hashlib.sha256(value).hexdigest()
        return hashlib.sha256(
            str(value).encode("utf-8", errors="replace")
        ).hexdigest()

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                "libx0t-ebpf-monitoring-integration",
            )
            coach = AgentThinkingCoach(
                agent_id=self.source_agent,
                role="monitoring",
                capabilities=("security", "zero-trust"),
                extra_techniques=("reverse_planning",),
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
            "task_type": "libx0t_ebpf_monitoring_integration_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                "local_integration_is_not_dataplane_proof": True,
                "local_integration_is_not_kernel_load_proof": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local libx0t eBPF monitoring integration decisions, "
                "hashed interface selectors, feature flags, counts, and status; "
                "do not expose raw interface names, flow payloads, map contents, "
                "or exporter payloads. Local object load attempts are not proof "
                "of live dataplane delivery."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose libx0t eBPF monitoring thinking state without raw payloads."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _load_xdp_counter(self) -> bool:
        """Load and attach XDP counter program."""
        self._record_thinking_context(
            operation="load_xdp_counter",
            goal="load and attach the XDP packet counter when available",
            constraints={
                "interface_hash": self._hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "loaded_programs_count": len(getattr(self, "loaded_programs", {})),
                "enabled_programs_count": len(getattr(self, "enabled_programs", [])),
            },
        )
        try:
            # Check if program exists
            xdp_counter_path = self.loader.programs_dir / "xdp_counter.o"
            if not xdp_counter_path.exists():
                self._record_thinking_context(
                    operation="load_xdp_counter",
                    goal="skip XDP packet counter because object file is missing",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "program_name": "xdp_counter",
                        "object_path_redacted": True,
                        "status": "missing_object",
                    },
                )
                logger.warning(
                    "xdp_counter.o not found. Compile it first: make -C src/network/ebpf/programs"
                )
                return False

            # Load program
            program_id = self.loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
            self.loaded_programs["xdp_counter"] = program_id

            # Attach to interface
            success = self.loader.attach_to_interface(
                program_id,
                self.interface,
                EBPFAttachMode.SKB,  # Generic mode for compatibility
            )

            if success:
                self.enabled_programs.append("xdp_counter")
                self._record_thinking_context(
                    operation="load_xdp_counter",
                    goal="XDP packet counter attached successfully",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "program_name": "xdp_counter",
                        "program_id_hash": self._hash_value(program_id),
                        "status": "success",
                    },
                )
                logger.info(f"✅ XDP counter attached to {self.interface}")
                return True
            else:
                self._record_thinking_context(
                    operation="load_xdp_counter",
                    goal="XDP packet counter load succeeded but attach failed",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "program_name": "xdp_counter",
                        "program_id_hash": self._hash_value(program_id),
                        "status": "attach_failed",
                    },
                )
                logger.warning(f"⚠️ Failed to attach XDP counter to {self.interface}")
                return False

        except Exception as e:
            self._record_thinking_context(
                operation="load_xdp_counter",
                goal="XDP packet counter load or attach raised an error",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "error_type": type(e).__name__,
                    "error_message_hash": self._hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )
            logger.error(f"❌ Failed to load XDP counter: {e}")
            return False

    def get_packet_counters(self) -> Optional[Dict[str, int]]:
        """
        Get packet counters from XDP program.

        Returns:
            Dict with protocol counts or None if not available
        """
        if "xdp_counter" not in self.loaded_programs:
            self._record_thinking_context(
                operation="get_packet_counters",
                goal="skip packet counter read because XDP counter is not loaded",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "xdp_counter_loaded": False,
                },
            )
            return None

        try:
            self._record_thinking_context(
                operation="get_packet_counters",
                goal="read packet counter map and aggregate per-CPU counters",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "map_name": "packet_counters",
                    "map_values_redacted": True,
                    "xdp_counter_loaded": True,
                },
            )
            # Read counters from BPF map
            counters = self.map_reader.read_map("packet_counters")

            if counters:
                # Aggregate per-CPU counters
                protocol_names = ["TCP", "UDP", "ICMP", "Other"]
                aggregated = {}

                for i, name in enumerate(protocol_names):
                    total = 0
                    # Sum across all CPUs
                    for cpu_data in (
                        counters.values() if isinstance(counters, dict) else []
                    ):
                        if isinstance(cpu_data, (list, tuple)) and i < len(cpu_data):
                            total += (
                                cpu_data[i]
                                if isinstance(cpu_data[i], (int, float))
                                else 0
                            )
                        elif isinstance(cpu_data, dict) and str(i) in cpu_data:
                            total += cpu_data[str(i)]

                    aggregated[name] = total

                self._record_thinking_context(
                    operation="get_packet_counters",
                    goal="packet counters aggregated successfully",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "protocol_names": list(aggregated.keys()),
                        "counter_values_redacted": True,
                        "status": "success",
                    },
                )
                return aggregated
        except Exception as e:
            self._record_thinking_context(
                operation="get_packet_counters",
                goal="packet counter map read failed",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "map_name": "packet_counters",
                    "error_type": type(e).__name__,
                    "error_message_hash": self._hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )
            logger.warning(f"Failed to read packet counters: {e}")

        return None

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all eBPF metrics for monitoring.

        Returns:
            Dict with all available metrics
        """
        self._record_thinking_context(
            operation="get_metrics",
            goal="collect available libx0t eBPF monitoring metrics",
            constraints={
                "interface_hash": self._hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "enabled_programs_count": len(getattr(self, "enabled_programs", [])),
                "loaded_programs_count": len(getattr(self, "loaded_programs", {})),
                "graphsage_streaming_enabled": bool(
                    getattr(self, "graphsage_streaming", None)
                ),
                "cilium_integration_enabled": bool(
                    getattr(self, "cilium_integration", None)
                ),
            },
        )
        metrics = {
            "interface": self.interface,
            "enabled_programs": self.enabled_programs,
            "timestamp": time.time(),
        }

        # Get packet counters
        counters = self.get_packet_counters()
        if counters:
            metrics["packet_counters"] = counters

        # Get GraphSAGE streaming metrics if available
        if self.graphsage_streaming:
            try:
                streaming_metrics = self.graphsage_streaming.get_metrics()
                if streaming_metrics:
                    metrics["graphsage_streaming"] = streaming_metrics
                    self._record_thinking_context(
                        operation="get_metrics",
                        goal="GraphSAGE streaming metrics were included",
                        constraints={
                            "interface_hash": self._hash_value(
                                getattr(self, "interface", None)
                            ),
                            "interface_redacted": True,
                            "graphsage_metric_keys": sorted(
                                str(key) for key in streaming_metrics.keys()
                            )
                            if isinstance(streaming_metrics, dict)
                            else [],
                            "graphsage_metric_values_redacted": True,
                        },
                    )
            except Exception as e:
                self._record_thinking_context(
                    operation="get_metrics",
                    goal="GraphSAGE streaming metric read failed",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "error_type": type(e).__name__,
                        "error_message_hash": self._hash_value(str(e)),
                        "error_message_redacted": True,
                    },
                )
                logger.debug(f"Failed to get GraphSAGE streaming metrics: {e}")

        # Get Cilium-like flow metrics if available
        if self.cilium_integration:
            try:
                flow_metrics = self.cilium_integration.get_flow_metrics()
                if flow_metrics:
                    metrics["cilium_flows"] = flow_metrics
                    self._record_thinking_context(
                        operation="get_metrics",
                        goal="Cilium-like flow metrics were included",
                        constraints={
                            "interface_hash": self._hash_value(
                                getattr(self, "interface", None)
                            ),
                            "interface_redacted": True,
                            "cilium_metric_keys": sorted(
                                str(key) for key in flow_metrics.keys()
                            )
                            if isinstance(flow_metrics, dict)
                            else [],
                            "cilium_metric_values_redacted": True,
                        },
                    )
            except Exception as e:
                self._record_thinking_context(
                    operation="get_metrics",
                    goal="Cilium-like flow metric read failed",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "error_type": type(e).__name__,
                        "error_message_hash": self._hash_value(str(e)),
                        "error_message_redacted": True,
                    },
                )
                logger.debug(f"Failed to get Cilium flow metrics: {e}")

        return metrics

    def export_to_prometheus(self) -> bool:
        """
        Export eBPF metrics to Prometheus.

        Returns:
            True if export successful
        """
        try:
            self._record_thinking_context(
                operation="export_to_prometheus",
                goal="export current libx0t eBPF metrics to Prometheus exporter",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "export_payload_redacted": True,
                },
            )
            metrics = self.get_metrics()
            self.metrics_exporter.export_metrics(metrics)
            self._record_thinking_context(
                operation="export_to_prometheus",
                goal="Prometheus export completed",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "metric_keys": sorted(str(key) for key in metrics.keys()),
                    "metric_values_redacted": True,
                    "status": "success",
                },
            )
            return True
        except Exception as e:
            self._record_thinking_context(
                operation="export_to_prometheus",
                goal="Prometheus export failed",
                constraints={
                    "interface_hash": self._hash_value(
                        getattr(self, "interface", None)
                    ),
                    "interface_redacted": True,
                    "error_type": type(e).__name__,
                    "error_message_hash": self._hash_value(str(e)),
                    "error_message_redacted": True,
                },
            )
            logger.warning(f"Failed to export metrics to Prometheus: {e}")
            return False

    def shutdown(self):
        """Shutdown eBPF monitoring and cleanup resources."""
        self._record_thinking_context(
            operation="shutdown",
            goal="detach and unload libx0t eBPF monitoring resources",
            constraints={
                "interface_hash": self._hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "loaded_programs_count": len(getattr(self, "loaded_programs", {})),
                "enabled_programs_count": len(getattr(self, "enabled_programs", [])),
            },
        )
        logger.info("Shutting down eBPF monitoring...")

        # Shutdown Cilium-like integration
        if self.cilium_integration:
            try:
                self.cilium_integration.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down Cilium integration: {e}")

        # Detach and unload all programs
        for program_name, program_id in self.loaded_programs.items():
            try:
                program_info = self.loader.loaded_programs.get(program_id, {})
                attached_to = program_info.get("attached_to")

                if attached_to:
                    self.loader.detach_from_interface(program_id, attached_to)

                self.loader.unload_program(program_id)
                self._record_thinking_context(
                    operation="shutdown",
                    goal="unloaded one libx0t eBPF monitoring program",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "program_name": program_name,
                        "program_id_hash": self._hash_value(program_id),
                        "attached_to_hash": self._hash_value(attached_to),
                        "attached_to_redacted": attached_to is not None,
                        "status": "success",
                    },
                )
                logger.info(f"✅ Unloaded {program_name}")
            except Exception as e:
                self._record_thinking_context(
                    operation="shutdown",
                    goal="unload of one libx0t eBPF monitoring program failed",
                    constraints={
                        "interface_hash": self._hash_value(
                            getattr(self, "interface", None)
                        ),
                        "interface_redacted": True,
                        "program_name": program_name,
                        "program_id_hash": self._hash_value(program_id),
                        "error_type": type(e).__name__,
                        "error_message_hash": self._hash_value(str(e)),
                        "error_message_redacted": True,
                    },
                )
                logger.warning(f"Error unloading {program_name}: {e}")

        self.loaded_programs.clear()
        self.enabled_programs.clear()

        self._record_thinking_context(
            operation="shutdown",
            goal="libx0t eBPF monitoring shutdown completed",
            constraints={
                "interface_hash": self._hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "loaded_programs_count": len(getattr(self, "loaded_programs", {})),
                "enabled_programs_count": len(getattr(self, "enabled_programs", [])),
                "status": "success",
            },
        )

        logger.info("✅ eBPF monitoring shutdown complete")


def create_ebpf_monitoring(
    interface: str = "eth0",
    enable_xdp_counter: bool = True,
    enable_graphsage_streaming: bool = True,
) -> EBPFMonitoringIntegration:
    """
    Factory function to create eBPF monitoring integration.

    Args:
        interface: Network interface to monitor
        enable_xdp_counter: Enable XDP packet counter
        enable_graphsage_streaming: Enable GraphSAGE streaming

    Returns:
        EBPFMonitoringIntegration instance
    """
    return EBPFMonitoringIntegration(
        interface=interface,
        enable_xdp_counter=enable_xdp_counter,
        enable_graphsage_streaming=enable_graphsage_streaming,
    )
