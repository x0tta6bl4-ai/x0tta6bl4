# eBPF Telemetry Module - Usage Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Basic Usage](#basic-usage)
3. [Advanced Usage](#advanced-usage)
4. [Performance Monitoring](#performance-monitoring)
5. [Network Monitoring](#network-monitoring)
6. [Security Monitoring](#security-monitoring)
7. [Custom Metrics](#custom-metrics)
8. [Integration Examples](#integration-examples)
9. [Best Practices](#best-practices)

## Quick Start

### Minimal Example

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import quick_start

# Load eBPF program
bpf = BPF(src_file="performance_monitor.bpf.c")

# Quick start telemetry
collector = quick_start(bpf, "performance_monitor", prometheus_port=9090)

# Metrics are now available at http://localhost:9090/metrics
```

### Full Example

```python
import logging
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    EBPFTelemetryCollector,
    TelemetryConfig,
    MetricType,
    MetricDefinition
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Create configuration
config = TelemetryConfig(
    collection_interval=1.0,
    prometheus_port=9090,
    max_workers=4
)

# Create collector
collector = EBPFTelemetryCollector(config)

# Load eBPF program
bpf = BPF(src_file="performance_monitor.bpf.c")

# Register program
collector.register_program(bpf, "performance_monitor", [
    "process_map",
    "system_metrics_map",
    "perf_events"
])

# Start collector
collector.start()

try:
    # Collect metrics
    metrics = collector.collect_all_metrics()
    print(f"Collected {len(metrics)} program metrics")
    
    # Keep running
    import time
    while True:
        time.sleep(1)
        
except KeyboardInterrupt:
    collector.stop()
```

## Basic Usage

### 1. Simple Counter Collection

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load eBPF program with counter map
bpf = BPF(text="""
#include <uapi/linux/ptrace.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} counter_map SEC(".maps");

SEC("kprobe/do_sys_open")
int count_syscalls(void *ctx) {
    __u32 key = 0;
    __u64 *count = bpf_map_lookup_elem(&counter_map, &key);
    if (count) {
        __sync_fetch_and_add(count, 1);
    }
    return 0;
}

char _license[] SEC("license") = "GPL";
""")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "syscall_counter", ["counter_map"])
collector.start()

# Metrics available at http://localhost:9090/metrics
# Example metric: syscall_counter_counter_map_0
```

### 2. Gauge Collection

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    MetricType,
    MetricDefinition
)

# Load eBPF program
bpf = BPF(src_file="performance_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "performance_monitor")

# Register custom gauge metric
collector.prometheus.register_metric(MetricDefinition(
    name="cpu_usage_percent",
    type=MetricType.GAUGE,
    description="Current CPU usage percentage"
))

# Start collector
collector.start()

# Update gauge manually
collector.prometheus.set_metric("cpu_usage_percent", 45.5)
```

### 3. Histogram Collection

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    MetricType,
    MetricDefinition
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Register histogram metric
collector.prometheus.register_metric(MetricDefinition(
    name="syscall_latency_ms",
    type=MetricType.HISTOGRAM,
    description="System call latency in milliseconds",
    labels=["syscall_name"]
))

# Observe values
collector.prometheus.metrics["syscall_latency_ms"].labels(
    syscall_name="open"
).observe(1.5)

collector.prometheus.metrics["syscall_latency_ms"].labels(
    syscall_name="read"
).observe(0.8)
```

## Advanced Usage

### 1. Custom Event Handlers

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    EBPFTelemetryCollector,
    TelemetryConfig,
    TelemetryEvent,
    EventSeverity
)

# Create collector
config = TelemetryConfig(log_events=True)
collector = EBPFTelemetryCollector(config)

# Load eBPF program
bpf = BPF(src_file="security_monitor.bpf.c")
collector.register_program(bpf, "security_monitor")

# Define custom event handler
def handle_security_event(event: TelemetryEvent):
    """Handle security events."""
    if event.severity >= EventSeverity.HIGH:
        print(f"🚨 HIGH SEVERITY: {event.event_type}")
        print(f"   PID: {event.pid}")
        print(f"   Data: {event.data}")
        
        # Send alert (example)
        # send_alert(event)

# Register handler
collector.perf_reader.register_handler("security_event", handle_security_event)

# Start perf buffer reading
collector.start_perf_reading("security_events")

# Start collector
collector.start()
```

### 2. Batch Processing

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    EBPFTelemetryCollector,
    TelemetryConfig
)

# Configure for batch processing
config = TelemetryConfig(
    collection_interval=5.0,  # Collect every 5 seconds
    batch_size=1000,  # Process 1000 metrics at a time
    max_queue_size=100000
)

collector = EBPFTelemetryCollector(config)

# Load eBPF program
bpf = BPF(src_file="network_monitor.bpf.c")
collector.register_program(bpf, "network_monitor")

# Start collector
collector.start()

# Collect and process in batches
import time
while True:
    metrics = collector.collect_all_metrics()
    
    # Process batch
    for program_name, program_metrics in metrics.items():
        print(f"Processing {len(program_metrics)} metrics from {program_name}")
        
        # Export to Prometheus
        collector.export_to_prometheus(metrics)
    
    time.sleep(5)
```

### 3. Multi-Program Collection

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Create collector
collector = create_collector(prometheus_port=9090)

# Load multiple eBPF programs
perf_bpf = BPF(src_file="performance_monitor.bpf.c")
net_bpf = BPF(src_file="network_monitor.bpf.c")
sec_bpf = BPF(src_file="security_monitor.bpf.c")

# Register all programs
collector.register_program(perf_bpf, "performance_monitor", [
    "process_map",
    "system_metrics_map"
])

collector.register_program(net_bpf, "network_monitor", [
    "connection_map",
    "system_network_map"
])

collector.register_program(sec_bpf, "security_monitor", [
    "connections",
    "system_security_map"
])

# Start collector
collector.start()

# All metrics from all programs are now available
```

## Performance Monitoring

### CPU Usage Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load performance monitor
bpf = BPF(src_file="performance_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "performance_monitor")

# Start collector
collector.start()

# Access CPU metrics
metrics = collector.collect_all_metrics()
perf_metrics = metrics.get("performance_monitor", {})

# Example metrics:
# - performance_monitor_system_metrics_map_0_total_context_switches
# - performance_monitor_system_metrics_map_0_total_syscalls
# - performance_monitor_system_metrics_map_0_cpu_cycles
```

### Memory Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load performance monitor
bpf = BPF(src_file="performance_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "performance_monitor")

# Start collector
collector.start()

# Access memory metrics
metrics = collector.collect_all_metrics()
perf_metrics = metrics.get("performance_monitor", {})

# Example metrics:
# - performance_monitor_system_metrics_map_0_total_memory_allocs
# - performance_monitor_process_map_<pid>_memory_allocations
```

### I/O Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load performance monitor
bpf = BPF(src_file="performance_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "performance_monitor")

# Start collector
collector.start()

# Access I/O metrics
metrics = collector.collect_all_metrics()
perf_metrics = metrics.get("performance_monitor", {})

# Example metrics:
# - performance_monitor_system_metrics_map_0_total_io_ops
# - performance_monitor_process_map_<pid>_io_operations
```

## Network Monitoring

### Packet Counting

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load network monitor
bpf = BPF(src_file="network_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "network_monitor")

# Start collector
collector.start()

# Access network metrics
metrics = collector.collect_all_metrics()
net_metrics = metrics.get("network_monitor", {})

# Example metrics:
# - network_monitor_system_network_map_0_total_packets_ingress
# - network_monitor_system_network_map_0_total_packets_egress
# - network_monitor_system_network_map_0_total_bytes_ingress
# - network_monitor_system_network_map_0_total_bytes_egress
```

### Connection Tracking

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load network monitor
bpf = BPF(src_file="network_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "network_monitor")

# Start collector
collector.start()

# Access connection metrics
metrics = collector.collect_all_metrics()
net_metrics = metrics.get("network_monitor", {})

# Example metrics:
# - network_monitor_system_network_map_0_active_connections
# - network_monitor_connection_map_<key>_packets_ingress
```

### Latency Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    MetricType,
    MetricDefinition
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Register latency histogram
collector.prometheus.register_metric(MetricDefinition(
    name="network_latency_ms",
    type=MetricType.HISTOGRAM,
    description="Network latency in milliseconds",
    labels=["protocol", "direction"]
))

# Load network monitor
bpf = BPF(src_file="network_monitor.bpf.c")
collector.register_program(bpf, "network_monitor")

# Start collector
collector.start()

# Observe latency values
collector.prometheus.metrics["network_latency_ms"].labels(
    protocol="tcp",
    direction="ingress"
).observe(25.5)
```

## Security Monitoring

### Connection Attempt Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Load security monitor
bpf = BPF(src_file="security_monitor.bpf.c")

# Create collector
collector = create_collector(prometheus_port=9090)
collector.register_program(bpf, "security_monitor")

# Start collector
collector.start()

# Access security metrics
metrics = collector.collect_all_metrics()
sec_metrics = metrics.get("security_monitor", {})

# Example metrics:
# - security_monitor_system_security_map_0_total_connection_attempts
# - security_monitor_system_security_map_0_failed_auth_attempts
```

### File Access Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    TelemetryEvent,
    EventSeverity
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Load security monitor
bpf = BPF(src_file="security_monitor.bpf.c")
collector.register_program(bpf, "security_monitor")

# Define file access handler
def handle_file_access(event: TelemetryEvent):
    """Handle suspicious file access."""
    if event.severity >= EventSeverity.HIGH:
        filename = event.data.get("filename", "unknown")
        print(f"🚨 Suspicious file access: {filename} by PID {event.pid}")

# Register handler
collector.perf_reader.register_handler("file_access", handle_file_access)

# Start perf buffer reading
collector.start_perf_reading("security_events")

# Start collector
collector.start()
```

### Privilege Escalation Monitoring

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    TelemetryEvent,
    EventSeverity
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Load security monitor
bpf = BPF(src_file="security_monitor.bpf.c")
collector.register_program(bpf, "security_monitor")

# Define privilege escalation handler
def handle_privilege_escalation(event: TelemetryEvent):
    """Handle privilege escalation attempts."""
    print(f"🚨 PRIVILEGE ESCALATION ATTEMPT!")
    print(f"   PID: {event.pid}")
    print(f"   Old UID: {event.data.get('old_uid')}")
    print(f"   New UID: {event.data.get('new_uid')}")
    
    # Send alert
    # send_alert(event)

# Register handler
collector.perf_reader.register_handler("privilege_escalation", handle_privilege_escalation)

# Start perf buffer reading
collector.start_perf_reading("security_events")

# Start collector
collector.start()
```

## Custom Metrics

### 1. Custom Counter

```python
from src.network.ebpf.telemetry_module import (
    create_collector,
    MetricType,
    MetricDefinition
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Register custom counter
collector.prometheus.register_metric(MetricDefinition(
    name="custom_requests_total",
    type=MetricType.COUNTER,
    description="Total number of custom requests",
    labels=["method", "endpoint"]
))

# Increment counter
collector.prometheus.increment_metric(
    "custom_requests_total",
    amount=1,
    labels={"method": "GET", "endpoint": "/api/health"}
)

# Increment multiple times
for _ in range(10):
    collector.prometheus.increment_metric(
        "custom_requests_total",
        labels={"method": "POST", "endpoint": "/api/data"}
    )
```

### 2. Custom Gauge

```python
from src.network.ebpf.telemetry_module import (
    create_collector,
    MetricType,
    MetricDefinition
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Register custom gauge
collector.prometheus.register_metric(MetricDefinition(
    name="custom_queue_size",
    type=MetricType.GAUGE,
    description="Current queue size",
    labels=["queue_name"]
))

# Set gauge value
collector.prometheus.set_metric(
    "custom_queue_size",
    value=42,
    labels={"queue_name": "processing"}
)

# Update gauge
collector.prometheus.set_metric(
    "custom_queue_size",
    value=38,
    labels={"queue_name": "processing"}
)
```

### 3. Custom Histogram

```python
from src.network.ebpf.telemetry_module import (
    create_collector,
    MetricType,
    MetricDefinition
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Register custom histogram
collector.prometheus.register_metric(MetricDefinition(
    name="custom_request_duration_ms",
    type=MetricType.HISTOGRAM,
    description="Request duration in milliseconds",
    labels=["service"]
))

# Observe values
import random
for _ in range(100):
    duration = random.uniform(10, 100)
    collector.prometheus.metrics["custom_request_duration_ms"].labels(
        service="api"
    ).observe(duration)
```

## Integration Examples

### 1. Integration with MAPE-K

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import create_collector

# Create collector
collector = create_collector(prometheus_port=9090)

# Load eBPF program
bpf = BPF(src_file="performance_monitor.bpf.c")
collector.register_program(bpf, "performance_monitor")

# Start collector
collector.start()

# Integrate with MAPE-K Monitor phase
def monitor_phase():
    """MAPE-K Monitor phase."""
    while True:
        # Collect metrics
        metrics = collector.collect_all_metrics()
        
        # Send to Analyze phase
        # analyze_phase(metrics)
        
        import time
        time.sleep(1)

# Start monitor phase
import threading
monitor_thread = threading.Thread(target=monitor_phase, daemon=True)
monitor_thread.start()
```

### 2. Integration with Alerting System

```python
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    TelemetryEvent,
    EventSeverity
)

# Create collector
collector = create_collector(prometheus_port=9090)

# Load security monitor
bpf = BPF(src_file="security_monitor.bpf.c")
collector.register_program(bpf, "security_monitor")

# Define alert handler
def send_alert(event: TelemetryEvent):
    """Send alert to external system."""
    alert_data = {
        "severity": event.severity.name,
        "event_type": event.event_type,
        "timestamp": event.timestamp_ns,
        "data": event.data
    }
    
    # Send to alerting system
    # requests.post("https://alerts.example.com/api/alerts", json=alert_data)
    print(f"🚨 ALERT: {alert_data}")

# Register handler for critical events
collector.perf_reader.register_handler("security_event", send_alert)

# Start perf buffer reading
collector.start_perf_reading("security_events")

# Start collector
collector.start()
```

### 3. Integration with Logging System

```python
import logging
from bcc import BPF
from src.network.ebpf.telemetry_module import (
    create_collector,
    TelemetryEvent
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ebpf_telemetry")

# Create collector
collector = create_collector(prometheus_port=9090)

# Load eBPF program
bpf = BPF(src_file="performance_monitor.bpf.c")
collector.register_program(bpf, "performance_monitor")

# Define logging handler
def log_event(event: TelemetryEvent):
    """Log telemetry events."""
    logger.info(
        f"Event: {event.event_type}, "
        f"CPU: {event.cpu_id}, "
        f"PID: {event.pid}, "
        f"Data: {event.data}"
    )

# Register handler
collector.perf_reader.register_handler("performance_event", log_event)

# Start perf buffer reading
collector.start_perf_reading("perf_events")

# Start collector
collector.start()
```

## Best Practices

### 1. Resource Management

```python
from src.network.ebpf.telemetry_module import EBPFTelemetryCollector, TelemetryConfig

# Configure for resource efficiency
config = TelemetryConfig(
    collection_interval=5.0,  # Don't collect too frequently
    batch_size=100,  # Process in batches
    max_queue_size=1000,  # Limit queue size
    max_workers=2  # Limit worker threads
)

collector = EBPFTelemetryCollector(config)

# Use context manager for automatic cleanup
with collector:
    # Your code here
    pass
```

### 2. Error Handling

```python
from src.network.ebpf.telemetry_module import create_collector

# Create collector
collector = create_collector(prometheus_port=9090)

# Start collector
collector.start()

try:
    while True:
        try:
            metrics = collector.collect_all_metrics()
            # Process metrics
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            # Continue running
            import time
            time.sleep(1)
            
except KeyboardInterrupt:
    print("Shutting down...")
    collector.stop()
```

### 3. Performance Optimization

```python
from src.network.ebpf.telemetry_module import EBPFTelemetryCollector, TelemetryConfig

# Configure for high performance
config = TelemetryConfig(
    collection_interval=0.1,  # Fast collection
    batch_size=1000,  # Large batches
    max_queue_size=100000,  # Large queue
    max_workers=8,  # Many workers
    read_timeout=2.0,  # Short timeout
    poll_timeout=50  # Fast polling
)

collector = EBPFTelemetryCollector(config)
collector.start()
```

### 4. Security Hardening

```python
from src.network.ebpf.telemetry_module import EBPFTelemetryCollector, TelemetryConfig

# Configure for security
config = TelemetryConfig(
    enable_validation=True,  # Validate all inputs
    enable_sanitization=True,  # Sanitize all data
    sanitize_paths=True,  # Sanitize file paths
    max_metric_value=1e12  # Limit metric values
)

collector = EBPFTelemetryCollector(config)
collector.start()
```

### 5. Monitoring and Observability

```python
from src.network.ebpf.telemetry_module import create_collector

# Create collector
collector = create_collector(prometheus_port=9090)

# Start collector
collector.start()

# Periodically check stats
import time
while True:
    stats = collector.get_stats()
    
    print(f"Total collections: {stats['collection']['total_collections']}")
    print(f"Successful: {stats['collection']['successful_collections']}")
    print(f"Failed: {stats['collection']['failed_collections']}")
    print(f"Avg time: {stats['collection']['average_collection_time']*1000:.2f}ms")
    print(f"Security errors: {stats['security']['validation_errors']}")
    
    time.sleep(60)
```

## Troubleshooting

### Check Collector Status

```python
from src.network.ebpf.telemetry_module import create_collector

collector = create_collector(prometheus_port=9090)

# Get stats
stats = collector.get_stats()
print(json.dumps(stats, indent=2))
```

### Enable Debug Logging

```python
import logging
from src.network.ebpf.telemetry_module import EBPFTelemetryCollector, TelemetryConfig

# Configure debug logging
logging.basicConfig(level=logging.DEBUG)

# Create collector with debug config
config = TelemetryConfig(log_level="DEBUG", log_events=True)
collector = EBPFTelemetryCollector(config)
collector.start()
```

### Test Prometheus Export

```bash
# Check if metrics are available
curl http://localhost:9090/metrics

# Check specific metric
curl http://localhost:9090/metrics | grep performance_monitor
```

## Next Steps

- Review [Installation Guide](TELEMETRY_INSTALLATION.md)
- Read [Architecture Documentation](TELEMETRY_ARCHITECTURE.md)
- Configure Prometheus scraping
- Set up Grafana dashboards
- Integrate with your monitoring stack
