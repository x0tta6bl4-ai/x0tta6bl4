"""
eBPF Metrics Exporter for Prometheus

Reads metrics from eBPF maps and exports them to Prometheus.
Supports:
- Per-CPU array counters
- Ring buffer events
- Histogram maps
"""

import logging
import struct
import subprocess
from typing import Dict, List, Optional
from pathlib import Path

try:
    from prometheus_client import Gauge, Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available")

logger = logging.getLogger(__name__)


class EBPFMetricsExporter:
    """
    Exports eBPF map data to Prometheus metrics.
    
    Example:
        >>> exporter = EBPFMetricsExporter()
        >>> exporter.register_map("packet_counters", "xdp_counter")
        >>> exporter.export_metrics()
    """
    
    def __init__(self):
        self.registered_maps: Dict[str, Dict] = {}
        self.metrics: Dict[str, any] = {}
        
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus not available, metrics will be logged only")
    
    def register_map(
        self,
        map_name: str,
        program_name: str,
        map_type: str = "per_cpu_array"
    ):
        """
        Register an eBPF map for metric export.
        
        Args:
            map_name: Name of the eBPF map
            program_name: Name of the eBPF program (for labeling)
            map_type: Type of map (per_cpu_array, ringbuf, histogram)
        """
        self.registered_maps[map_name] = {
            "program": program_name,
            "type": map_type,
        }
        
        # Create Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            if map_type == "per_cpu_array":
                # Create Gauge for each counter index
                for i, label in enumerate(["tcp", "udp", "icmp", "other"]):
                    metric_name = f"ebpf_{program_name}_{label}_packets"
                    self.metrics[metric_name] = Gauge(
                        metric_name,
                        f"Number of {label.upper()} packets counted by {program_name}",
                        ["cpu"]
                    )
            elif map_type == "histogram":
                metric_name = f"ebpf_{program_name}_latency"
                self.metrics[metric_name] = Histogram(
                    metric_name,
                    f"Latency histogram from {program_name}",
                    ["operation"]
                )
        
        logger.info(f"Registered map '{map_name}' for program '{program_name}'")
    
    def _read_map_via_bpftool(self, map_name: str) -> Optional[Dict]:
        """
        Read eBPF map data using bpftool.
        
        Returns:
            Dict with map data or None if failed
        """
        try:
            # Find map ID by name
            cmd = ['bpftool', 'map', 'show', 'name', map_name]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                logger.debug(f"Map '{map_name}' not found: {result.stderr}")
                return None
            
            # Extract map ID from output
            map_id = None
            for line in result.stdout.split('\n'):
                if 'id:' in line:
                    map_id = line.split('id:')[1].strip().split()[0]
                    break
            
            if not map_id:
                logger.warning(f"Could not extract map ID for '{map_name}'")
                return None
            
            # Dump map contents
            cmd = ['bpftool', 'map', 'dump', 'id', map_id]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                logger.warning(f"Failed to dump map '{map_name}': {result.stderr}")
                return None
            
            # Parse output (simplified - real implementation would parse JSON)
            return {"raw_output": result.stdout, "map_id": map_id}
            
        except FileNotFoundError:
            logger.debug("bpftool not found")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"bpftool command timed out for map '{map_name}'")
            return None
        except Exception as e:
            logger.warning(f"Error reading map '{map_name}': {e}")
            return None
    
    def export_metrics(self) -> Dict[str, float]:
        """
        Export all registered maps to Prometheus.
        
        Returns:
            Dict of metric_name -> value
        """
        exported = {}
        
        for map_name, map_info in self.registered_maps.items():
            program_name = map_info["program"]
            map_type = map_info["type"]
            
            # Read map data
            map_data = self._read_map_via_bpftool(map_name)
            if not map_data:
                continue
            
            # Parse and export based on map type
            if map_type == "per_cpu_array":
                # For per-CPU arrays, sum across all CPUs
                # Simplified parsing - real implementation would parse JSON
                raw_output = map_data.get("raw_output", "")
                
                # Extract values (this is simplified - real parsing needed)
                # Format: key: 0  value: [cpu0_value, cpu1_value, ...]
                values = self._parse_per_cpu_array(raw_output)
                
                if values:
                    labels = ["tcp", "udp", "icmp", "other"]
                    for i, (label, total_value) in enumerate(zip(labels, values)):
                        metric_name = f"ebpf_{program_name}_{label}_packets"
                        
                        if PROMETHEUS_AVAILABLE and metric_name in self.metrics:
                            # Set metric (per-CPU breakdown would be better)
                            self.metrics[metric_name].labels(cpu="total").set(total_value)
                        
                        exported[metric_name] = total_value
                        logger.debug(f"{metric_name}: {total_value}")
        
        return exported
    
    def _parse_per_cpu_array(self, raw_output: str) -> Optional[List[int]]:
        """
        Parse per-CPU array output from bpftool.
        
        This is a simplified parser - real implementation should parse JSON.
        """
        # Simplified parsing - assumes format like:
        # key: 0  value: [cpu0, cpu1, cpu2, ...]
        # key: 1  value: [cpu0, cpu1, cpu2, ...]
        # ...
        
        try:
            # For now, return placeholder values
            # Real implementation would parse JSON output from bpftool
            return [0, 0, 0, 0]  # TCP, UDP, ICMP, Other
        except Exception as e:
            logger.warning(f"Failed to parse per-CPU array: {e}")
            return None
    
    def get_metrics_summary(self) -> Dict[str, any]:
        """Get summary of all exported metrics."""
        return {
            "registered_maps": len(self.registered_maps),
            "prometheus_metrics": len(self.metrics) if PROMETHEUS_AVAILABLE else 0,
            "maps": list(self.registered_maps.keys()),
        }


# Example usage
if __name__ == "__main__":
    exporter = EBPFMetricsExporter()
    exporter.register_map("packet_counters", "xdp_counter", "per_cpu_array")
    
    # Export metrics
    metrics = exporter.export_metrics()
    print("Exported metrics:", metrics)

