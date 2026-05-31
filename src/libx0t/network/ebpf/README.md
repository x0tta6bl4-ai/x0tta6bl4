# x0tta6bl4 eBPF Subsystem Documentation

## Overview

The eBPF subsystem provides high-performance network monitoring, filtering, and observability capabilities for the x0tta6bl4 decentralized mesh network. It leverages Linux eBPF (extended Berkeley Packet Filter) technology to implement zero-trust networking with sub-microsecond latency.

## Architecture

### Core Components

- **EBPFLoader**: Loads and manages eBPF programs, handles attachment to network interfaces
- **EBPFOrchestrator**: Unified control point for all eBPF operations, lifecycle management
- **CLI Interface**: Command-line tools for administration and monitoring
- **BCC Probes**: Dynamic instrumentation for network flow monitoring
- **Cilium Integration**: Hubble-like flow observability and network policy
- **Metrics Exporter**: Prometheus-compatible metrics collection
- **Dynamic Fallback**: Automatic degradation handling for system stability
- **MAPE-K Integration**: Autonomic self-healing capabilities

### Program Types Supported

- **XDP (eXpress Data Path)**: Fastest packet processing at network driver level
- **TC (Traffic Control)**: Classifier and action programs for QoS
- **cgroup_skb**: Socket buffer control for container networking
- **Socket Filter**: Classic socket-level filtering

## Installation

### Prerequisites

```bash
# Install BCC (BPF Compiler Collection)
sudo apt-get install bpfcc-tools linux-headers-$(uname -r)

# Install Python dependencies
pip install pyelftools prometheus-client

# For development
pip install pytest mock
```

### Quick Start

```python
from src.network.ebpf.orchestrator import EBPFOrchestrator, OrchestratorConfig

# Create configuration
config = OrchestratorConfig(
    interface="eth0",
    enable_flow_observability=True,
    enable_metrics_export=True,
    prometheus_port=9090
)

# Initialize orchestrator
orchestrator = EBPFOrchestrator(config)

# Start the system
await orchestrator.start()

# Monitor flows
flows = await orchestrator.get_flows()
print(f"Active flows: {len(flows)}")

# Get metrics
metrics = orchestrator.get_metrics()
print(f"Packet rate: {metrics.get('packets_per_second', 0)}")

# Cleanup
await orchestrator.stop()
```

## CLI Usage

### Basic Commands

```bash
# View system status
x0tta6bl4-ebpf status

# Load eBPF program
x0tta6bl4-ebpf load xdp_firewall.o

# Attach program to interface
x0tta6bl4-ebpf attach program_123 eth0

# View statistics
x0tta6bl4-ebpf stats

# Monitor network flows
x0tta6bl4-ebpf flows --source 192.168.1.1 --dest 10.0.0.1

# Health check
x0tta6bl4-ebpf health
```

### Advanced Commands

```bash
# Load with specific parameters
x0tta6bl4-ebpf load xdp_monitor.o --mode drv --priority 100

# View detailed program information
x0tta6bl4-ebpf programs --verbose

# Export metrics to file
x0tta6bl4-ebpf metrics --export metrics.json

# Debug mode
x0tta6bl4-ebpf debug --enable --log-level DEBUG
```

## Configuration

### Orchestrator Configuration

```python
from src.network.ebpf.orchestrator import OrchestratorConfig

config = OrchestratorConfig(
    interface="eth0",                    # Network interface to monitor
    programs_dir="/opt/x0tta6bl4/ebpf", # Directory with .o files
    enable_flow_observability=True,      # Enable Cilium-like flow monitoring
    enable_metrics_export=True,          # Export metrics to Prometheus
    enable_dynamic_fallback=True,        # Enable fallback on failures
    enable_mapek_integration=True,       # Enable self-healing
    prometheus_port=9090,               # Metrics export port
    latency_threshold_ms=100.0,         # Alert threshold
    monitoring_interval_seconds=10.0,   # Monitoring frequency
    auto_load_programs=True             # Auto-load programs on start
)
```

### Program-Specific Configuration

```json
{
  "xdp_firewall": {
    "type": "xdp",
    "attach_mode": "drv",
    "rules": [
      {"action": "drop", "source_ip": "192.168.1.100"},
      {"action": "allow", "protocol": "tcp", "port": 443}
    ]
  },
  "tc_shaper": {
    "type": "tc",
    "bandwidth_limit": "100mbit",
    "latency_target": "50ms"
  }
}
```

## API Reference

### EBPFLoader

```python
class EBPFLoader:
    def __init__(self, programs_dir: Optional[Path] = None)
    def load_program(self, program_path: str) -> str
    def attach_to_interface(self, program_id: str, interface: str, program_type: EBPFProgramType) -> bool
    def detach_from_interface(self, program_id: str, interface: str) -> bool
    def unload_program(self, program_id: str) -> bool
    def get_stats(self) -> Dict[str, Any]
    def update_routes(self, routes: Dict[str, Any]) -> bool
    def cleanup(self) -> None
```

### EBPFOrchestrator

```python
class EBPFOrchestrator:
    async def start(self) -> None
    async def stop(self) -> None
    def get_status(self) -> Dict[str, Any]
    async def load_program(self, program_name: str) -> str
    async def attach_program(self, program_id: str, interface: str, program_type: EBPFProgramType) -> bool
    async def detach_program(self, program_id: str, interface: str) -> bool
    async def unload_program(self, program_id: str) -> str
    async def get_flows(self, filters: Optional[Dict] = None) -> List[Dict]
    def get_metrics(self) -> Dict[str, Any]
    def health_check(self) -> Dict[str, Any]
    def list_programs(self) -> List[Dict]
```

