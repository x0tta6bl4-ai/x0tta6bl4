#!/usr/bin/env python3
"""
eBPF Configuration Examples for x0tta6bl4

This module provides example configurations for various eBPF use cases
in the x0tta6bl4 mesh network. These examples demonstrate:

- Basic packet filtering and monitoring
- Traffic shaping and QoS
- Flow observability
- Security policies
- Performance monitoring

Each example includes:
- Orchestrator configuration
- Program-specific settings
- CLI usage examples
- Monitoring setup
"""

from pathlib import Path
from typing import Any, Dict, List

from ..loader import EBPFAttachMode, EBPFProgramType
from ..orchestrator import EBPFOrchestrator, OrchestratorConfig


# Example 1: Basic Network Monitoring
def get_basic_monitoring_config() -> OrchestratorConfig:
    """
    Basic network monitoring configuration.

    Monitors all traffic on eth0 with flow observability enabled.
    Suitable for initial deployment and traffic analysis.
    """
    return OrchestratorConfig(
        interface="eth0",
        programs_dir=Path("/opt/x0tta6bl4/ebpf/programs"),
        enable_flow_observability=True,
        enable_metrics_export=True,
        enable_dynamic_fallback=True,
        enable_mapek_integration=False,  # Disable for basic monitoring
        prometheus_port=9090,
        latency_threshold_ms=50.0,  # Lower threshold for monitoring
        monitoring_interval_seconds=5.0,
        auto_load_programs=True,
    )


# Example 2: High-Performance Firewall
def get_firewall_config() -> OrchestratorConfig:
    """
    High-performance XDP firewall configuration.

    Uses driver-mode XDP for maximum performance with zero-trust policies.
    """
    return OrchestratorConfig(
        interface="eth0",
        programs_dir=Path("/opt/x0tta6bl4/ebpf/programs"),
        enable_flow_observability=True,
        enable_metrics_export=True,
        enable_dynamic_fallback=True,
        enable_mapek_integration=True,  # Enable self-healing
        prometheus_port=9090,
        latency_threshold_ms=10.0,  # Very low latency requirement
        monitoring_interval_seconds=1.0,  # Frequent monitoring
        auto_load_programs=True,
    )


# Example 3: Traffic Shaping for QoS
def get_qos_config() -> OrchestratorConfig:
    """
    Quality of Service configuration with traffic shaping.

    Uses TC programs for bandwidth management and priority queuing.
    """
    return OrchestratorConfig(
        interface="eth0",
        programs_dir=Path("/opt/x0tta6bl4/ebpf/programs"),
        enable_flow_observability=True,
        enable_metrics_export=True,
        enable_dynamic_fallback=True,
        enable_mapek_integration=True,
        prometheus_port=9090,
        latency_threshold_ms=100.0,  # Higher tolerance for QoS
        monitoring_interval_seconds=10.0,
        auto_load_programs=True,
    )


# Example 4: Container Networking
def get_container_networking_config() -> OrchestratorConfig:
    """
    Container networking configuration.

    Optimized for Kubernetes/Docker environments with cgroup integration.
    """
    return OrchestratorConfig(
        interface="eth0",
        programs_dir=Path("/opt/x0tta6bl4/ebpf/programs"),
        enable_flow_observability=True,
        enable_metrics_export=True,
        enable_dynamic_fallback=True,
        enable_mapek_integration=True,
        prometheus_port=9090,
        latency_threshold_ms=25.0,  # Container networking latency
        monitoring_interval_seconds=5.0,
        auto_load_programs=False,  # Manual control for containers
    )


