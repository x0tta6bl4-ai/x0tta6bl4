#!/usr/bin/env python3
"""
eBPF Performance Monitoring Example

This example demonstrates how to use the EBPFPerformanceMonitor
to monitor eBPF program performance, set up alerting, and export
metrics to Grafana dashboards.

Features demonstrated:
- Real-time performance monitoring
- Automated alerting for performance issues
- Grafana dashboard generation
- Prometheus alert rule export
- Performance report generation
"""

import asyncio
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from src.network.ebpf.performance_monitor import (
        EBPFPerformanceMonitor,
        start_performance_monitoring,
        generate_performance_report
    )
    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError as e:
    logger.error(f"Performance monitor not available: {e}")
    PERFORMANCE_MONITOR_AVAILABLE = False


async def basic_performance_monitoring():
    """
    Basic performance monitoring example.

    Monitors eBPF performance for 60 seconds and generates a report.
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        logger.error("Performance monitor not available")
        return

    logger.info("🚀 Starting basic performance monitoring...")

    # Start monitoring
    monitor = await start_performance_monitoring(port=9090)

    # Monitor for 60 seconds
    logger.info("📊 Monitoring performance for 60 seconds...")
    await asyncio.sleep(60)

    # Generate and display report
    report = generate_performance_report(monitor)
    print("\n" + "="*60)
    print("PERFORMANCE REPORT")
    print("="*60)
    print(report)
    print("="*60)

    # Stop monitoring
    await monitor.stop_monitoring()
    logger.info("✅ Basic monitoring completed")


async def advanced_monitoring_with_alerting():
    """
    Advanced monitoring with custom alerting and dashboard export.
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        logger.error("Performance monitor not available")
        return

    logger.info("🚀 Starting advanced performance monitoring...")

    # Create monitor with custom settings
    monitor = EBPFPerformanceMonitor(prometheus_port=9091)

    # Start monitoring
    await monitor.start_monitoring()

    # Monitor for 30 seconds to collect some data
    logger.info("📊 Collecting performance data for 30 seconds...")
    await asyncio.sleep(30)

    # Export Grafana dashboard
    dashboard_path = Path("dashboards/ebpf_performance_dashboard.json")
    dashboard = monitor.export_grafana_dashboard()

    with open(dashboard_path, 'w') as f:
        json.dump(dashboard, f, indent=2)

    logger.info(f"📈 Grafana dashboard exported to {dashboard_path}")

    # Export Prometheus alert rules
    alerts_path = Path("monitoring/ebpf_performance_alerts.yml")
    alerts = monitor.export_prometheus_alerts()

    with open(alerts_path, 'w') as f:
        json.dump(alerts, f, indent=2)

    logger.info(f"🚨 Prometheus alerts exported to {alerts_path}")

    # Generate detailed report
    report = monitor.get_performance_report()
    print("\n" + "="*60)
    print("DETAILED PERFORMANCE REPORT")
    print("="*60)
    print(json.dumps(report, indent=2, default=str))
    print("="*60)

    # Stop monitoring
    await monitor.stop_monitoring()
    logger.info("✅ Advanced monitoring completed")


async def continuous_monitoring_example():
    """
    Example of continuous monitoring with periodic reports.
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        logger.error("Performance monitor not available")
        return

    logger.info("🚀 Starting continuous performance monitoring...")

    monitor = await start_performance_monitoring(port=9092)

    try:
        for i in range(5):  # 5 monitoring cycles
            logger.info(f"📊 Monitoring cycle {i+1}/5...")

            # Monitor for 30 seconds
            await asyncio.sleep(30)

            # Generate periodic report
            report = generate_performance_report(monitor)
            print(f"\n--- Cycle {i+1} Report ---")
            print(report[:500] + "..." if len(report) > 500 else report)

    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")

    finally:
        await monitor.stop_monitoring()
        logger.info("✅ Continuous monitoring stopped")


async def custom_metrics_example():
    """
    Example of adding custom performance metrics.
    """
    if not PERFORMANCE_MONITOR_AVAILABLE:
        logger.error("Performance monitor not available")
        return

    logger.info("🚀 Starting custom metrics monitoring...")

    monitor = EBPFPerformanceMonitor()

    # Add custom metric (this would normally be done in the monitor)
    # For demonstration, we'll just show the structure

    custom_metrics_config = {
        "custom_metrics": [
            {
                "name": "ebpf_custom_throughput_mbps",
                "type": "gauge",
                "description": "Custom throughput metric in Mbps",
                "labels": ["interface", "direction"]
            },
            {
                "name": "ebpf_custom_error_rate",
                "type": "counter",
                "description": "Custom error rate counter",
                "labels": ["error_type", "severity"]
            }
        ]
    }

    print("Custom metrics configuration:")
    print(json.dumps(custom_metrics_config, indent=2))

    # Start monitoring
    await monitor.start_monitoring()
    await asyncio.sleep(10)

    # In a real implementation, you would register these metrics
    # and update them based on your eBPF program data

    await monitor.stop_monitoring()
    logger.info("✅ Custom metrics monitoring completed")


def create_monitoring_setup_guide():
    """
    Create a comprehensive monitoring setup guide.
    """
    guide = """
