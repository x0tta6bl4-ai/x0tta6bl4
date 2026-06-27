# x0tta6bl4 AI Gateway Example

This example demonstrates x0tta6bl4 as a self-healing AI gateway with post-quantum security.

## What this demo shows

- **Self-healing mesh network** with 2 nodes
- **Post-quantum cryptography** (ML-KEM-768 + ML-DSA-65)
- **Zero-trust security** with mTLS and SPIFFE/SPIRE
- **AI-driven threat detection** using RAG pipeline
- **Automatic failover** when a node is down
- **Real-time monitoring** with Prometheus and Grafana

## How to run

1. Make sure Docker is running

2. Run the demo:
   ```bash
   cd examples/ai-gateway
   ./demo.sh
   ```

3. The demo will:
   - Build the x0tta6bl4 image if it doesn't exist
   - Start the mesh network with 2 nodes
   - Wait for services to initialize
   - Verify node health
   - Display demo URLs and next steps

## What to observe

### 1. Service Health
Check if both nodes are healthy:
```bash
curl http://localhost:8081/health
curl http://localhost:8082/health
```

### 2. Metrics
Open Prometheus in your browser: http://localhost:9090

Query for node health:
```promql
x0tta6bl4_node_health
```

### 3. Grafana Dashboard
Open Grafana: http://localhost:3000 (admin/admin)

Add Prometheus data source (http://prometheus:9090) and create a dashboard.

### 4. AI Gateway Usage
Test the chat endpoint:
```bash
curl -X POST http://localhost:8081/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing to a 10-year-old",
    "context": "simple explanation for kids"
  }'
```

### 5. Failover Simulation
Simulate a node failure:
```bash
docker stop x0tta6bl4-node1
```

Wait ~30 seconds and check if node 2 is still healthy:
```bash
curl http://localhost:8082/health
```

The mesh will automatically:
- Detect the failed node (MTTD ~20s)
- Reconfigure the network
- Redirect traffic to healthy nodes

### 6. Restore Node
Bring the failed node back online:
```bash
docker start x0tta6bl4-node1
```

Check if the mesh heals:
```bash
curl http://localhost:8081/health
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  AI Gateway Demo Architecture               │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ Node 1       │  │ Node 2       │        │
│  │ - API        │  │ - API        │        │
│  │ - RAG        │  │ - RAG        │        │
│  │ - Monitor    │  │ - Monitor    │        │
│  └──────────────┘  └──────────────┘        │
│          │                  │               │
│          └──────────┬───────┘               │
│                     ▼                       │
│         ┌──────────────────┐               │
│         │ Mesh Network     │               │
│         │ (Batman-adv)     │               │
│         └──────────────────┘               │
│                     │                       │
│         ┌───────────▼───────────┐          │
│         │ Monitoring Stack     │          │
│         │ - Prometheus         │          │
│         │ - Grafana            │          │
│         └──────────────────────┘          │
│                     │                       │
│         ┌───────────▼───────────┐          │
│         │ Data Storage         │          │
│         │ - PostgreSQL         │          │
│         │ - Redis              │          │
│         └──────────────────────┘          │
│                                             │
└─────────────────────────────────────────────┘
```

## Cleanup

To stop the demo:
```bash
cd examples/ai-gateway
docker-compose down