# Program-specific configurations
class EBPFProgramConfigs:
    """Collection of program-specific configuration examples"""

    @staticmethod
    def xdp_firewall() -> Dict[str, Any]:
        """XDP firewall program configuration"""
        return {
            "program_name": "xdp_firewall.o",
            "type": EBPFProgramType.XDP,
            "attach_mode": EBPFAttachMode.DRV,
            "rules": [
                {
                    "id": 1,
                    "action": "drop",
                    "protocol": "tcp",
                    "source_ip": "192.168.1.100",
                    "description": "Block suspicious IP",
                },
                {
                    "id": 2,
                    "action": "allow",
                    "protocol": "tcp",
                    "port": 443,
                    "description": "Allow HTTPS traffic",
                },
                {
                    "id": 3,
                    "action": "allow",
                    "protocol": "tcp",
                    "port": 80,
                    "description": "Allow HTTP traffic",
                },
            ],
            "default_action": "drop",  # Zero-trust: drop by default
            "max_rules": 1000,
            "update_interval_seconds": 30,
        }

    @staticmethod
    def tc_shaper() -> Dict[str, Any]:
        """Traffic Control shaper program configuration"""
        return {
            "program_name": "tc_shaper.o",
            "type": EBPFProgramType.TC,
            "classes": [
                {
                    "id": 1,
                    "bandwidth_mbps": 100,
                    "priority": 1,
                    "description": "High priority traffic",
                },
                {
                    "id": 2,
                    "bandwidth_mbps": 50,
                    "priority": 2,
                    "description": "Medium priority traffic",
                },
                {
                    "id": 3,
                    "bandwidth_mbps": 10,
                    "priority": 3,
                    "description": "Low priority traffic",
                },
            ],
            "default_class": 3,
            "buffer_size_kb": 1024,
            "ecn_enabled": True,
        }

    @staticmethod
    def flow_monitor() -> Dict[str, Any]:
        """Flow monitoring program configuration"""
        return {
            "program_name": "flow_monitor.o",
            "type": EBPFProgramType.XDP,
            "attach_mode": EBPFAttachMode.SKB,  # Compatible mode
            "flow_timeout_seconds": 300,
            "max_flows": 100000,
            "sampling_rate": 1.0,  # 100% sampling
            "export_interval_seconds": 10,
            "metrics": ["packets_total", "bytes_total", "flow_duration", "tcp_flags"],
        }

    @staticmethod
    def ddos_protection() -> Dict[str, Any]:
        """DDoS protection program configuration"""
        return {
            "program_name": "ddos_protect.o",
            "type": EBPFProgramType.XDP,
            "attach_mode": EBPFAttachMode.DRV,
            "syn_flood_threshold": 1000,  # packets/second
            "udp_flood_threshold": 5000,
            "icmp_flood_threshold": 100,
            "block_duration_seconds": 300,
            "whitelist": ["10.0.0.0/8", "192.168.0.0/16"],  # Internal networks
            "auto_mitigation": True,
        }


# CLI usage examples
class CLIExamples:
    """Examples of CLI commands for different scenarios"""

    @staticmethod
    def basic_monitoring() -> List[str]:
        """CLI commands for basic network monitoring setup"""
        return [
            "# Start monitoring on eth0",
            "x0tta6bl4-ebpf load flow_monitor.o",
            "x0tta6bl4-ebpf attach flow_monitor_001 eth0",
            "",
            "# View current status",
            "x0tta6bl4-ebpf status",
            "",
            "# Monitor flows in real-time",
            "x0tta6bl4-ebpf flows --follow",
            "",
            "# Get statistics",
            "x0tta6bl4-ebpf stats",
            "",
            "# Export metrics",
            "x0tta6bl4-ebpf metrics --export monitoring_metrics.json",
        ]

    @staticmethod
    def firewall_deployment() -> List[str]:
        """CLI commands for firewall deployment"""
        return [
            "# Load XDP firewall",
            "x0tta6bl4-ebpf load xdp_firewall.o --mode drv",
            "",
            "# Attach to interface",
            "x0tta6bl4-ebpf attach xdp_firewall_001 eth0",
            "",
            "# Update firewall rules",
            "x0tta6bl4-ebpf update-rules xdp_firewall_001 firewall_rules.json",
            "",
            "# Monitor blocked packets",
            "x0tta6bl4-ebpf watch --filter 'action=drop'",
            "",
            "# Health check",
            "x0tta6bl4-ebpf health",
        ]

    @staticmethod
    def performance_optimization() -> List[str]:
        """CLI commands for performance monitoring and optimization"""
        return [
            "# Enable performance monitoring",
            "x0tta6bl4-ebpf perf --enable --interval 1",
            "",
            "# Monitor latency",
            "x0tta6bl4-ebpf latency --histogram",
            "",
            "# Check drop rates",
            "x0tta6bl4-ebpf drops --threshold 0.01",
            "",
            "# Memory usage",
            "x0tta6bl4-ebpf memory --maps",
            "",
            "# Generate performance report",
            "x0tta6bl4-ebpf report --output perf_report.html",
        ]


