# Core Module

Core application logic, FastAPI server, and autonomic self-healing infrastructure for x0tta6bl4 mesh network.

## Overview

The core module provides:
- **FastAPI Application**: Production REST API with security headers, rate limiting, and error handling
- **MAPE-K Control Loop**: Autonomic self-healing system (Monitor → Analyze → Plan → Execute → Knowledge)
- **Feature Flags**: Runtime feature toggling without redeployment
- **Health Checks**: System and dependency monitoring
- **Logging Configuration**: Structured logging with multiple backends
- **Post-Quantum Cryptography**: LibOQS integration (mandatory in production)
- **Memory Profiling**: Production memory usage tracking

## Architecture

```
┌─────────────────────────────────────────┐
│      FastAPI Application (app.py)       │
│  Security, rate limiting, error handling│
└──────────────────┬──────────────────────┘
                   │
         ┌─────────┴──────────┐
         │                    │
    ┌────▼────────────┐  ┌────▼─────────┐
    │  MAPE-K Loop    │  │Feature Flags  │
    │ (Self-Healing)  │  │(Runtime Ctrl) │
    └────┬────────────┘  └───────────────┘
         │
    ┌────┴────┬────┬───┬─────┐
    │          │    │   │     │
 ┌──▼──┐ ┌───▼──┐┌──▼┐┌──▼┐┌─▼──┐
 │Mon  ││ Anal  ││Plan││Exec││Know│
 │itor ││yze    ││    ││ute ││ledg│
 └─────┘└───────┘└────┘└────┘└────┘
```

## Components

### 1. FastAPI Application (`app.py` - 54.5 KB)

Production REST API server with:
- **Security**: CSP headers, X-Frame-Options, HTTPS enforcement
- **Rate Limiting**: Per-IP limits via slowapi
- **Error Handling**: Custom exception handlers with structured responses
- **Health Checks**: Dependency tracking (PQC, mesh, monitoring)
- **Endpoints**:
  - `GET /health` - Health status with component checks
  - `GET /metrics` - Prometheus metrics
  - `GET /status` - System status (memory, CPU, connections)
  - `POST /api/v1/commands` - Execute mesh commands
  - `WebSocket /ws` - Real-time updates

**Security Features:**
- Mandatory LibOQS PQC in production (no fallback)
- CORS policy enforcement
- Request/response validation (Pydantic)
- Rate limiting (default 100 req/min per IP)
- Security headers (CSP, X-Frame-Options, HSTS)

### 2. MAPE-K Control Loop Implementations

Multiple MAPE-K variants for different use cases:

#### `mape_k_loop.py` (10 KB)
Base MAPE-K implementation:
1. **Monitor**: Collect metrics from Prometheus, mesh, eBPF
2. **Analyze**: Detect anomalies (latency spikes, node failures)
3. **Plan**: Generate remediation actions (reroute, scale, restart)
4. **Execute**: Apply changes via Kubernetes API or eBPF
5. **Knowledge**: Store historical decisions for learning

```python
from src.core.mape_k_loop import MAPEK

mapek = MAPEK()
await mapek.run_cycle()  # Single cycle
await mapek.start()      # Continuous (default: 60s interval)
```

#### `mape_k_self_learning.py` (11.6 KB)
Dynamic threshold optimization based on historical data:
- Learns anomaly thresholds from patterns
- Adapts detection sensitivity
- Reduces false positives over time

#### `mape_k_mttr_optimizer.py` (13.2 KB)
Mean Time To Recovery optimization:
- Tracks recovery time per failure type
- Selects fastest recovery action
- Learns from success/failure rates

#### `mape_k_dynamic_optimizer.py` (8.6 KB)
Adaptive strategy selection:
- Chooses best remediation strategy per anomaly type
- Compares multiple action options
- Tracks success metrics

#### `mape_k_feedback_loops.py` (12.6 KB)
Multi-level feedback management:
- Local feedback (per-node)
- Mesh-level feedback (across nodes)
- Global feedback (system-wide learning)

#### `mape_k_thread_safe.py` (13.3 KB)
Thread-safe variant for concurrent execution:
- Locks for state management
- Queue-based action execution
- Concurrent monitoring

### 3. Feature Flags (`feature_flags.py`)

Runtime feature control:

```python
from src.core.feature_flags import FeatureFlags

flags = FeatureFlags()
if flags.is_enabled("auto_healing"):
    await mapek.start()
```