# eBPF Performance Monitoring Setup Guide

## Prerequisites

1. **Prometheus** - Metrics collection
   ```bash
   # Install Prometheus
   wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
   tar xvf prometheus-2.40.0.linux-amd64.tar.gz
   cd prometheus-2.40.0.linux-amd64/
   ./prometheus --config.file=prometheus.yml
   ```

2. **Grafana** - Dashboard visualization
   ```bash
   # Install Grafana
   sudo apt-get install grafana
   sudo systemctl start grafana-server
   ```

3. **AlertManager** - Alert handling
   ```bash
   # Install AlertManager
   wget https://github.com/prometheus/alertmanager/releases/download/v0.25.0/alertmanager-0.25.0.linux-amd64.tar.gz
   tar xvf alertmanager-0.25.0.linux-amd64.tar.gz
   ```

## Configuration Files

### 1. Prometheus Configuration (prometheus.yml)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - ebpf_alerts.yml

scrape_configs:
  - job_name: 'ebpf-metrics'
    static_configs:
      - targets: ['localhost:9090']
```

### 2. AlertManager Configuration (alertmanager.yml)

```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@yourdomain.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'email'

receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@yourdomain.com'
```

## Dashboard Import

1. Open Grafana (http://localhost:3000)
2. Go to Dashboards → Import
3. Upload `dashboards/ebpf_performance_dashboard.json`
4. Configure Prometheus as data source

## Alert Rules

The exported `monitoring/ebpf_performance_alerts.yml` contains:

- **EBPFHighLatency**: Alerts when processing latency > 100µs (95th percentile)
- **EBPFPacketDrops**: Alerts when drop rate > 5%
- **EBPFHighCPUUsage**: Alerts when CPU usage > 80%
- **EBPFMemoryPressure**: Alerts when memory usage > 100MB
- **EBPFProgramErrors**: Alerts when error rate > 10 in 10 minutes

## Monitoring Commands

```bash
# Start monitoring
python examples/ebpf_performance_monitoring.py

# View metrics
curl http://localhost:9090/metrics

# Check alerts
curl http://localhost:9093/api/v2/alerts
```

## Troubleshooting

### Common Issues

1. **Metrics not appearing**
   - Check Prometheus targets: http://localhost:9090/targets
   - Verify eBPF programs are loaded
   - Check firewall settings

2. **Alerts not firing**
   - Verify alert rules are loaded in Prometheus
   - Check AlertManager configuration
   - Test with manual alert injection

3. **Dashboard not loading**
   - Ensure Grafana can connect to Prometheus
   - Check dashboard JSON syntax
   - Verify data source configuration

### Performance Tuning

- Adjust scrape intervals based on your needs
- Use appropriate metric aggregation windows
- Configure alert thresholds for your environment
- Monitor system resource usage

## Integration with x0tta6bl4

The performance monitor integrates automatically with the eBPF orchestrator:

```python
from src.network.ebpf.orchestrator import EBPFOrchestrator, OrchestratorConfig

config = OrchestratorConfig(
    interface="eth0",
    enable_performance_monitoring=True,
    prometheus_port=9090
)

orchestrator = EBPFOrchestrator(config)
await orchestrator.start()

# Performance monitoring is now active
status = orchestrator.get_status()
performance = status['metrics']['performance_metrics']
```

This provides end-to-end visibility into your eBPF network performance.
"""

    with open("docs/EBPF_PERFORMANCE_MONITORING_GUIDE.md", "w") as f:
        f.write(guide)

    logger.info("📖 Monitoring setup guide created: docs/EBPF_PERFORMANCE_MONITORING_GUIDE.md")


async def main():
    """
    Main function demonstrating all monitoring examples.
    """
    print("eBPF Performance Monitoring Examples")
    print("=" * 50)

    # Create setup guide
    create_monitoring_setup_guide()

    # Run examples (commented out to avoid long execution)
    # await basic_performance_monitoring()
    # await advanced_monitoring_with_alerting()
    # await continuous_monitoring_example()
    # await custom_metrics_example()

    print("\n✅ All examples prepared!")
    print("Run individual examples by uncommenting in main()")
    print("See docs/EBPF_PERFORMANCE_MONITORING_GUIDE.md for setup instructions")


if __name__ == "__main__":
    asyncio.run(main())