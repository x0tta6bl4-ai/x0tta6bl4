# x0tta6bl4 AI Gateway Demo

This demo shows how to use x0tta6bl4 as a self-healing AI gateway with post-quantum cryptography and zero-trust security.

---

## What this demo shows

1. **Self-healing mesh network** with Batman-adv and Yggdrasil
2. **Post-quantum cryptography** using ML-KEM-768 and ML-DSA-65
3. **Zero-trust security** with mTLS and SPIFFE/SPIRE
4. **AI-driven threat detection** with 17 ML/AI components
5. **Prometheus metrics** for real-time monitoring

---

## How to run

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)

### Run the demo
```bash
cd examples/ai-gateway
docker-compose up -d
```

### Health Check
```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "3.3.0", "timestamp": "..."}
```

### Prometheus Metrics
Open your browser and go to `http://localhost:9090`.

You should see metrics like:
- `x0tta6bl4_api_requests_total` - Total API requests
- `x0tta6bl4_api_request_duration_seconds` - API request duration
- `x0tta6bl4_mesh_nodes_total` - Number of mesh nodes
- `x0tta6bl4_threat_detection_total` - Number of threats detected

---

## What to observe

### Mesh Network Status
```bash
curl http://localhost:8000/api/v1/mesh/nodes
```

You should see information about the mesh nodes, including:
- Node ID
- IP address
- Status (connected/disconnected)
- Threat level (low/medium/high)

### Threat Detection
```bash
curl http://localhost:8000/api/v1/threats
```

You should see a list of detected threats, including:
- Threat ID
- Type (malware/phishing/ddos)
- Source IP
- Destination IP
- Severity (low/medium/high)

---

## How to break it (failure injection)

### Disconnect a node
```bash
docker stop x0tta6bl4_1
```

Wait 30 seconds and check the mesh network status:
```bash
curl http://localhost:8000/api/v1/mesh/nodes
```

The node should be marked as disconnected, and the mesh should automatically heal.

### Restore the node
```bash
docker start x0tta6bl4_1
```

Wait 30 seconds and check the mesh network status:
```bash
curl http://localhost:8000/api/v1/mesh/nodes
```

The node should be marked as connected again.

---

## Cleanup
```bash
cd examples/ai-gateway
docker-compose down -v
```
