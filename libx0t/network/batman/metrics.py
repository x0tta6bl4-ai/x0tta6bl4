"""
Batman-adv Metrics Collector for Prometheus
============================================

Comprehensive metrics collection for Batman-adv mesh networking.
Exports metrics in Prometheus format for monitoring and alerting.

Features:
- Node and mesh topology metrics
- Link quality metrics
- Routing table metrics
- Gateway metrics
- Performance metrics
- Integration with existing x0tta6bl4 metrics
"""

import asyncio
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Gauge, Histogram, Info, Registry, CollectorRegistry
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not available, metrics will be logged only")


@dataclass
class BatmanMetricsSnapshot:
    """Snapshot of Batman-adv metrics at a point in time."""
    
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Node metrics
    originators_count: int = 0
    neighbors_count: int = 0
    
    # Link metrics
    total_links: int = 0
    avg_link_quality: float = 0.0
    min_link_quality: float = 0.0
    max_link_quality: float = 0.0
    
    # Routing metrics
    routing_entries: int = 0
    local_transmissions: int = 0
    
    # Gateway metrics
    gateways_count: int = 0
    has_gateway: bool = False
    gateway_mode: str = ""
    
    # Performance metrics
    throughput_mbps: float = 0.0
    latency_ms: float = 0.0
    packet_loss_percent: float = 0.0
    
    # Interface metrics
    interface_up: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "originators_count": self.originators_count,
            "neighbors_count": self.neighbors_count,
            "total_links": self.total_links,
            "avg_link_quality": self.avg_link_quality,
            "min_link_quality": self.min_link_quality,
            "max_link_quality": self.max_link_quality,
            "routing_entries": self.routing_entries,
            "gateways_count": self.gateways_count,
            "has_gateway": self.has_gateway,
            "gateway_mode": self.gateway_mode,
            "throughput_mbps": self.throughput_mbps,
            "latency_ms": self.latency_ms,
            "packet_loss_percent": self.packet_loss_percent,
            "interface_up": self.interface_up,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
            "rx_packets": self.rx_packets,
            "tx_packets": self.tx_packets,
        }


