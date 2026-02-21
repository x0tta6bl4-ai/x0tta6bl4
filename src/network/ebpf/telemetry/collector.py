"""
Main telemetry collector for eBPF programs.

This is the primary interface for collecting telemetry from eBPF programs.
It coordinates map reading, perf buffer processing, and metrics export.
"""

import importlib.util
import logging
import sys
import threading
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from .map_reader import MapReader
from .models import CollectionStats, MapType, TelemetryConfig
from .perf_reader import PerfBufferReader
from .prometheus_exporter import PrometheusExporter
from .security import SecurityManager

logger = logging.getLogger(__name__)


def _module_available(module_name: str) -> bool:
    """Return True when module is available, including test-injected stubs."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return module_name in sys.modules


# Check for BCC availability
BCC_AVAILABLE = _module_available("bcc")


class EBPFTelemetryCollector:
    """
    Main telemetry collector for eBPF programs.

    This is the primary interface for collecting telemetry from eBPF programs.
    It coordinates map reading, perf buffer processing, and metrics export.

    Usage:
        collector = EBPFTelemetryCollector(config)
        collector.register_program(perf_monitor, "performance_monitor")
        collector.start()

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Export to Prometheus
        collector.export_to_prometheus(metrics)
    """

    def __init__(self, config: Optional[TelemetryConfig] = None):
        """
        Initialize telemetry collector.

        Args:
            config: Optional configuration
        """
        self.config = config or TelemetryConfig()
        self.security = SecurityManager(self.config)
        self.map_reader = MapReader(self.config, self.security)
        self.perf_reader = PerfBufferReader(self.config, self.security)
        self.prometheus = PrometheusExporter(self.config, self.security)

        # Registered programs
        self.programs: Dict[str, Any] = {}
        self.program_maps: Dict[str, List[str]] = {}

        # Statistics
        self.stats = CollectionStats()

        # Threading
        self.collection_thread: Optional[threading.Thread] = None
        self.perf_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        logger.info("EBPFTelemetryCollector initialized")

    def register_program(
        self, bpf_program: Any, program_name: str, map_names: Optional[List[str]] = None
    ):
        """
        Register an eBPF program for telemetry collection.

        Args:
            bpf_program: BCC BPF program instance
            program_name: Name of the program
            map_names: List of map names to monitor
        """
        self.programs[program_name] = bpf_program
        self.program_maps[program_name] = map_names or []

        logger.info(f"Registered eBPF program: {program_name}")

    def register_map(
        self, program_name: str, map_name: str, map_type: MapType = MapType.HASH
    ):
        """
        Register a specific map for monitoring.

        Args:
            program_name: Name of the program
            map_name: Name of the map
            map_type: Type of the map
        """
        if program_name not in self.program_maps:
            self.program_maps[program_name] = []

        if map_name not in self.program_maps[program_name]:
            self.program_maps[program_name].append(map_name)
            logger.debug(f"Registered map: {program_name}/{map_name}")

    def collect_from_map(self, program_name: str, map_name: str) -> Dict[str, Any]:
        """
        Collect metrics from a specific map.

        Args:
            program_name: Name of the program
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        bpf_program = self.programs.get(program_name)
        if not bpf_program:
            logger.warning(f"Program {program_name} not found")
            return {}

        try:
            data = self.map_reader.read_map(bpf_program, map_name)
            self.stats.total_metrics_collected += len(data)
            return data
        except Exception as e:
            logger.error(f"Error collecting from map {map_name}: {e}")
            return {}

    def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all registered programs and maps.

        Returns:
            Dictionary with all collected metrics
        """
        start_time = time.time()
        all_metrics = {}

        self.stats.total_collections += 1

        try:
            # Collect from all programs
            for program_name, bpf_program in self.programs.items():
                program_metrics = {}

                # Get maps for this program
                map_names = self.program_maps.get(program_name, [])

                if not map_names and BCC_AVAILABLE:
                    # Auto-discover maps
                    try:
                        for key in dir(bpf_program):
                            if key.startswith("[") and key.endswith("]"):
                                map_name = key[2:-2]
                                map_names.append(map_name)
                    except Exception as e:
                        logger.debug(
                            f"Could not auto-discover maps for {program_name}: {e}"
                        )

                # Read all maps
                if map_names:
                    map_data = self.map_reader.read_multiple_maps(
                        bpf_program, map_names
                    )
                    for map_name, data in map_data.items():
                        # Flatten map data into metrics
                        for key, value in data.items():
                            metric_name = f"{program_name}_{map_name}_{key}"
                            program_metrics[metric_name] = value

                all_metrics[program_name] = program_metrics

            self.stats.successful_collections += 1
            self.stats.last_collection_time = time.time()

            # Update average collection time
            collection_time = time.time() - start_time
            self.stats.collection_times.append(collection_time)
            self.stats.average_collection_time = sum(self.stats.collection_times) / len(
                self.stats.collection_times
            )

            logger.debug(
                f"Collected {len(all_metrics)} program metrics in {collection_time*1000:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self.stats.failed_collections += 1

        return all_metrics

    def export_to_prometheus(self, metrics: Dict[str, Any]):
        """
        Export metrics to Prometheus.

        Args:
            metrics: Dictionary of metrics to export
        """
        # Flatten metrics
        flat_metrics = {}
        for program_name, program_metrics in metrics.items():
            for metric_name, value in program_metrics.items():
                flat_metrics[f"{program_name}_{metric_name}"] = value

        # Export
        self.prometheus.export_metrics(flat_metrics)

        logger.debug(f"Exported {len(flat_metrics)} metrics to Prometheus")

    def start_perf_reading(self, map_name: str = "events"):
        """
        Start reading perf buffer events.

        Args:
            map_name: Name of the perf buffer map
        """
        if not self.programs:
            logger.warning("No programs registered for perf reading")
            return

        # Use first registered program
        bpf_program = next(iter(self.programs.values()))

        self.perf_thread = threading.Thread(
            target=self.perf_reader.start_reading,
            args=(bpf_program, map_name),
            daemon=True,
        )
        self.perf_thread.start()

        logger.info("Started perf buffer reading thread")

    def start_collection_loop(self, interval: Optional[float] = None):
        """
        Start automatic metric collection loop.

        Args:
            interval: Collection interval in seconds
        """
        interval = interval or self.config.collection_interval

        def collection_loop():
            while not self.stop_event.is_set():
                try:
                    metrics = self.collect_all_metrics()
                    self.export_to_prometheus(metrics)
                except Exception as e:
                    logger.error(f"Error in collection loop: {e}")

                self.stop_event.wait(interval)

        self.collection_thread = threading.Thread(target=collection_loop, daemon=True)
        self.collection_thread.start()

        logger.info(f"Started collection loop (interval={interval}s)")

    def start(self):
        """Start the telemetry collector."""
        # Start Prometheus server
        self.prometheus.start_server()

        # Start collection loop
        self.start_collection_loop()

        logger.info("Telemetry collector started")

    def stop(self):
        """Stop the telemetry collector."""
        self.stop_event.set()

        # Stop perf reader
        self.perf_reader.stop_reading()

        # Wait for threads
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        if self.perf_thread:
            self.perf_thread.join(timeout=5)

        logger.info("Telemetry collector stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            "collection": asdict(self.stats),
            "security": self.security.get_stats(),
            "perf_reader": self.perf_reader.get_stats(),
            "programs": list(self.programs.keys()),
            "maps": self.program_maps,
        }

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


__all__ = ["EBPFTelemetryCollector"]
