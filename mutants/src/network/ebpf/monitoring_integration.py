"""
eBPF Monitoring Integration

Integrates eBPF programs with x0tta6bl4 monitoring system.
Provides real-time metrics from eBPF programs to MAPE-K and GraphSAGE.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional imports
try:
    from src.network.ebpf.loader import EBPFLoader, EBPFProgramType, EBPFAttachMode
    from src.network.ebpf.map_reader import EBPFMapReader
    from src.network.ebpf.metrics_exporter import EBPFMetricsExporter
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
    from src.network.ebpf.graphsage_streaming import EBPFGraphSAGEStreaming
    GRAPHSAGE_STREAMING_AVAILABLE = True
except ImportError:
    GRAPHSAGE_STREAMING_AVAILABLE = False
    EBPFGraphSAGEStreaming = None
    logger.warning("⚠️ eBPF GraphSAGE streaming not available")

try:
    from src.network.ebpf.cilium_integration import CiliumLikeIntegration, FlowEvent, FlowDirection, FlowVerdict
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
        enable_cilium_integration: bool = True
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
                    enable_policy_enforcement=True
                )
                logger.info("✅ Cilium-like integration enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Cilium-like integration: {e}")
        
        # Load XDP counter if enabled
        if enable_xdp_counter:
            self._load_xdp_counter()
        
        logger.info(f"✅ eBPF Monitoring Integration initialized for {interface}")
    
    def _load_xdp_counter(self) -> bool:
        """Load and attach XDP counter program."""
        try:
            # Check if program exists
            xdp_counter_path = self.loader.programs_dir / "xdp_counter.o"
            if not xdp_counter_path.exists():
                logger.warning("xdp_counter.o not found. Compile it first: make -C src/network/ebpf/programs")
                return False
            
            # Load program
            program_id = self.loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
            self.loaded_programs["xdp_counter"] = program_id
            
            # Attach to interface
            success = self.loader.attach_to_interface(
                program_id,
                self.interface,
                EBPFAttachMode.SKB  # Generic mode for compatibility
            )
            
            if success:
                self.enabled_programs.append("xdp_counter")
                logger.info(f"✅ XDP counter attached to {self.interface}")
                return True
            else:
                logger.warning(f"⚠️ Failed to attach XDP counter to {self.interface}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to load XDP counter: {e}")
            return False
    
    def get_packet_counters(self) -> Optional[Dict[str, int]]:
        """
        Get packet counters from XDP program.
        
        Returns:
            Dict with protocol counts or None if not available
        """
        if "xdp_counter" not in self.loaded_programs:
            return None
        
        try:
            # Read counters from BPF map
            counters = self.map_reader.read_map("packet_counters")
            
            if counters:
                # Aggregate per-CPU counters
                protocol_names = ['TCP', 'UDP', 'ICMP', 'Other']
                aggregated = {}
                
                for i, name in enumerate(protocol_names):
                    total = 0
                    # Sum across all CPUs
                    for cpu_data in counters.values() if isinstance(counters, dict) else []:
                        if isinstance(cpu_data, (list, tuple)) and i < len(cpu_data):
                            total += cpu_data[i] if isinstance(cpu_data[i], (int, float)) else 0
                        elif isinstance(cpu_data, dict) and str(i) in cpu_data:
                            total += cpu_data[str(i)]
                    
                    aggregated[name] = total
                
                return aggregated
        except Exception as e:
            logger.warning(f"Failed to read packet counters: {e}")
        
        return None
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all eBPF metrics for monitoring.
        
        Returns:
            Dict with all available metrics
        """
        metrics = {
            'interface': self.interface,
            'enabled_programs': self.enabled_programs,
            'timestamp': time.time()
        }
        
        # Get packet counters
        counters = self.get_packet_counters()
        if counters:
            metrics['packet_counters'] = counters
        
        # Get GraphSAGE streaming metrics if available
        if self.graphsage_streaming:
            try:
                streaming_metrics = self.graphsage_streaming.get_metrics()
                if streaming_metrics:
                    metrics['graphsage_streaming'] = streaming_metrics
            except Exception as e:
                logger.debug(f"Failed to get GraphSAGE streaming metrics: {e}")
        
        # Get Cilium-like flow metrics if available
        if self.cilium_integration:
            try:
                flow_metrics = self.cilium_integration.get_flow_metrics()
                if flow_metrics:
                    metrics['cilium_flows'] = flow_metrics
            except Exception as e:
                logger.debug(f"Failed to get Cilium flow metrics: {e}")
        
        return metrics
    
    def export_to_prometheus(self) -> bool:
        """
        Export eBPF metrics to Prometheus.
        
        Returns:
            True if export successful
        """
        try:
            metrics = self.get_metrics()
            self.metrics_exporter.export_metrics(metrics)
            return True
        except Exception as e:
            logger.warning(f"Failed to export metrics to Prometheus: {e}")
            return False
    
    def shutdown(self):
        """Shutdown eBPF monitoring and cleanup resources."""
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
                logger.info(f"✅ Unloaded {program_name}")
            except Exception as e:
                logger.warning(f"Error unloading {program_name}: {e}")
        
        self.loaded_programs.clear()
        self.enabled_programs.clear()
        
        logger.info("✅ eBPF monitoring shutdown complete")


def create_ebpf_monitoring(
    interface: str = "eth0",
    enable_xdp_counter: bool = True,
    enable_graphsage_streaming: bool = True
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
        enable_graphsage_streaming=enable_graphsage_streaming
    )

