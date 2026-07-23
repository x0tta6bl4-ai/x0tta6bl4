# x0tta6bl4 API Quickstart

Working code examples for the most common API endpoints.

## Base URLs

| Service | URL | Description |
|:--------|:----|:------------|
| Mesh Node (local) | `http://localhost:9100` | Quick Start single node |
| Mesh Node (2-node) | `http://localhost:9190` | Docker Compose mesh |
| Prometheus | `http://localhost:9090` | Metrics (via override) |

---

## Mesh Node Endpoints

### Health Check

```bash
curl -s http://localhost:9100/health | python3 -m json.tool
```

```python
import requests

resp = requests.get("http://localhost:9100/health")
print(resp.json())
```

**Response:**
```json
{
  "node_id": "mesh-node",
  "status": "ok",
  "uptime": 120,
  "peers": ["mesh-node-2"],
  "consensus_count": 4
}
```

---

### List Peers

```bash
curl -s http://localhost:9100/peers | python3 -m json.tool
```

```python
import requests

resp = requests.get("http://localhost:9100/peers")
print(resp.json())
```

**Response:**
```json
{
  "mesh-node-2": {
    "peer_id": "mesh-node-2",
    "address": "172.18.0.3:9103",
    "status": "active",
    "last_seen": 1721712000.0,
    "missed_announcements": 0
  }
}
```

---

### Get Routing Table

```bash
curl -s http://localhost:9100/routing | python3 -m json.tool
```

```python
import requests

resp = requests.get("http://localhost:9100/routing")
print(resp.json())
```

**Response:**
```json
{
  "node_id": "mesh-node",
  "entries": [
    {
      "peer_id": "mesh-node-2",
      "address": "172.18.0.3",
      "status": "resolved",
      "last_updated": 1721712000.0
    }
  ]
}
```

---

### Send Consensus Request

```bash
curl -s -X POST http://localhost:9100/consensus \
  -H "Content-Type: application/json" \
  -d '{
    "type": "routine_check",
    "severity": "low",
    "failure_rate": 0.0,
    "total_packets": 10
  }' | python3 -m json.tool
```

```python
import requests

resp = requests.post("http://localhost:9100/consensus", json={
    "type": "routine_check",
    "severity": "low",
    "failure_rate": 0.0,
    "total_packets": 10,
})
print(resp.json())
```

**Response:**
```json
{
  "approved": true,
  "session_id": "hb-1"
}
```

---

### Forward Message

```bash
curl -s -X POST http://localhost:9100/message \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "mesh-node-2",
    "payload": {"action": "ping"}
  }' | python3 -m json.tool
```

```python
import requests

resp = requests.post("http://localhost:9100/message", json={
    "destination": "mesh-node-2",
    "payload": {"action": "ping"},
})
print(resp.json())
```

**Response:**
```json
{
  "status": "delivered",
  "destination": "mesh-node-2",
  "payload": {"action": "ping"}
}
```

---

### Prometheus Metrics

```bash
curl -s http://localhost:9190/metrics | grep x0tta6bl4_mesh
```

```python
import requests

resp = requests.get("http://localhost:9190/metrics")
for line in resp.text.splitlines():
    if "x0tta6bl4_mesh" in line:
        print(line)
```

**Response (excerpt):**
```
# HELP x0tta6bl4_mesh_health_score Mesh node health score baseline
# TYPE x0tta6bl4_mesh_health_score gauge
x0tta6bl4_mesh_health_score{node_id="mesh-node"} 20.0
# HELP x0tta6bl4_mesh_uptime_seconds Seconds since the mesh node started
# TYPE x0tta6bl4_mesh_uptime_seconds gauge
x0tta6bl4_mesh_uptime_seconds{node_id="mesh-node"} 120
# HELP x0tta6bl4_mesh_peers_connected Number of currently valid/active peers
# TYPE x0tta6bl4_mesh_peers_connected gauge
x0tta6bl4_mesh_peers_connected{node_id="mesh-node"} 1
```

---

## MaaS API Endpoints

Base URL: `http://localhost:8280` (Quick Start) or your deployed instance.

### Register Node

```bash
curl -s -X POST http://localhost:8280/v1/mesh/mesh-001/nodes/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "node-alpha",
    "address": "192.168.1.10:9100",
    "capabilities": ["vpn", "relay"]
  }' | python3 -m json.tool
```

```python
import requests

resp = requests.post("http://localhost:8280/v1/mesh/mesh-001/nodes/register", json={
    "node_id": "node-alpha",
    "address": "192.168.1.10:9100",
    "capabilities": ["vpn", "relay"],
})
print(resp.json())
```

---

### List Mesh Nodes

```bash
curl -s http://localhost:8280/v1/mesh/mesh-001/nodes | python3 -m json.tool
```

```python
import requests

resp = requests.get("http://localhost:8280/v1/mesh/mesh-001/nodes")
for node in resp.json():
    print(f"{node['node_id']}: {node['status']}")
```

---

### Heal Node

```bash
curl -s -X POST http://localhost:8280/v1/mesh/mesh-001/nodes/node-alpha/heal \
  -H "Content-Type: application/json" | python3 -m json.tool
```

```python
import requests

resp = requests.post("http://localhost:8280/v1/mesh/mesh-001/nodes/node-alpha/heal")
print(resp.json())
```

---

### VPN Subscription Status

```bash
curl -s http://localhost:8280/v1/vpn/subscription/status | python3 -m json.tool
```

```python
import requests

resp = requests.get("http://localhost:8280/v1/vpn/subscription/status")
print(resp.json())
```

---

### Billing Readiness

```bash
curl -s http://localhost:8280/v1/billing/readiness | python3 -m json.tool
```

```python
import requests

resp = requests.get("http://localhost:8280/v1/billing/readiness")
print(resp.json())
```

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "detail": "Node not found",
  "status_code": 404
}
```

Common HTTP codes:

| Code | Meaning |
|:-----|:--------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (missing/invalid fields) |
| 403 | Forbidden (invalid SVID signature) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Quick Start

```bash
# Start 2-node mesh
cd quickstart
docker compose up -d

# Check health
curl -s http://localhost:8280/health

# List peers
curl -s http://localhost:9190/peers

# View metrics
curl -s http://localhost:9190/metrics | grep x0tta6bl4_mesh
```
