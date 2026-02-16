"""
eBPF Metrics Collector for x0tta6bl4
Collects metrics from eBPF programs and provides them to MAPE-K

Date: February 2, 2026
Version: 1.0
"""

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import BCC
BCC_AVAILABLE = False
try:
    from bcc import BPF

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False


@dataclass
class PerformanceMetrics:
    """Performance metrics from eBPF."""

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    context_switches_per_sec: float = 0.0
    syscalls_per_sec: float = 0.0
    io_operations_per_sec: float = 0.0
    load_average: List[float] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class NetworkMetrics:
    """Network metrics from eBPF."""

    packets_ingress_per_sec: float = 0.0
    packets_egress_per_sec: float = 0.0
    bytes_ingress_per_sec: float = 0.0
    bytes_egress_per_sec: float = 0.0
    packet_loss_percent: float = 0.0
    latency_ms: float = 0.0
    tcp_connections: int = 0
    udp_connections: int = 0
    network_errors_per_sec: float = 0.0
    timestamp: float = 0.0


@dataclass
class SecurityMetrics:
    """Security metrics from eBPF."""

    connection_attempts_per_sec: float = 0.0
    failed_auth_attempts_per_sec: float = 0.0
    suspicious_file_access: int = 0
    executable_executions_per_sec: float = 0.0
    privilege_escalation_attempts: int = 0
    unusual_syscall_patterns: int = 0
    security_events: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0


