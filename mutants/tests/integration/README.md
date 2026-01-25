# Integration Tests for x0tta6bl4 Mesh

This directory contains integration tests that verify multi-node mesh behavior, self-healing capabilities, and real-world scenarios.

## Prerequisites

- Docker and docker-compose installed
- Mesh running: `docker-compose up -d` from project root
- All 3 nodes healthy (verify with `docker-compose ps`)

## Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov=src --cov-report=term-missing -v

# Run specific test module
pytest tests/integration/test_mesh_self_healing.py -v

# Run specific test
pytest tests/integration/test_mesh_self_healing.py::test_node_failure_recovery -v
```

## Test Scenarios

### test_mesh_self_healing.py
- **test_mesh_formation**: Verify all 3 nodes online, peer connections established
- **test_node_failure_recovery**: Stop node-b → MAPE-K detects → restart → verify reconvergence
- **test_network_partition**: Isolate node → routing updates → heal → full restoration
- **test_consensus_election**: Stop leader → election → verify new leader
- **test_distributed_kvstore**: Put/get across nodes → stop node → verify data persists
- **test_self_healing_metrics**: Verify Prometheus metrics for MAPE-K cycles

### test_mesh_performance.py
- **test_latency_within_sla**: Verify p50 <50ms, p95 <200ms, p99 <500ms
- **test_throughput**: Verify >100 req/s per node under load
- **test_concurrent_requests**: 100 parallel requests → all succeed
- **test_mesh_overhead**: Compare direct vs mesh-routed latency

## Markers

```bash
# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "integration and not slow"
```

## Expected Coverage Improvement

Integration tests naturally cover edge cases difficult to reach with unit tests:
- `topology.py`: Dijkstra with unreachable nodes, path reconstruction failures
- `raft_consensus.py`: Election splits, network partitions, state transitions
- `notification_suite.py`: watch() timeout scenarios, pod state changes

Expected coverage increase: **74% → 78-80%** without additional unit test grinding.

## Troubleshooting

### Tests fail: "Connection refused to localhost:8000"
- Verify mesh is running: `docker-compose ps`
- Check node health: `curl http://localhost:8000/health`
- View logs: `docker-compose logs node-a`

### Tests timeout
- Increase timeouts in test fixtures (default: 30s mesh convergence)
- Check if nodes are CPU/memory constrained: `docker stats`

### Mesh not forming
- Verify Yggdrasil daemon: `docker-compose exec node-a sudo yggdrasilctl getSelf`
- Check peer config: `docker-compose exec node-a cat /etc/yggdrasil/yggdrasil.conf`
- Restart mesh: `docker-compose restart`