## Monitoring and Metrics

### Prometheus Metrics

The system exports the following metrics to Prometheus:

- `ebpf_programs_loaded`: Number of loaded eBPF programs
- `ebpf_packets_processed_total`: Total packets processed
- `ebpf_packets_dropped_total`: Total packets dropped
- `ebpf_flows_active`: Number of active network flows
- `ebpf_latency_microseconds`: Processing latency in microseconds
- `ebpf_errors_total`: Total number of errors
- `ebpf_memory_usage_bytes`: Memory usage of eBPF maps

### Health Checks

```python
# Get health status
health = orchestrator.health_check()
print(health)
# Output: {'status': 'healthy', 'checks': {...}}
```

### Alerts

The system generates alerts for:
- High latency (> 100ms)
- Program loading failures
- Interface attachment failures
- Memory usage > 80%
- Packet drop rate > 5%

## Examples

### Basic Packet Filtering

```python
from src.network.ebpf.orchestrator import EBPFOrchestrator, OrchestratorConfig

async def setup_firewall():
    config = OrchestratorConfig(interface="eth0")
    orchestrator = EBPFOrchestrator(config)

    await orchestrator.start()

    # Load XDP firewall
    program_id = await orchestrator.load_program("xdp_firewall.o")
    await orchestrator.attach_program(program_id, "eth0", EBPFProgramType.XDP)

    # Monitor blocked packets
    while True:
        stats = orchestrator.get_status()
        blocked = stats.get('blocked_packets', 0)
        print(f"Blocked packets: {blocked}")
        await asyncio.sleep(5)

asyncio.run(setup_firewall())
```

### Flow Monitoring

```python
async def monitor_flows():
    config = OrchestratorConfig(enable_flow_observability=True)
    orchestrator = EBPFOrchestrator(config)

    await orchestrator.start()

    # Get all flows
    flows = await orchestrator.get_flows()
    for flow in flows:
        print(f"Flow: {flow['source']} -> {flow['destination']} "
              f"({flow['packets']} packets, {flow['bytes']} bytes)")

    # Filter flows
    tcp_flows = await orchestrator.get_flows({
        'protocol': 'tcp',
        'min_packets': 100
    })

asyncio.run(monitor_flows())
```

### Custom Metrics Export

```python
from src.network.ebpf.metrics_exporter import EBPFMetricsExporter

def setup_custom_metrics():
    exporter = EBPFMetricsExporter(port=9090)

    # Add custom metric
    exporter.add_metric(
        name="ebpf_custom_packets",
        type="counter",
        description="Custom packet counter",
        labels=["interface", "direction"]
    )

    exporter.start()

setup_custom_metrics()
```

## Troubleshooting

### Common Issues

1. **Program loading fails**
   - Check if BCC is installed: `which bpftool`
   - Verify kernel version: `uname -r`
   - Check program file permissions

2. **Attachment fails**
   - Ensure interface exists: `ip link show`
   - Check if another program is attached: `bpftool prog show`
   - Try different attach mode (skb instead of drv)

3. **High latency**
   - Monitor system load: `uptime`
   - Check eBPF map sizes: `bpftool map show`
   - Consider hardware offload if available

4. **Memory issues**
   - Monitor eBPF memory: `bpftool map show | grep -E "(bytes|entries)"`
   - Check system memory: `free -h`
   - Reduce map sizes in programs

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via CLI
x0tta6bl4-ebpf debug --enable
```

### Logs Location

- System logs: `/var/log/x0tta6bl4/ebpf.log`
- BCC debug: `bcc -d`
- Kernel messages: `dmesg | grep bpf`

## Development

### Running Tests

```bash
# Unit tests
pytest tests/test_ebpf_loader.py -v
pytest tests/test_ebpf_orchestrator.py -v

# Integration tests
pytest tests/test_ebpf_integration.py -v

# All tests
make test
```

### Building eBPF Programs

```bash
# Compile XDP program
clang -O2 -target bpf -c xdp_program.c -o xdp_program.o

# With BCC
python3 -c "from bcc import BPF; BPF(src_file='program.c').load_func('xdp_func', 'xdp')"
```

### Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Ensure backward compatibility

## Security Considerations

- eBPF programs run in kernel space - validate all bytecode
- Use safe attach modes (skb) in production initially
- Monitor for privilege escalation attempts
- Regular security audits of eBPF code
- Zero-trust principles: never trust, always verify

## Performance Tuning

### Optimization Tips

1. **Use appropriate attach modes**: drv > skb > hw (when available)
2. **Minimize map operations**: Cache frequently accessed data
3. **Batch operations**: Process multiple packets when possible
4. **Monitor drop rates**: High drops indicate overload
5. **Tune map sizes**: Balance memory usage vs performance

### Benchmarks

- XDP packet processing: < 10µs per packet
- TC classification: < 50µs per packet
- Memory overhead: < 100MB for typical deployments
- CPU usage: < 5% for 10Gbps traffic

## License

This component is part of the x0tta6bl4 project. See main project license for details.

## Support

- Documentation: [docs/README.md](../../docs/README.md)
- Issues: [GitHub Issues](../../issues)
- Discussions: [GitHub Discussions](../../discussions)