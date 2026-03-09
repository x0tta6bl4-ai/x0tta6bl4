# x0tta6bl4 API - Interactive Examples

This guide provides `curl` examples to interact with the MaaS API endpoints. Ensure you have your `X-API-Key` ready.

## 1. Supply Chain & Attestation

### Get SBOM Registry
List all registered SBOMs for your environment.

```bash
curl -X GET "http://localhost:8000/api/v1/maas/supply-chain/sbom" \
     -H "X-API-Key: YOUR_ADMIN_API_KEY" \
     -H "Content-Type: application/json"
```

### Get Mesh Integrity Report
Check if any nodes in your mesh are compromised (binary mismatch).

```bash
curl -X GET "http://localhost:8000/api/v1/maas/supply-chain/mesh-attestation-report/mesh-12345" \
     -H "X-API-Key: YOUR_ADMIN_API_KEY" \
     -H "Content-Type: application/json"
```

## 2. Mesh Federation

### Create a Federation Link
Request a link between your mesh and a target mesh (cross-tenant routing).

```bash
curl -X POST "http://localhost:8000/api/v1/maas/federation/mesh-12345/link" \
     -H "X-API-Key: YOUR_ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "target_mesh_id": "mesh-67890",
       "policy": "allow_all"
     }'
```

### Approve a Federation Request
Approve a pending request from another tenant.

```bash
curl -X POST "http://localhost:8000/api/v1/maas/federation/fed-abc123def456/approve" \
     -H "X-API-Key: YOUR_ADMIN_API_KEY" \
     -H "Content-Type: application/json"
```

## 3. Telemetry & Heartbeat

### Submit Node Heartbeat (Agent)
Simulate a node heartbeat with latency and CPU metrics.

```bash
curl -X POST "http://localhost:8000/api/v1/maas/heartbeat" \
     -H "X-API-Key: YOUR_NODE_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "node_id": "node-777",
       "mesh_id": "mesh-12345",
       "cpu_usage": 45.2,
       "memory_usage": 60.1,
       "neighbors_count": 3,
       "routing_table_size": 15,
       "uptime": 3600,
       "custom_metrics": {
         "latency_ms": 12.5,
         "total_pkts": 150000,
         "dropped_pkts": 12
       }
     }'
```

## 4. Governance & Staking

### Stake Tokens for DAO Voting Power
Enterprise users can stake X0T tokens for governance.

```bash
curl -X POST "http://localhost:8000/api/v1/maas/governance/stake" \
     -H "X-API-Key: YOUR_ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 5000.0
     }'
```
