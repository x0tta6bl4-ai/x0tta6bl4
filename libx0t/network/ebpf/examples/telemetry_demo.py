#!/usr/bin/env python3
"""
eBPF Telemetry Module - Demo Script

This script demonstrates the usage of the eBPF telemetry module with
various examples including performance monitoring, network monitoring,
and security monitoring.

Usage:
    sudo python3 telemetry_demo.py --demo basic
    sudo python3 telemetry_demo.py --demo performance
    sudo python3 telemetry_demo.py --demo network
    sudo python3 telemetry_demo.py --demo security
    sudo python3 telemetry_demo.py --demo all

Requirements:
    - Run with sudo or appropriate capabilities
    - BCC and bpftool installed
    - Linux kernel 5.8+
"""

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telemetry_module import (EBPFTelemetryCollector, EventSeverity,
                              MetricDefinition, MetricType, TelemetryConfig,
                              TelemetryEvent, create_collector, quick_start)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TelemetryDemo:
    """Demo class for eBPF telemetry module."""

    def __init__(self, demo_type: str):
        self.demo_type = demo_type
        self.collector = None
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.collector:
            self.collector.stop()
        sys.exit(0)

    def demo_basic(self):
        """Basic telemetry collection demo."""
        logger.info("=" * 60)
        logger.info("Basic Telemetry Collection Demo")
        logger.info("=" * 60)

        # Create collector with default config
        config = TelemetryConfig(
            prometheus_port=9090, collection_interval=1.0, log_level="INFO"
        )

        self.collector = EBPFTelemetryCollector(config)

        # Register custom metrics
        self.collector.prometheus.register_metric(
            MetricDefinition(
                name="demo_counter_total",
                type=MetricType.COUNTER,
                description="Demo counter metric",
            )
        )

        self.collector.prometheus.register_metric(
            MetricDefinition(
                name="demo_gauge_value",
                type=MetricType.GAUGE,
                description="Demo gauge metric",
            )
        )

        # Start collector
        self.collector.start()

        logger.info("✅ Collector started")
        logger.info("📊 Prometheus metrics available at http://localhost:9090/metrics")
        logger.info("Press Ctrl+C to stop")

        # Simulate metrics
        counter = 0
        self.running = True
        while self.running:
            # Increment counter
            counter += 1
            self.collector.prometheus.increment_metric("demo_counter_total")

            # Update gauge
            import random

            gauge_value = random.uniform(0, 100)
            self.collector.prometheus.set_metric("demo_gauge_value", gauge_value)

            # Log stats
            if counter % 10 == 0:
                stats = self.collector.get_stats()
                logger.info(
                    f"📈 Counter: {counter}, "
                    f"Gauge: {gauge_value:.2f}, "
                    f"Collections: {stats['collection']['total_collections']}"
                )

            time.sleep(1)

    def demo_performance(self):
        """Performance monitoring demo."""
        logger.info("=" * 60)
        logger.info("Performance Monitoring Demo")
        logger.info("=" * 60)

        try:
            from bcc import BPF
        except ImportError:
            logger.error(
                "❌ BCC not available. Install with: apt-get install bpfcc-tools"
            )
            return

        # Load performance monitor eBPF program
        bpf_program_path = Path(__file__).parent.parent / "performance_monitor.bpf.c"

        if not bpf_program_path.exists():
            logger.warning(f"⚠️ eBPF program not found at {bpf_program_path}")
            logger.info("Using stub mode for demo...")

            # Create collector without eBPF program
            config = TelemetryConfig(prometheus_port=9090, collection_interval=1.0)
            self.collector = EBPFTelemetryCollector(config)

            # Register performance metrics
            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="cpu_usage_percent",
                    type=MetricType.GAUGE,
                    description="CPU usage percentage",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="memory_usage_percent",
                    type=MetricType.GAUGE,
                    description="Memory usage percentage",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="context_switches_per_sec",
                    type=MetricType.GAUGE,
                    description="Context switches per second",
                )
            )

            self.collector.start()

            logger.info("✅ Collector started (stub mode)")
            logger.info(
                "📊 Prometheus metrics available at http://localhost:9090/metrics"
            )

            # Simulate performance metrics
            import random

            self.running = True
            while self.running:
                cpu = random.uniform(10, 80)
                memory = random.uniform(30, 70)
                ctx_switches = random.uniform(1000, 10000)

                self.collector.prometheus.set_metric("cpu_usage_percent", cpu)
                self.collector.prometheus.set_metric("memory_usage_percent", memory)
                self.collector.prometheus.set_metric(
                    "context_switches_per_sec", ctx_switches
                )

                logger.info(
                    f"📊 CPU: {cpu:.1f}%, "
                    f"Memory: {memory:.1f}%, "
                    f"CtxSwitch: {ctx_switches:.0f}/s"
                )

                time.sleep(1)
        else:
            # Load real eBPF program
            logger.info(f"Loading eBPF program from {bpf_program_path}")

            try:
                bpf = BPF(src_file=str(bpf_program_path))

                # Create collector
                config = TelemetryConfig(prometheus_port=9090, collection_interval=1.0)
                self.collector = EBPFTelemetryCollector(config)

                # Register program
                self.collector.register_program(
                    bpf, "performance_monitor", ["process_map", "system_metrics_map"]
                )

                # Start collector
                self.collector.start()

                logger.info("✅ Collector started with eBPF program")
                logger.info(
                    "📊 Prometheus metrics available at http://localhost:9090/metrics"
                )

                # Collect and display metrics
                self.running = True
                while self.running:
                    metrics = self.collector.collect_all_metrics()

                    perf_metrics = metrics.get("performance_monitor", {})
                    if perf_metrics:
                        logger.info(
                            f"📊 Collected {len(perf_metrics)} performance metrics"
                        )

                    time.sleep(5)

            except Exception as e:
                logger.error(f"❌ Error loading eBPF program: {e}")
                logger.info("Falling back to stub mode...")
                self.demo_performance_stub()

    def demo_performance_stub(self):
        """Stub mode for performance demo."""
        config = TelemetryConfig(prometheus_port=9090)
        self.collector = EBPFTelemetryCollector(config)
        self.collector.start()

        import random

        self.running = True
        while self.running:
            cpu = random.uniform(10, 80)
            self.collector.prometheus.set_metric("cpu_usage_percent", cpu)
            logger.info(f"📊 CPU: {cpu:.1f}%")
            time.sleep(1)

    def demo_network(self):
        """Network monitoring demo."""
        logger.info("=" * 60)
        logger.info("Network Monitoring Demo")
        logger.info("=" * 60)

        try:
            from bcc import BPF
        except ImportError:
            logger.error(
                "❌ BCC not available. Install with: apt-get install bpfcc-tools"
            )
            return

        # Load network monitor eBPF program
        bpf_program_path = Path(__file__).parent.parent / "network_monitor.bpf.c"

        if not bpf_program_path.exists():
            logger.warning(f"⚠️ eBPF program not found at {bpf_program_path}")
            logger.info("Using stub mode for demo...")

            # Create collector without eBPF program
            config = TelemetryConfig(prometheus_port=9090, collection_interval=1.0)
            self.collector = EBPFTelemetryCollector(config)

            # Register network metrics
            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="packets_ingress_total",
                    type=MetricType.COUNTER,
                    description="Total ingress packets",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="packets_egress_total",
                    type=MetricType.COUNTER,
                    description="Total egress packets",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="bytes_ingress_total",
                    type=MetricType.COUNTER,
                    description="Total ingress bytes",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="bytes_egress_total",
                    type=MetricType.COUNTER,
                    description="Total egress bytes",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="active_connections",
                    type=MetricType.GAUGE,
                    description="Active network connections",
                )
            )

            self.collector.start()

            logger.info("✅ Collector started (stub mode)")
            logger.info(
                "📊 Prometheus metrics available at http://localhost:9090/metrics"
            )

            # Simulate network metrics
            import random

            packets_in = 0
            packets_out = 0
            bytes_in = 0
            bytes_out = 0

            self.running = True
            while self.running:
                # Simulate network traffic
                new_packets_in = random.randint(10, 100)
                new_packets_out = random.randint(5, 50)
                new_bytes_in = new_packets_in * random.randint(64, 1500)
                new_bytes_out = new_packets_out * random.randint(64, 1500)

                packets_in += new_packets_in
                packets_out += new_packets_out
                bytes_in += new_bytes_in
                bytes_out += new_bytes_out

                self.collector.prometheus.set_metric(
                    "packets_ingress_total", packets_in
                )
                self.collector.prometheus.set_metric(
                    "packets_egress_total", packets_out
                )
                self.collector.prometheus.set_metric("bytes_ingress_total", bytes_in)
                self.collector.prometheus.set_metric("bytes_egress_total", bytes_out)
                self.collector.prometheus.set_metric(
                    "active_connections", random.randint(10, 100)
                )

                logger.info(
                    f"🌐 In: {new_packets_in} pkts/{new_bytes_in/1024:.1f}KB, "
                    f"Out: {new_packets_out} pkts/{new_bytes_out/1024:.1f}KB, "
                    f"Conn: {random.randint(10, 100)}"
                )

                time.sleep(1)
        else:
            # Load real eBPF program
            logger.info(f"Loading eBPF program from {bpf_program_path}")

            try:
                bpf = BPF(src_file=str(bpf_program_path))

                # Create collector
                config = TelemetryConfig(prometheus_port=9090, collection_interval=1.0)
                self.collector = EBPFTelemetryCollector(config)

                # Register program
                self.collector.register_program(
                    bpf, "network_monitor", ["connection_map", "system_network_map"]
                )

                # Start collector
                self.collector.start()

                logger.info("✅ Collector started with eBPF program")
                logger.info(
                    "📊 Prometheus metrics available at http://localhost:9090/metrics"
                )

                # Collect and display metrics
                self.running = True
                while self.running:
                    metrics = self.collector.collect_all_metrics()

                    net_metrics = metrics.get("network_monitor", {})
                    if net_metrics:
                        logger.info(f"🌐 Collected {len(net_metrics)} network metrics")

                    time.sleep(5)

            except Exception as e:
                logger.error(f"❌ Error loading eBPF program: {e}")
                logger.info("Falling back to stub mode...")
                self.demo_network_stub()

    def demo_network_stub(self):
        """Stub mode for network demo."""
        config = TelemetryConfig(prometheus_port=9090)
        self.collector = EBPFTelemetryCollector(config)
        self.collector.start()

        import random

        self.running = True
        while self.running:
            packets = random.randint(10, 100)
            self.collector.prometheus.set_metric("packets_ingress_total", packets)
            logger.info(f"🌐 Packets: {packets}")
            time.sleep(1)

    def demo_security(self):
        """Security monitoring demo."""
        logger.info("=" * 60)
        logger.info("Security Monitoring Demo")
        logger.info("=" * 60)

        try:
            from bcc import BPF
        except ImportError:
            logger.error(
                "❌ BCC not available. Install with: apt-get install bpfcc-tools"
            )
            return

        # Load security monitor eBPF program
        bpf_program_path = Path(__file__).parent.parent / "security_monitor.bpf.c"

        if not bpf_program_path.exists():
            logger.warning(f"⚠️ eBPF program not found at {bpf_program_path}")
            logger.info("Using stub mode for demo...")

            # Create collector without eBPF program
            config = TelemetryConfig(
                prometheus_port=9090, collection_interval=1.0, log_events=True
            )
            self.collector = EBPFTelemetryCollector(config)

            # Register security metrics
            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="connection_attempts_total",
                    type=MetricType.COUNTER,
                    description="Total connection attempts",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="failed_auth_attempts_total",
                    type=MetricType.COUNTER,
                    description="Total failed authentication attempts",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="suspicious_file_access_total",
                    type=MetricType.COUNTER,
                    description="Total suspicious file access attempts",
                )
            )

            self.collector.prometheus.register_metric(
                MetricDefinition(
                    name="privilege_escalation_attempts_total",
                    type=MetricType.COUNTER,
                    description="Total privilege escalation attempts",
                )
            )

            # Register event handler
            def handle_security_event(event: TelemetryEvent):
                if event.severity >= EventSeverity.HIGH:
                    logger.warning(
                        f"🚨 SECURITY EVENT: {event.event_type}, "
                        f"PID: {event.pid}, "
                        f"Severity: {event.severity.name}"
                    )

            self.collector.perf_reader.register_handler(
                "security_event", handle_security_event
            )

            self.collector.start()

            logger.info("✅ Collector started (stub mode)")
            logger.info(
                "📊 Prometheus metrics available at http://localhost:9090/metrics"
            )

            # Simulate security events
            import random

            connection_attempts = 0
            failed_auth = 0
            suspicious_access = 0
            priv_esc = 0

            self.running = True
            while self.running:
                # Simulate security events
                connection_attempts += random.randint(1, 10)
                if random.random() < 0.1:
                    failed_auth += random.randint(1, 5)
                if random.random() < 0.05:
                    suspicious_access += 1
                if random.random() < 0.01:
                    priv_esc += 1

                self.collector.prometheus.set_metric(
                    "connection_attempts_total", connection_attempts
                )
                self.collector.prometheus.set_metric(
                    "failed_auth_attempts_total", failed_auth
                )
                self.collector.prometheus.set_metric(
                    "suspicious_file_access_total", suspicious_access
                )
                self.collector.prometheus.set_metric(
                    "privilege_escalation_attempts_total", priv_esc
                )

                logger.info(
                    f"🔒 Conn: {connection_attempts}, "
                    f"AuthFail: {failed_auth}, "
                    f"Suspicious: {suspicious_access}, "
                    f"PrivEsc: {priv_esc}"
                )

                time.sleep(1)
        else:
            # Load real eBPF program
            logger.info(f"Loading eBPF program from {bpf_program_path}")

            try:
                bpf = BPF(src_file=str(bpf_program_path))

                # Create collector
                config = TelemetryConfig(
                    prometheus_port=9090, collection_interval=1.0, log_events=True
                )
                self.collector = EBPFTelemetryCollector(config)

                # Register program
                self.collector.register_program(
                    bpf, "security_monitor", ["connections", "system_security_map"]
                )

                # Register event handler
                def handle_security_event(event: TelemetryEvent):
                    if event.severity >= EventSeverity.HIGH:
                        logger.warning(
                            f"🚨 SECURITY EVENT: {event.event_type}, "
                            f"PID: {event.pid}, "
                            f"Severity: {event.severity.name}"
                        )

                self.collector.perf_reader.register_handler(
                    "security_event", handle_security_event
                )

                # Start perf buffer reading
                self.collector.start_perf_reading("security_events")

                # Start collector
                self.collector.start()

                logger.info("✅ Collector started with eBPF program")
                logger.info(
                    "📊 Prometheus metrics available at http://localhost:9090/metrics"
                )

                # Collect and display metrics
                self.running = True
                while self.running:
                    metrics = self.collector.collect_all_metrics()

                    sec_metrics = metrics.get("security_monitor", {})
                    if sec_metrics:
                        logger.info(f"🔒 Collected {len(sec_metrics)} security metrics")

                    time.sleep(5)

            except Exception as e:
                logger.error(f"❌ Error loading eBPF program: {e}")
                logger.info("Falling back to stub mode...")
                self.demo_security_stub()

    def demo_security_stub(self):
        """Stub mode for security demo."""
        config = TelemetryConfig(prometheus_port=9090)
        self.collector = EBPFTelemetryCollector(config)
        self.collector.start()

        import random

        self.running = True
        while self.running:
            attempts = random.randint(1, 10)
            self.collector.prometheus.set_metric("connection_attempts_total", attempts)
            logger.info(f"🔒 Connection attempts: {attempts}")
            time.sleep(1)

    def demo_all(self):
        """Combined demo with all monitors."""
        logger.info("=" * 60)
        logger.info("Combined Telemetry Demo (All Monitors)")
        logger.info("=" * 60)

        # Create collector
        config = TelemetryConfig(
            prometheus_port=9090, collection_interval=1.0, log_events=True
        )
        self.collector = EBPFTelemetryCollector(config)

        # Register metrics for all monitors
        # Performance metrics
        self.collector.prometheus.register_metric(
            MetricDefinition(
                name="cpu_usage_percent",
                type=MetricType.GAUGE,
                description="CPU usage percentage",
            )
        )

        # Network metrics
        self.collector.prometheus.register_metric(
            MetricDefinition(
                name="packets_total",
                type=MetricType.COUNTER,
                description="Total packets",
            )
        )

        # Security metrics
        self.collector.prometheus.register_metric(
            MetricDefinition(
                name="security_events_total",
                type=MetricType.COUNTER,
                description="Total security events",
            )
        )

        # Start collector
        self.collector.start()

        logger.info("✅ Collector started")
        logger.info("📊 Prometheus metrics available at http://localhost:9090/metrics")

        # Simulate all metrics
        import random

        packets = 0
        security_events = 0

        self.running = True
        while self.running:
            # Performance
            cpu = random.uniform(10, 80)
            self.collector.prometheus.set_metric("cpu_usage_percent", cpu)

            # Network
            new_packets = random.randint(10, 100)
            packets += new_packets
            self.collector.prometheus.set_metric("packets_total", packets)

            # Security
            if random.random() < 0.1:
                security_events += 1
                self.collector.prometheus.set_metric(
                    "security_events_total", security_events
                )

            logger.info(
                f"📊 CPU: {cpu:.1f}%, "
                f"Packets: {new_packets}, "
                f"Security: {security_events}"
            )

            time.sleep(1)

    def run(self):
        """Run the selected demo."""
        logger.info(f"Starting demo: {self.demo_type}")

        if self.demo_type == "basic":
            self.demo_basic()
        elif self.demo_type == "performance":
            self.demo_performance()
        elif self.demo_type == "network":
            self.demo_network()
        elif self.demo_type == "security":
            self.demo_security()
        elif self.demo_type == "all":
            self.demo_all()
        else:
            logger.error(f"Unknown demo type: {self.demo_type}")
            logger.info("Available demos: basic, performance, network, security, all")
            sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="eBPF Telemetry Module Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 telemetry_demo.py --demo basic
  sudo python3 telemetry_demo.py --demo performance
  sudo python3 telemetry_demo.py --demo network
  sudo python3 telemetry_demo.py --demo security
  sudo python3 telemetry_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        type=str,
        required=True,
        choices=["basic", "performance", "network", "security", "all"],
        help="Type of demo to run",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Prometheus HTTP server port (default: 9090)",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Collection interval in seconds (default: 1.0)",
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check permissions
    if os.geteuid() != 0:
        logger.warning("⚠️ Not running as root. Some features may not work.")
        logger.info("Consider running with sudo for full functionality.")

    # Run demo
    demo = TelemetryDemo(args.demo)
    demo.run()


if __name__ == "__main__":
    main()
