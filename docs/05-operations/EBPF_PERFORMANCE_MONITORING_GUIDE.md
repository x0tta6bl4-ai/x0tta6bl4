
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