**Common Flags:**
- `auto_healing`: Enable MAPE-K control loop
- `pqc_required`: Enforce post-quantum crypto
- `mesh_auto_repair`: Auto-repair mesh topology
- `monitoring_verbose`: Verbose logging
- `experimental_features`: Enable beta features

### 4. Health Checks (`health.py`)

System health monitoring:

```python
from src.core.health import HealthChecker

checker = HealthChecker()
status = checker.check_all()
# {
#   "status": "healthy",
#   "checks": {
#     "pqc": "ok",
#     "mesh": "ok", 
#     "database": "ok",
#     "api_latency_ms": 45
#   }
# }
```

### 5. Logging Configuration (`logging_config.py`)

Structured logging with JSON output:

```python
from src.core.logging_config import setup_logging
import logging

setup_logging(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")
logger.info("Started", extra={"service": "core", "version": "3.3.0"})
```

### 6. Memory Profiler (`memory_profiler.py`)

Production memory tracking:

```python
from src.core.memory_profiler import get_memory_profiler

profiler = get_memory_profiler()
stats = profiler.get_memory_stats()
print(f"Memory: {stats['current_mb']}MB, Peak: {stats['peak_mb']}MB")
```

### 7. Production Checks (`production_checks.py`)

Mandatory checks before production startup:
- LibOQS available
- Required dependencies installed
- Configuration valid
- Security settings enforced

### 8. Subprocess Validator (`subprocess_validator.py`)

Safe subprocess execution for mesh commands:
- Command allowlisting
- Timeout enforcement
- Error handling

## Configuration

Environment variables:

```bash
# Deployment mode
ENVIRONMENT=production        # production|staging|development
X0TTA6BL4_PRODUCTION=true     # Enforce production checks (LibOQS required)

# PQC Security
PQC_BACKEND=liboqs            # Required in production
PQC_REQUIRED=true             # Fail if PQC unavailable

# MAPE-K Control Loop
MAPEK_ENABLED=true
MAPEK_CYCLE_INTERVAL_SECONDS=60
MAPEK_TIMEOUT_SECONDS=30
MAPEK_ANOMALY_THRESHOLD=2.0   # Standard deviations

# API Server
HOST=0.0.0.0
PORT=8080
WORKERS=4
HTTPS_ONLY=true
RATE_LIMIT_PER_MINUTE=100
CORS_ORIGINS=["http://localhost:3000"]

# Logging
LOG_LEVEL=INFO                # DEBUG|INFO|WARNING|ERROR
LOG_FORMAT=json               # json|text
LOG_FILE=/var/log/x0tta6bl4/app.log

# Monitoring
PROMETHEUS_PORT=9090
METRICS_ENABLED=true
HEALTH_CHECK_INTERVAL_SECONDS=30
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
pip install liboqs-python>=0.14.1  # Required in production
```

### 2. Set Production Mode

```bash
export X0TTA6BL4_PRODUCTION=true
export ENVIRONMENT=production
```

### 3. Start Application

```bash
# Development
uvicorn src.core.app:app --reload --port 8080

# Production
gunicorn -w 4 -b 0.0.0.0:8080 src.core.app:app
```

### 4. Enable Self-Healing

```bash
curl -X POST http://localhost:8080/api/v1/config/features   -H "Content-Type: application/json"   -d '{"auto_healing": true}'
```

### 5. Monitor

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Logs (JSON)
journalctl -u x0tta6bl4 -f --no-hostname -o json
```

## API Examples

### Health Check with Component Status

```bash
curl http://localhost:8080/health | jq .
{
  "status": "healthy",
  "timestamp": "2025-01-17T15:00:00Z",
  "components": {
    "pqc": {"status": "ok", "latency_ms": 1.2},
    "mesh": {"status": "ok", "nodes": 5, "links": 8},
    "database": {"status": "ok", "connections": 3},
    "api": {"status": "ok", "latency_p95_ms": 42}
  },
  "version": "3.3.0"
}
```

### Execute Mesh Command

```bash
curl -X POST http://localhost:8080/api/v1/commands   -H "Content-Type: application/json"   -d '{
    "command": "reroute_mesh",
    "params": {
      "source": "node-1",
      "destination": "node-5",
      "path": ["node-1", "node-2", "node-5"]
    },
    "timeout_seconds": 10
  }'
