"""
Native eBPF Metrics Exporter using BCC.

Reads kernel-level metrics directly from eBPF maps and exposes them to Prometheus.
Specifically designed for network_monitor.bpf.c.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from prometheus_client import Gauge, Counter, CollectorRegistry, generate_latest

try:
    from bcc import BPF
    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False

logger = logging.getLogger(__name__)

# Registry for native eBPF metrics
ebpf_native_registry = CollectorRegistry()

# ==================== Metrics Definitions ====================

packets_ingress = Gauge(
    "x0tta6bl4_ebpf_packets_ingress_total",
    "Total ingress packets observed by eBPF TC/XDP",
    registry=ebpf_native_registry
)

packets_egress = Gauge(
    "x0tta6bl4_ebpf_packets_egress_total",
    "Total egress packets observed by eBPF TC",
    registry=ebpf_native_registry
)

bytes_ingress = Gauge(
    "x0tta6bl4_ebpf_bytes_ingress_total",
    "Total ingress bytes observed by eBPF TC/XDP",
    registry=ebpf_native_registry
)

bytes_egress = Gauge(
    "x0tta6bl4_ebpf_bytes_egress_total",
    "Total egress bytes observed by eBPF TC",
    registry=ebpf_native_registry
)

packet_loss = Gauge(
    "x0tta6bl4_ebpf_packet_loss_total",
    "Total packet drops observed in kernel (kfree_skb)",
    registry=ebpf_native_registry
)

retransmissions = Gauge(
    "x0tta6bl4_ebpf_retransmissions_total",
    "Total TCP retransmissions observed in kernel",
    registry=ebpf_native_registry
)

active_connections = Gauge(
    "x0tta6bl4_ebpf_active_connections_total",
    "Current number of established TCP connections",
    registry=ebpf_native_registry
)

# ==================== Exporter Implementation ====================

class EBPFNativeExporter:
    """
    Native eBPF metrics exporter using BCC.
    """

    def __init__(self, bpf_source_path: str):
        self.bpf_source_path = Path(bpf_source_path)
        self.b = None
        self.running = False
        self._thread = None

    def start(self, interval_seconds: float = 5.0):
        """Start the background metrics polling thread."""
        if not BCC_AVAILABLE:
            logger.error("BCC not available, cannot start native eBPF exporter")
            return

        if not self.bpf_source_path.exists():
            logger.error(f"BPF source file not found: {self.bpf_source_path}")
            return

        try:
            logger.info(f"Loading eBPF program from {self.bpf_source_path}...")
            self.b = BPF(src_file=str(self.bpf_source_path))
            # Programs are assumed to be loaded/attached by the eBPF Orchestrator.
            # Here we just attach to existing maps by name if needed, 
            # or BCC handles it if the maps are defined in the source.
            
            self.running = True
            self._thread = threading.Thread(target=self._poll_loop, args=(interval_seconds,), daemon=True)
            self._thread.start()
            logger.info("Native eBPF exporter started successfully")
        except Exception as e:
            logger.error(f"Failed to start native eBPF exporter: {e}")

    def stop(self):
        """Stop the background polling."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _poll_loop(self, interval: float):
        """Poll eBPF maps and update Prometheus metrics."""
        while self.running:
            try:
                self._update_metrics()
            except Exception as e:
                logger.error(f"Error updating eBPF metrics: {e}")
            time.sleep(interval)

    def _update_metrics(self):
        """Read values from eBPF maps."""
        if not self.b:
            return

        # 1. Update system-wide metrics from 'system_network_map'
        # Map is ARRAY, entry 0 has 'struct system_network_metrics'
        try:
            sys_metrics_map = self.b.get_table("system_network_map")
            if sys_metrics_map:
                for k, v in sys_metrics_map.items():
                    if k.value == 0:
                        packets_ingress.set(v.total_packets_ingress)
                        packets_egress.set(v.total_packets_egress)
                        bytes_ingress.set(v.total_bytes_ingress)
                        bytes_egress.set(v.total_bytes_egress)
                        packet_loss.set(v.total_packet_loss)
                        retransmissions.set(v.total_retransmissions)
                        active_connections.set(v.active_connections)
        except Exception as e:
            logger.debug(f"Failed to read system_network_map: {e}")

        # 2. Update specific packet loss counters if needed
        # (Could be expanded to per-protocol loss)

    def get_metrics_text(self) -> bytes:
        """Return Prometheus text format metrics."""
        return generate_latest(ebpf_native_registry)

# Singleton instance
_exporter: Optional[EBPFNativeExporter] = None

def get_native_exporter() -> EBPFNativeExporter:
    """Get or create the native eBPF exporter."""
    global _exporter
    if _exporter is None:
        source_path = os.getenv("X0T_EBPF_SOURCE", "src/libx0t/network/ebpf/kernel/network_monitor.bpf.c")
        _exporter = EBPFNativeExporter(source_path)
    return _exporter

if __name__ == "__main__":
    # Self-test mode
    logging.basicConfig(level=logging.INFO)
    exp = get_native_exporter()
    exp.start()
    
    try:
        while True:
            print(exp.get_metrics_text().decode())
            time.sleep(10)
    except KeyboardInterrupt:
        exp.stop()

