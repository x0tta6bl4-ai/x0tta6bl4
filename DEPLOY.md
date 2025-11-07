# Multi-Node Mesh Deployment

This directory contains Docker Compose configuration for deploying x0tta6bl4 as a 3-node mesh network with full observability.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Node A    │────▶│   Node B    │────▶│   Node C    │
│  :8000      │     │  :8001      │     │  :8002      │
│  (primary)  │◀────│ (secondary) │◀────│ (tertiary)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                   Yggdrasil Mesh
                   (IPv6 overlay)
                           │
       ┌───────────────────┴───────────────────┐
       │                                       │
┌──────▼──────┐                     ┌─────────▼────────┐
│ Prometheus  │────────────────────▶│    Grafana       │
│   :9093     │   scrape metrics    │     :3000        │
└─────────────┘                     └──────────────────┘
```

## Services

### Mesh Nodes (x3)
- **node-a** (primary): http://localhost:8000
- **node-b** (secondary): http://localhost:8001
- **node-c** (tertiary): http://localhost:8002

Each node runs:
- FastAPI server with `/health`, `/mesh/status`, `/mesh/peers`, `/mesh/routes` endpoints
- Yggdrasil daemon for mesh networking (auto-configured with peer connections)
- MAPE-K self-healing loop monitoring node health
- Prometheus metrics exporter on port 9090

### Observability Stack
- **Prometheus**: http://localhost:9093 (metrics collection, 15s scrape interval)
- **Grafana**: http://localhost:3000 (dashboards, user: admin / pass: admin)

## Quick Start

### 1. Build and Start Mesh
```bash
# Build Docker images (first time only, ~5-10 minutes)
docker-compose build

# Start all services (nodes + monitoring)
docker-compose up -d

# Watch logs
docker-compose logs -f
```

### 2. Verify Mesh Formation
```bash
# Check node health
curl http://localhost:8000/health  # node-a
curl http://localhost:8001/health  # node-b
curl http://localhost:8002/health  # node-c

# Check mesh status (Yggdrasil info)
curl http://localhost:8000/mesh/status

# Check peer connections
curl http://localhost:8000/mesh/peers

# Check routing table
curl http://localhost:8000/mesh/routes
```

Expected: Each node should report 2 active peers after ~30 seconds.

### 3. Access Monitoring
- Open Grafana: http://localhost:3000
- Login: `admin` / `admin`
- Navigate to Dashboards → x0tta6bl4 → Mesh Overview
- Verify: All 3 nodes online, peer count = 6 (3 nodes × 2 peers each)

## Testing Self-Healing

### Scenario 1: Node Failure
```bash
# Stop node-b to simulate failure
docker-compose stop node-b

# Observe MAPE-K response (check logs on node-a and node-c)
docker-compose logs -f node-a node-c

# Check mesh rebalancing
curl http://localhost:8000/mesh/peers  # Should show node-b missing

# Restore node-b
docker-compose start node-b

# Verify recovery (mesh should reconverge within 10s)
curl http://localhost:8000/mesh/peers  # Should show node-b restored
```

### Scenario 2: Network Partition
```bash
# Isolate node-c from the mesh
docker network disconnect x0tta6bl4_mesh x0tta6bl4-node-c

# Observe routing updates
curl http://localhost:8000/mesh/routes

# Heal partition
docker network connect x0tta6bl4_mesh x0tta6bl4-node-c

# Verify full mesh restoration
curl http://localhost:8000/mesh/peers
```

## Integration Tests

Run automated integration tests (requires mesh running):
```bash
# From project root
pytest tests/integration/test_mesh_self_healing.py -v

# With coverage
pytest tests/integration/ --cov=src --cov-report=term-missing -v
```

Tests include:
- `test_node_failure_recovery`: Stop node → verify MAPE-K detects → restart → verify convergence
- `test_network_partition`: Isolate node → verify routing updates → heal → verify restoration
- `test_consensus_election`: Stop leader → verify election → verify new leader
- `test_distributed_kvstore`: Put/get across nodes → stop node → verify data persistence

## Performance Benchmarks

Run locust load tests:
```bash
# Install locust
pip install locust

# Run benchmark against all 3 nodes
locust -f tests/performance/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10

# Expected results (laptop-class hardware):
# - p50 latency: <50ms
# - p95 latency: <200ms
# - p99 latency: <500ms
# - Max RPS per node: ~500
```

## Troubleshooting

### Nodes not forming mesh
```bash
# Check Yggdrasil daemon status
docker-compose exec node-a sudo yggdrasilctl getSelf
docker-compose exec node-b sudo yggdrasilctl getSelf
docker-compose exec node-c sudo yggdrasilctl getSelf

# Verify peer configuration
docker-compose exec node-a cat /etc/yggdrasil/yggdrasil.conf | grep -A 5 Peers

# Restart Yggdrasil if needed
docker-compose restart node-a node-b node-c
```

### Prometheus not scraping metrics
```bash
# Check Prometheus targets
curl http://localhost:9093/api/v1/targets | jq

# Verify node metrics endpoint
curl http://localhost:9090/metrics  # node-a metrics

# Check Prometheus logs
docker-compose logs prometheus
```

### Grafana dashboard empty
```bash
# Verify Prometheus data source
curl http://localhost:3000/api/datasources

# Check if metrics are arriving
curl 'http://localhost:9093/api/v1/query?query=up'

# Restart Grafana
docker-compose restart grafana
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

## Configuration

### Environment Variables
Override in `docker-compose.yml` or create `.env`:
```bash
NODE_ID=node-a               # Unique node identifier
LISTEN_HOST=0.0.0.0          # API server bind address
LISTEN_PORT=8000             # API server port
LOG_LEVEL=info               # Logging level (debug, info, warning, error)
YGGDRASIL_PEERS=tcp://...    # Comma-separated peer URIs
```

### Scaling to N Nodes
To add more nodes, edit `docker-compose.yml`:
1. Copy `node-c` service definition
2. Rename to `node-d`, increment ports (8003, 9093)
3. Update `YGGDRASIL_PEERS` for all nodes to include new node
4. Add new target to `infra/monitoring/prometheus.yml`

## Next Steps

1. **Integration Tests**: See `tests/integration/test_mesh_self_healing.py`
2. **SPIFFE/SPIRE**: Enable mTLS between nodes (roadmap: Week 3)
3. **Production Deployment**: Kubernetes Helm chart (roadmap: Week 4)
4. **eBPF/XDP**: Enable advanced traffic shaping (roadmap: Week 4)

## Documentation

- Main README: `../README.md`
- Architecture: `../docs/ARCHITECTURE.md`
- Security: `../SECURITY.md`
- Contributing: `../CONTRIBUTING.md`