# Monitoring and alerting configurations
class MonitoringConfigs:
    """Monitoring and alerting configuration examples"""

    @staticmethod
    def prometheus_config() -> Dict[str, Any]:
        """Prometheus configuration for eBPF metrics"""
        return {
            "global": {"scrape_interval": "15s", "evaluation_interval": "15s"},
            "scrape_configs": [
                {
                    "job_name": "ebpf-metrics",
                    "static_configs": [{"targets": ["localhost:9090"]}],
                }
            ],
            "rule_files": ["ebpf_alerts.yml"],
        }

    @staticmethod
    def alert_rules() -> Dict[str, Any]:
        """Prometheus alert rules for eBPF monitoring"""
        return {
            "groups": [
                {
                    "name": "ebpf_alerts",
                    "rules": [
                        {
                            "alert": "EBPFHighLatency",
                            "expr": "ebpf_latency_microseconds > 100000",
                            "for": "5m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "High eBPF processing latency",
                                "description": "eBPF packet processing latency is {{ $value }}µs",
                            },
                        },
                        {
                            "alert": "EBPFPacketDrops",
                            "expr": "rate(ebpf_packets_dropped_total[5m]) > 0.05",
                            "for": "2m",
                            "labels": {"severity": "critical"},
                            "annotations": {
                                "summary": "High packet drop rate",
                                "description": "Packet drop rate is {{ $value | humanizePercentage }}",
                            },
                        },
                        {
                            "alert": "EBPFMemoryUsage",
                            "expr": "ebpf_memory_usage_bytes / ebpf_memory_limit_bytes > 0.8",
                            "for": "10m",
                            "labels": {"severity": "warning"},
                            "annotations": {
                                "summary": "High eBPF memory usage",
                                "description": "eBPF memory usage is {{ $value | humanizePercentage }}",
                            },
                        },
                    ],
                }
            ]
        }

    @staticmethod
    def grafana_dashboard() -> Dict[str, Any]:
        """Grafana dashboard configuration for eBPF metrics"""
        return {
            "dashboard": {
                "title": "x0tta6bl4 eBPF Monitoring",
                "tags": ["ebpf", "networking", "x0tta6bl4"],
                "timezone": "browser",
                "panels": [
                    {
                        "title": "Packet Processing Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "rate(ebpf_packets_processed_total[5m])",
                                "legendFormat": "Packets/sec",
                            }
                        ],
                    },
                    {
                        "title": "Processing Latency",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "ebpf_latency_microseconds",
                                "legendFormat": "Latency (µs)",
                            }
                        ],
                    },
                    {
                        "title": "Active Flows",
                        "type": "singlestat",
                        "targets": [
                            {
                                "expr": "ebpf_flows_active",
                                "legendFormat": "Active Flows",
                            }
                        ],
                    },
                ],
            }
        }


# Usage examples
def demonstrate_config_usage():
    """Demonstrate how to use the configuration examples"""

    # Get basic monitoring config
    config = get_basic_monitoring_config()
    print(f"Basic monitoring config: interface={config.interface}")

    # Get firewall program config
    firewall_config = EBPFProgramConfigs.xdp_firewall()
    print(f"Firewall rules: {len(firewall_config['rules'])}")

    # Show CLI examples
    monitoring_commands = CLIExamples.basic_monitoring()
    print("CLI monitoring commands:")
    for cmd in monitoring_commands[:3]:  # Show first 3
        print(f"  {cmd}")

    # Show monitoring config
    prom_config = MonitoringConfigs.prometheus_config()
    print(f"Prometheus scrape interval: {prom_config['global']['scrape_interval']}")


if __name__ == "__main__":
    demonstrate_config_usage()