```

### Get Prometheus Metrics

```bash
curl http://localhost:8080/metrics | grep x0tta6bl4_
# x0tta6bl4_api_latency_seconds_bucket{endpoint="/health",le="0.1"} 45
# x0tta6bl4_mapek_cycle_duration_seconds{phase="monitor"} 5.2
# x0tta6bl4_pqc_encryption_latency_ms 1.8
```

## Testing

```bash
# Unit tests
pytest tests/unit/test_core_app.py -v
pytest tests/unit/test_mape_k_*.py -v

# Integration tests
pytest tests/integration/test_core_integration.py -v

# Load testing
python tests/performance/benchmark_metrics.py --url http://localhost:8080

# Coverage report
pytest --cov=src.core tests/
```

## Production Deployment

### Docker

```bash
docker run \
  -e X0TTA6BL4_PRODUCTION=true \
  -e ENVIRONMENT=production \
  -p 8080:8080 \
  x0tta6bl4:latest
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: x0tta6bl4-core
spec:
  template:
    spec:
      containers:
      - name: core
        image: x0tta6bl4:latest
        env:
        - name: X0TTA6BL4_PRODUCTION
          value: "true"
        - name: MAPEK_ENABLED
          value: "true"
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
```

### Systemd

```ini
[Unit]
Description=x0tta6bl4 Core Service
After=network.target

[Service]
Type=notify
User=x0tta6bl4
Environment=X0TTA6BL4_PRODUCTION=true
Environment=ENVIRONMENT=production
ExecStart=/usr/local/bin/gunicorn -w 4 src.core.app:app
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| API Latency (p95) | < 100ms | ✅ |
| MAPE-K Cycle | < 60s | ✅ |
| Memory Overhead | < 100MB | ✅ |
| CPU (idle) | < 10% | ✅ |
| PQC Handshake | < 2ms | ✅ |

## Troubleshooting

### LibOQS Not Found (Production Error)

```
CRITICAL: LibOQS REQUIRED but not available!
```

**Solution:**
```bash
pip install liboqs-python>=0.14.1
python -c "from oqs import KeyEncapsulation; print('OK')"
```

### MAPE-K Not Running

```python
from src.core.mape_k_loop import MAPEK
mapek = MAPEK()
print(mapek.status)  # Should be 'running'
print(mapek.cycle_count)  # Should be > 0
```

### High Memory Usage

```python
from src.core.memory_profiler import get_memory_profiler
profiler = get_memory_profiler()
profiler.dump_stats("memory.prof")
# Analyze with: python -m pstats memory.prof
```

### API Latency Issues

1. Check health endpoint: `curl http://localhost:8080/health`
2. Check Prometheus metrics: `curl http://localhost:8080/metrics | grep api_latency`
3. Check logs: `grep "latency\|slow" /var/log/x0tta6bl4/app.log`
4. Profile: `python -m cProfile -s cumtime src.core.app:app`

## Performance Profiling

### CPU Profiling

```bash
python -m cProfile -s cumtime -m uvicorn src.core.app:app
```

### Memory Profiling

```bash
pip install memory_profiler
python -m memory_profiler src/core/app.py
```

### Load Testing

```bash
# k6 script (k6_load_test.js)
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '1m30s', target: 100 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  let res = http.get('http://localhost:8080/health');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'latency < 100ms': (r) => r.timings.duration < 100,
  });
}
```

Run with:
```bash
k6 run k6_load_test.js
```

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Autonomic Computing / MAPE-K](https://en.wikipedia.org/wiki/Autonomic_computing)
- [LibOQS Python Bindings](https://github.com/open-quantum-safe/liboqs-python)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)

## Related Modules

- [Monitoring Module](../monitoring/README.md) - Metrics collection and Prometheus integration
- [Security Module](../security/README.md) - Post-quantum cryptography and zero-trust
- [Mesh Module](../mesh/README.md) - Mesh network topology and routing
- [ML Module](../ml/README.md) - Anomaly detection and decision making
- [Self-Healing Module](../self_healing/README.md) - MAPE-K loop implementations

## Status

✅ **Production Ready**
- MAPE-K: Full implementation with 6 variants
- PQC: LibOQS mandatory in production
- API: FastAPI with comprehensive security
- Health: Dependency tracking
- Logging: Structured JSON logging
- Monitoring: Prometheus metrics

## Version

3.3.0 - January 2025