class EBPFMetricsCollector:
    """
    Collects metrics from eBPF programs.

    Responsibilities:
    - Read metrics from eBPF maps
    - Aggregate and normalize metrics
    - Convert to Python data structures
    - Push to MAPE-K cycle
    - Handle errors gracefully
    """

    def __init__(
        self,
        perf_monitor: Optional[Any] = None,
        net_monitor: Optional[Any] = None,
        sec_monitor: Optional[Any] = None,
    ):
        """
        Initialize eBPF metrics collector.

        Args:
            perf_monitor: Performance monitor eBPF program
            net_monitor: Network monitor eBPF program
            sec_monitor: Security monitor eBPF program
        """
        self.perf_monitor = perf_monitor
        self.net_monitor = net_monitor
        self.sec_monitor = sec_monitor

        # Metrics cache
        self._perf_cache: Dict[str, Any] = {}
        self._net_cache: Dict[str, Any] = {}
        self._sec_cache: Dict[str, Any] = {}

        # Timestamp tracking
        self._last_collection_time: float = 0.0
        self._collection_interval: float = 1.0  # seconds

        logger.info("✅ eBPF Metrics Collector initialized")

    def collect_performance_metrics(self) -> PerformanceMetrics:
        """
        Collect performance metrics from eBPF.

        Returns:
            PerformanceMetrics object
        """
        if not BCC_AVAILABLE or not self.perf_monitor:
            logger.warning(
                "⚠️ Performance monitor not available - returning stub metrics"
            )
            return PerformanceMetrics(timestamp=time.time())

        try:
            # Read process metrics map
            process_map = self.perf_monitor["process_map"]

            # Aggregate metrics
            total_cpu_time = 0
            total_context_switches = 0
            total_syscalls = 0
            total_memory_allocs = 0
            total_io_ops = 0
            process_count = 0

            for pid, metrics in process_map.items():
                total_cpu_time += metrics.cpu_time_ns
                total_context_switches += metrics.context_switches
                total_syscalls += metrics.syscalls
                total_memory_allocs += metrics.memory_allocations
                total_io_ops += metrics.io_operations
                process_count += 1

            # Read system metrics map
            sys_metrics_map = self.perf_monitor["system_metrics_map"]
            sys_metrics = sys_metrics_map[0]

            # Calculate rates (per second)
            current_time = time.time()
            time_delta = (
                current_time - self._last_collection_time
                if self._last_collection_time > 0
                else 1.0
            )

            context_switches_per_sec = (
                total_context_switches / time_delta if time_delta > 0 else 0
            )
            syscalls_per_sec = total_syscalls / time_delta if time_delta > 0 else 0
            io_operations_per_sec = total_io_ops / time_delta if time_delta > 0 else 0

            # Calculate CPU percentage (simplified)
            cpu_percent = (
                min(100.0, (total_cpu_time / 1e9) / time_delta * 100)
                if time_delta > 0
                else 0
            )

            # Calculate memory percentage (simplified)
            memory_percent = min(
                100.0, (total_memory_allocs / 1e6) * 10
            )  # Approximation

            # Load average (simplified)
            load_average = [
                context_switches_per_sec / 1000.0,
                syscalls_per_sec / 10000.0,
                io_operations_per_sec / 100.0,
            ]

            # Create metrics object
            metrics = PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                context_switches_per_sec=context_switches_per_sec,
                syscalls_per_sec=syscalls_per_sec,
                io_operations_per_sec=io_operations_per_sec,
                load_average=load_average,
                timestamp=current_time,
            )

            # Update cache
            self._perf_cache = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "context_switches_per_sec": context_switches_per_sec,
                "syscalls_per_sec": syscalls_per_sec,
                "io_operations_per_sec": io_operations_per_sec,
                "load_average": load_average,
                "process_count": process_count,
            }

            logger.debug(
                f"📊 Collected performance metrics: CPU={cpu_percent:.1f}%, Memory={memory_percent:.1f}%"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Failed to collect performance metrics: {e}")
            return PerformanceMetrics(timestamp=time.time())

    def collect_network_metrics(self) -> NetworkMetrics:
        """
        Collect network metrics from eBPF.

        Returns:
            NetworkMetrics object
        """
        if not BCC_AVAILABLE or not self.net_monitor:
            logger.warning("⚠️ Network monitor not available - returning stub metrics")
            return NetworkMetrics(timestamp=time.time())

        try:
            # Read system network metrics map
            sys_net_map = self.net_monitor["system_network_map"]
            sys_metrics = sys_net_map[0]

            # Read packet loss map
            packet_loss_map = self.net_monitor["packet_loss_map"]
            total_packet_loss = packet_loss_map[0]

            # Calculate rates (per second)
            current_time = time.time()
            time_delta = (
                current_time - self._last_collection_time
                if self._last_collection_time > 0
                else 1.0
            )

            packets_ingress_per_sec = (
                sys_metrics.total_packets_ingress / time_delta if time_delta > 0 else 0
            )
            packets_egress_per_sec = (
                sys_metrics.total_packets_egress / time_delta if time_delta > 0 else 0
            )
            bytes_ingress_per_sec = (
                sys_metrics.total_bytes_ingress / time_delta if time_delta > 0 else 0
            )
            bytes_egress_per_sec = (
                sys_metrics.total_bytes_egress / time_delta if time_delta > 0 else 0
            )
            network_errors_per_sec = (
                sys_metrics.total_connection_errors / time_delta
                if time_delta > 0
                else 0
            )

            # Calculate packet loss percentage
            total_packets = (
                sys_metrics.total_packets_ingress + sys_metrics.total_packets_egress
            )
            packet_loss_percent = (
                (total_packet_loss / total_packets * 100) if total_packets > 0 else 0
            )

            # Calculate latency (simplified - would need RTT tracking)
            latency_ms = 25.0  # Placeholder - would be calculated from RTT

            # Create metrics object
            metrics = NetworkMetrics(
                packets_ingress_per_sec=packets_ingress_per_sec,
                packets_egress_per_sec=packets_egress_per_sec,
                bytes_ingress_per_sec=bytes_ingress_per_sec,
                bytes_egress_per_sec=bytes_egress_per_sec,
                packet_loss_percent=packet_loss_percent,
                latency_ms=latency_ms,
                tcp_connections=sys_metrics.active_connections,
                udp_connections=0,  # Would need separate tracking
                network_errors_per_sec=network_errors_per_sec,
                timestamp=current_time,
            )

            # Update cache
            self._net_cache = {
                "packets_ingress_per_sec": packets_ingress_per_sec,
                "packets_egress_per_sec": packets_egress_per_sec,
                "bytes_ingress_per_sec": bytes_ingress_per_sec,
                "bytes_egress_per_sec": bytes_egress_per_sec,
                "packet_loss_percent": packet_loss_percent,
                "latency_ms": latency_ms,
                "tcp_connections": sys_metrics.active_connections,
                "network_errors_per_sec": network_errors_per_sec,
            }

            logger.debug(
                f"📊 Collected network metrics: Loss={packet_loss_percent:.1f}%, Latency={latency_ms:.1f}ms"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Failed to collect network metrics: {e}")
            return NetworkMetrics(timestamp=time.time())

    def collect_security_metrics(self) -> SecurityMetrics:
        """
        Collect security metrics from eBPF.

        Returns:
            SecurityMetrics object
        """
        if not BCC_AVAILABLE or not self.sec_monitor:
            logger.warning("⚠️ Security monitor not available - returning stub metrics")
            return SecurityMetrics(timestamp=time.time())

        try:
            # Read system security metrics map
            sys_sec_map = self.sec_monitor["system_security_map"]
            sys_metrics = sys_sec_map[0]

            # Calculate rates (per second)
            current_time = time.time()
            time_delta = (
                current_time - self._last_collection_time
                if self._last_collection_time > 0
                else 1.0
            )

            connection_attempts_per_sec = (
                sys_metrics.total_connection_attempts / time_delta
                if time_delta > 0
                else 0
            )
            failed_auth_attempts_per_sec = (
                sys_metrics.failed_auth_attempts / time_delta if time_delta > 0 else 0
            )
            executable_executions_per_sec = (
                sys_metrics.executable_executions / time_delta if time_delta > 0 else 0
            )

            # Create metrics object
            metrics = SecurityMetrics(
                connection_attempts_per_sec=connection_attempts_per_sec,
                failed_auth_attempts_per_sec=failed_auth_attempts_per_sec,
                suspicious_file_access=sys_metrics.suspicious_file_access,
                executable_executions_per_sec=executable_executions_per_sec,
                privilege_escalation_attempts=sys_metrics.privilege_escalation_attempts,
                unusual_syscall_patterns=sys_metrics.unusual_syscall_patterns,
                security_events=[],  # Would be collected from perf events
                timestamp=current_time,
            )

            # Update cache
            self._sec_cache = {
                "connection_attempts_per_sec": connection_attempts_per_sec,
                "failed_auth_attempts_per_sec": failed_auth_attempts_per_sec,
                "suspicious_file_access": sys_metrics.suspicious_file_access,
                "executable_executions_per_sec": executable_executions_per_sec,
                "privilege_escalation_attempts": sys_metrics.privilege_escalation_attempts,
                "unusual_syscall_patterns": sys_metrics.unusual_syscall_patterns,
                "active_connections": sys_metrics.active_connections,
            }

            logger.debug(
                f"📊 Collected security metrics: AuthFails={failed_auth_attempts_per_sec:.1f}/s"
            )
            return metrics

        except Exception as e:
            logger.error(f"❌ Failed to collect security metrics: {e}")
            return SecurityMetrics(timestamp=time.time())

    def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Collect all metrics from eBPF programs.

        Returns:
            Dictionary with all metrics
        """
        current_time = time.time()

        # Collect metrics from all monitors
        perf_metrics = self.collect_performance_metrics()
        net_metrics = self.collect_network_metrics()
        sec_metrics = self.collect_security_metrics()

        # Update last collection time
        self._last_collection_time = current_time

        # Combine all metrics
        all_metrics = {
            "performance": {
                "cpu_percent": perf_metrics.cpu_percent,
                "memory_percent": perf_metrics.memory_percent,
                "context_switches_per_sec": perf_metrics.context_switches_per_sec,
                "syscalls_per_sec": perf_metrics.syscalls_per_sec,
                "io_operations_per_sec": perf_metrics.io_operations_per_sec,
                "load_average": perf_metrics.load_average,
                "timestamp": perf_metrics.timestamp,
            },
            "network": {
                "packets_ingress_per_sec": net_metrics.packets_ingress_per_sec,
                "packets_egress_per_sec": net_metrics.packets_egress_per_sec,
                "bytes_ingress_per_sec": net_metrics.bytes_ingress_per_sec,
                "bytes_egress_per_sec": net_metrics.bytes_egress_per_sec,
                "packet_loss_percent": net_metrics.packet_loss_percent,
                "latency_ms": net_metrics.latency_ms,
                "tcp_connections": net_metrics.tcp_connections,
                "udp_connections": net_metrics.udp_connections,
                "network_errors_per_sec": net_metrics.network_errors_per_sec,
                "timestamp": net_metrics.timestamp,
            },
            "security": {
                "connection_attempts_per_sec": sec_metrics.connection_attempts_per_sec,
                "failed_auth_attempts_per_sec": sec_metrics.failed_auth_attempts_per_sec,
                "suspicious_file_access": sec_metrics.suspicious_file_access,
                "executable_executions_per_sec": sec_metrics.executable_executions_per_sec,
                "privilege_escalation_attempts": sec_metrics.privilege_escalation_attempts,
                "unusual_syscall_patterns": sec_metrics.unusual_syscall_patterns,
                "security_events": sec_metrics.security_events,
                "timestamp": sec_metrics.timestamp,
            },
            "timestamp": current_time,
        }

        logger.info(
            f"📊 Collected all metrics: CPU={perf_metrics.cpu_percent:.1f}%, "
            f"Loss={net_metrics.packet_loss_percent:.1f}%, "
            f"AuthFails={sec_metrics.failed_auth_attempts_per_sec:.1f}/s"
        )

        return all_metrics

    def push_to_mapek(self, metrics: Dict[str, Any]) -> bool:
        """
        Push metrics to MAPE-K cycle.

        Args:
            metrics: Dictionary with all metrics

        Returns:
            True if successful, False otherwise
        """
        try:
            # This would be implemented by the MAPE-K integration
            # For now, just log the metrics
            logger.info(f"📤 Pushing metrics to MAPE-K: {len(metrics)} categories")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to push metrics to MAPE-K: {e}")
            return False

    def get_cached_metrics(self) -> Dict[str, Any]:
        """
        Get cached metrics from last collection.

        Returns:
            Dictionary with cached metrics
        """
        return {
            "performance": self._perf_cache.copy(),
            "network": self._net_cache.copy(),
            "security": self._sec_cache.copy(),
            "last_collection_time": self._last_collection_time,
        }

    def clear_cache(self):
        """Clear metrics cache."""
        self._perf_cache.clear()
        self._net_cache.clear()
        self._sec_cache.clear()
        logger.debug("🗑️ Cleared metrics cache")

    def set_collection_interval(self, interval: float):
        """
        Set metrics collection interval.

        Args:
            interval: Collection interval in seconds
        """
        self._collection_interval = interval
        logger.info(f"⏱️ Set collection interval to {interval}s")

    def get_collection_interval(self) -> float:
        """Get current collection interval."""
        return self._collection_interval