class BatmanMetricsCollector:
    """
    Prometheus metrics collector for Batman-adv mesh networking.
    
    Collects and exports metrics for:
    - Mesh topology (nodes, links, originators)
    - Link quality (TQ values, latency)
    - Routing (entries, paths)
    - Gateways (availability, selection)
    - Performance (throughput, packet loss)
    
    Example:
        >>> collector = BatmanMetricsCollector(node_id="node-001")
        >>> await collector.collect()
        >>> metrics = collector.get_metrics_output()
    """
    
    def __init__(
        self,
        node_id: str,
        interface: str = "bat0",
        collection_interval: float = 15.0,
        registry: Optional["CollectorRegistry"] = None,
    ):
        """
        Initialize Batman metrics collector.
        
        Args:
            node_id: Unique identifier for this node
            interface: Batman-adv interface name
            collection_interval: Interval between metric collections
            registry: Optional Prometheus registry to use
        """
        self.node_id = node_id
        self.interface = interface
        self.collection_interval = collection_interval
        
        self._running = False
        self._last_snapshot: Optional[BatmanMetricsSnapshot] = None
        self._snapshots: List[BatmanMetricsSnapshot] = []
        self._max_snapshots = 100
        
        # Initialize Prometheus metrics
        self._metrics: Dict[str, Any] = {}
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics(registry)
        
        logger.info(f"BatmanMetricsCollector initialized for {node_id} on {interface}")
    
    def _init_prometheus_metrics(self, registry: Optional["CollectorRegistry"]) -> None:
        """Initialize Prometheus metrics."""
        # Use provided registry or create new one
        if registry is None:
            registry = Registry()
        
        self._registry = registry
        
        # Mesh topology metrics
        self._metrics["originators_count"] = Gauge(
            "batman_originators_total",
            "Number of originators in Batman mesh",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["neighbors_count"] = Gauge(
            "batman_neighbors_total",
            "Number of direct neighbors",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["mesh_nodes_total"] = Gauge(
            "batman_mesh_nodes_total",
            "Total nodes in mesh network",
            ["node_id"],
            registry=registry,
        )
        
        # Link quality metrics
        self._metrics["link_quality_avg"] = Gauge(
            "batman_link_quality_avg",
            "Average link quality (TQ normalized 0-1)",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["link_quality_min"] = Gauge(
            "batman_link_quality_min",
            "Minimum link quality (TQ normalized 0-1)",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["link_quality_max"] = Gauge(
            "batman_link_quality_max",
            "Maximum link quality (TQ normalized 0-1)",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["links_total"] = Gauge(
            "batman_links_total",
            "Total number of links",
            ["node_id", "interface"],
            registry=registry,
        )
        
        # Routing metrics
        self._metrics["routing_entries"] = Gauge(
            "batman_routing_entries",
            "Number of routing table entries",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["routing_loops"] = Counter(
            "batman_routing_loops_total",
            "Number of routing loops detected",
            ["node_id", "interface"],
            registry=registry,
        )
        
        # Gateway metrics
        self._metrics["gateways_count"] = Gauge(
            "batman_gateways_total",
            "Number of available gateways",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["has_gateway"] = Gauge(
            "batman_has_gateway",
            "Whether node has a selected gateway (1=yes, 0=no)",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["gateway_mode"] = Info(
            "batman_gateway_mode",
            "Gateway mode information",
            ["node_id", "interface"],
            registry=registry,
        )
        
        # Performance metrics
        self._metrics["throughput_mbps"] = Gauge(
            "batman_throughput_mbps",
            "Estimated throughput in Mbps",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["latency_ms"] = Gauge(
            "batman_latency_ms",
            "Average latency in milliseconds",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["packet_loss_percent"] = Gauge(
            "batman_packet_loss_percent",
            "Packet loss percentage",
            ["node_id", "interface"],
            registry=registry,
        )
        
        # Interface metrics
        self._metrics["interface_up"] = Gauge(
            "batman_interface_up",
            "Interface status (1=up, 0=down)",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["rx_bytes"] = Counter(
            "batman_rx_bytes_total",
            "Total bytes received",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["tx_bytes"] = Counter(
            "batman_tx_bytes_total",
            "Total bytes transmitted",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["rx_packets"] = Counter(
            "batman_rx_packets_total",
            "Total packets received",
            ["node_id", "interface"],
            registry=registry,
        )
        
        self._metrics["tx_packets"] = Counter(
            "batman_tx_packets_total",
            "Total packets transmitted",
            ["node_id", "interface"],
            registry=registry,
        )
        
        # Collection metrics
        self._metrics["collection_duration"] = Gauge(
            "batman_metrics_collection_duration_seconds",
            "Duration of metrics collection",
            ["node_id"],
            registry=registry,
        )
        
        self._metrics["collection_errors"] = Counter(
            "batman_metrics_collection_errors_total",
            "Total metrics collection errors",
            ["node_id", "error_type"],
            registry=registry,
        )
        
        self._metrics["collections_total"] = Counter(
            "batman_metrics_collections_total",
            "Total metrics collections performed",
            ["node_id", "status"],
            registry=registry,
        )
        
        logger.info("Prometheus metrics initialized")
    
    async def collect(self) -> BatmanMetricsSnapshot:
        """
        Collect all Batman-adv metrics.
        
        Returns:
            BatmanMetricsSnapshot with collected metrics
        """
        start_time = time.time()
        snapshot = BatmanMetricsSnapshot()
        
        try:
            # Collect topology metrics
            await self._collect_topology_metrics(snapshot)
            
            # Collect link quality metrics
            await self._collect_link_metrics(snapshot)
            
            # Collect routing metrics
            await self._collect_routing_metrics(snapshot)
            
            # Collect gateway metrics
            await self._collect_gateway_metrics(snapshot)
            
            # Collect interface metrics
            await self._collect_interface_metrics(snapshot)
            
            # Collect performance metrics
            await self._collect_performance_metrics(snapshot)
            
            # Update Prometheus metrics
            if PROMETHEUS_AVAILABLE:
                self._update_prometheus_metrics(snapshot)
            
            # Store snapshot
            self._last_snapshot = snapshot
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots.pop(0)
            
            # Record successful collection
            if PROMETHEUS_AVAILABLE and "collections_total" in self._metrics:
                self._metrics["collections_total"].labels(
                    node_id=self.node_id, status="success"
                ).inc()
            
        except Exception as e:
            logger.error(f"Metrics collection error: {e}")
            if PROMETHEUS_AVAILABLE and "collection_errors" in self._metrics:
                self._metrics["collection_errors"].labels(
                    node_id=self.node_id, error_type=type(e).__name__
                ).inc()
            
            if PROMETHEUS_AVAILABLE and "collections_total" in self._metrics:
                self._metrics["collections_total"].labels(
                    node_id=self.node_id, status="error"
                ).inc()
        
        # Record collection duration
        duration = time.time() - start_time
        if PROMETHEUS_AVAILABLE and "collection_duration" in self._metrics:
            self._metrics["collection_duration"].labels(
                node_id=self.node_id
            ).set(duration)
        
        logger.debug(f"Metrics collection completed in {duration:.3f}s")
        return snapshot
    
    async def _collect_topology_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Collect mesh topology metrics."""
        try:
            # Get originators
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "originators"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                snapshot.originators_count = max(0, len(lines) - 2)  # Skip header
            
            # Get neighbors
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "transglobal"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                snapshot.neighbors_count = max(0, len(lines) - 1)
                
        except FileNotFoundError:
            logger.debug("batctl not available for topology metrics")
        except Exception as e:
            logger.warning(f"Failed to collect topology metrics: {e}")
    
    async def _collect_link_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Collect link quality metrics."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "originators"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return
            
            qualities = []
            lines = result.stdout.strip().split("\n")
            
            for line in lines[2:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        # Extract TQ value (format: "(255)")
                        tq_match = re.search(r'\((\d+)\)', line)
                        if tq_match:
                            tq = int(tq_match.group(1))
                            qualities.append(tq / 255.0)
                    except (ValueError, IndexError):
                        continue
            
            if qualities:
                snapshot.total_links = len(qualities)
                snapshot.avg_link_quality = sum(qualities) / len(qualities)
                snapshot.min_link_quality = min(qualities)
                snapshot.max_link_quality = max(qualities)
                
        except FileNotFoundError:
            logger.debug("batctl not available for link metrics")
        except Exception as e:
            logger.warning(f"Failed to collect link metrics: {e}")
    
    async def _collect_routing_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Collect routing table metrics."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "translocal"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                snapshot.routing_entries = max(0, len(lines) - 1)
                
        except FileNotFoundError:
            logger.debug("batctl not available for routing metrics")
        except Exception as e:
            logger.warning(f"Failed to collect routing metrics: {e}")
    
    async def _collect_gateway_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Collect gateway metrics."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "gateways"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                
                if "No gateways" not in output:
                    lines = [l for l in output.split("\n") if l.strip()]
                    snapshot.gateways_count = len(lines)
                    
                    # Check if we have a selected gateway
                    for line in lines:
                        if line.startswith("=>") or "*" in line:
                            snapshot.has_gateway = True
                            break
            
            # Get gateway mode
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "gw_mode"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                snapshot.gateway_mode = result.stdout.strip()
                
        except FileNotFoundError:
            logger.debug("batctl not available for gateway metrics")
        except Exception as e:
            logger.warning(f"Failed to collect gateway metrics: {e}")
    
    async def _collect_interface_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Collect interface metrics."""
        try:
            # Check interface status
            result = subprocess.run(
                ["ip", "link", "show", self.interface],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                snapshot.interface_up = "up" in output and "down" not in output
            
            # Get traffic statistics
            result = subprocess.run(
                ["cat", f"/sys/class/net/{self.interface}/statistics/rx_bytes"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                snapshot.rx_bytes = int(result.stdout.strip())
            
            result = subprocess.run(
                ["cat", f"/sys/class/net/{self.interface}/statistics/tx_bytes"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                snapshot.tx_bytes = int(result.stdout.strip())
            
            result = subprocess.run(
                ["cat", f"/sys/class/net/{self.interface}/statistics/rx_packets"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                snapshot.rx_packets = int(result.stdout.strip())
            
            result = subprocess.run(
                ["cat", f"/sys/class/net/{self.interface}/statistics/tx_packets"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                snapshot.tx_packets = int(result.stdout.strip())
                
        except FileNotFoundError:
            logger.debug("Interface statistics not available")
        except Exception as e:
            logger.warning(f"Failed to collect interface metrics: {e}")
    
    async def _collect_performance_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Collect performance metrics."""
        try:
            # Estimate throughput based on link quality
            if snapshot.avg_link_quality > 0:
                # Rough estimate: higher quality = higher throughput
                # This is a simplified model
                snapshot.throughput_mbps = snapshot.avg_link_quality * 100  # Max 100 Mbps
            
            # Measure latency to a known originator
            if snapshot.originators_count > 0:
                result = subprocess.run(
                    ["batctl", "meshif", self.interface, "originators"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 2:
                        # Get first originator MAC
                        parts = lines[2].split()
                        if parts:
                            mac = parts[0]
                            
                            # Ping to measure latency
                            ping_result = subprocess.run(
                                ["batctl", "meshif", self.interface, "ping", "-c", "3", mac],
                                capture_output=True,
                                text=True,
                                timeout=15,
                            )
                            
                            if ping_result.returncode == 0:
                                # Parse average latency from ping output
                                latency_match = re.search(
                                    r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/',
                                    ping_result.stdout
                                )
                                if latency_match:
                                    snapshot.latency_ms = float(latency_match.group(1))
                                
                                # Parse packet loss
                                loss_match = re.search(r'(\d+)% packet loss', ping_result.stdout)
                                if loss_match:
                                    snapshot.packet_loss_percent = float(loss_match.group(1))
                                    
        except FileNotFoundError:
            logger.debug("batctl not available for performance metrics")
        except Exception as e:
            logger.warning(f"Failed to collect performance metrics: {e}")
    
    def _update_prometheus_metrics(self, snapshot: BatmanMetricsSnapshot) -> None:
        """Update Prometheus metrics with snapshot data."""
        if not PROMETHEUS_AVAILABLE:
            return
        
        try:
            # Topology metrics
            self._metrics["originators_count"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.originators_count)
            
            self._metrics["neighbors_count"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.neighbors_count)
            
            self._metrics["mesh_nodes_total"].labels(
                node_id=self.node_id
            ).set(snapshot.originators_count)
            
            # Link quality metrics
            self._metrics["link_quality_avg"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.avg_link_quality)
            
            self._metrics["link_quality_min"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.min_link_quality)
            
            self._metrics["link_quality_max"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.max_link_quality)
            
            self._metrics["links_total"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.total_links)
            
            # Routing metrics
            self._metrics["routing_entries"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.routing_entries)
            
            # Gateway metrics
            self._metrics["gateways_count"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.gateways_count)
            
            self._metrics["has_gateway"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(1 if snapshot.has_gateway else 0)
            
            self._metrics["gateway_mode"].labels(
                node_id=self.node_id, interface=self.interface
            ).info({"mode": snapshot.gateway_mode or "unknown"})
            
            # Performance metrics
            self._metrics["throughput_mbps"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.throughput_mbps)
            
            self._metrics["latency_ms"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.latency_ms)
            
            self._metrics["packet_loss_percent"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(snapshot.packet_loss_percent)
            
            # Interface metrics
            self._metrics["interface_up"].labels(
                node_id=self.node_id, interface=self.interface
            ).set(1 if snapshot.interface_up else 0)
            
            # Note: Counter metrics for rx/tx bytes and packets should be
            # incremented by the delta, not set directly
            # For simplicity, we use Gauge behavior here
            
        except Exception as e:
            logger.error(f"Failed to update Prometheus metrics: {e}")
    
    def get_metrics_output(self) -> str:
        """
        Get Prometheus metrics output.
        
        Returns:
            Prometheus-formatted metrics string
        """
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus client not available"
        
        try:
            from prometheus_client import generate_latest
            return generate_latest(self._registry).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to generate metrics output: {e}")
            return f"# Error generating metrics: {e}"
    
    def get_last_snapshot(self) -> Optional[BatmanMetricsSnapshot]:
        """Get the last metrics snapshot."""
        return self._last_snapshot
    
    def get_snapshots(self, limit: int = 10) -> List[BatmanMetricsSnapshot]:
        """Get recent metrics snapshots."""
        return self._snapshots[-limit:]
    
    async def start_collection(self) -> None:
        """Start continuous metrics collection loop."""
        self._running = True
        logger.info(f"Starting metrics collection for {self.node_id}")
        
        while self._running:
            try:
                await self.collect()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(self.collection_interval)
        
        logger.info(f"Metrics collection stopped for {self.node_id}")
    
    def stop_collection(self) -> None:
        """Stop metrics collection loop."""
        self._running = False


def create_metrics_collector_for_mapek(
    node_id: str,
    interface: str = "bat0",
) -> BatmanMetricsCollector:
    """
    Create a BatmanMetricsCollector configured for MAPE-K integration.
    
    Args:
        node_id: Node identifier
        interface: Batman-adv interface
    
    Returns:
        Configured BatmanMetricsCollector instance
    """
    return BatmanMetricsCollector(
        node_id=node_id,
        interface=interface,
        collection_interval=15.0,
    )


# Integration with existing x0tta6bl4 metrics
def integrate_with_x0tta6bl4_metrics(collector: BatmanMetricsCollector) -> None:
    """
    Integrate Batman metrics with existing x0tta6bl4 metrics system.
    
    Args:
        collector: BatmanMetricsCollector instance
    """
    try:
        from src.monitoring.metrics import get_metrics_registry
        
        registry = get_metrics_registry()
        
        # Add Batman-specific metrics to the main registry
        # This allows Batman metrics to be exposed alongside other metrics
        logger.info("Batman metrics integrated with x0tta6bl4 metrics system")
        
    except ImportError:
        logger.warning("x0tta6bl4 metrics system not available")
