# SPIRE/SPIFFE Deployment Guide

**Quick Start**: Deploy Zero-Trust identity management to x0tta6bl4 mesh network.

---

## 🚀 Quick Start (3 Steps)

### 1. Generate CA Certificates

```bash
cd /mnt/AC74CC2974CBF3DC
./scripts/ca-bootstrap.sh
```

This creates:
- `infra/security/ca/root-ca.crt` - Root CA certificate
- `infra/security/ca/server-ca.crt` - Server CA certificate
- `infra/security/ca/trust-bundle.pem` - Trust bundle for agents

**⚠️ Security**: Private keys are generated but should be stored securely (KMS/Vault for production).

### 2. Deploy SPIRE Server

```bash
kubectl apply -f infra/security/spire-server-deployment.yaml
```

Wait for server to be ready:
```bash
kubectl wait --for=condition=ready pod -l app=spire-server -n spire-system --timeout=120s
```

### 3. Deploy SPIRE Agent

```bash
kubectl apply -f infra/security/spire-agent-daemonset.yaml
```

Verify agents are running:
```bash
kubectl get pods -n spire-system -l app=spire-agent
```

---

## 📋 Verification

### Check SPIRE Server Health

```bash
# Server logs
kubectl logs -n spire-system spire-server-0

# Server metrics (if Prometheus installed)
curl http://spire-server.spire-system.svc.cluster.local:9988/metrics
```

### Check SPIRE Agent Health

```bash
# Agent logs (on each node)
kubectl logs -n spire-system -l app=spire-agent --tail=50

# Agent metrics
curl http://localhost:9989/metrics
```

### Verify Workload API Socket

```bash
# On a node with SPIRE Agent
ls -la /run/spire/sockets/agent.sock
```

---

## 🔧 Mesh Node Integration

After SPIRE Server and Agents are deployed, bootstrap mesh nodes:

```bash
# Deploy SPIFFE to all mesh nodes
python scripts/deploy_spiffe_to_mesh_nodes.py --nodes all

# Or specific nodes
python scripts/deploy_spiffe_to_mesh_nodes.py --nodes node-001,node-002
```

---

## 📊 Monitoring

### Prometheus Metrics

**SPIRE Server** (`:9988`):
- `spire_server_svid_issued_total` - SVIDs issued
- `spire_server_node_attestations_total` - Node attestations
- `spire_server_ca_rotation_total` - CA rotations

**SPIRE Agent** (`:9989`):
- `spire_agent_svid_rotations_total` - SVID rotations
- `spire_agent_workload_api_connections` - Active connections
- `spire_agent_svid_cache_size` - Cached SVIDs

### Grafana Dashboard

Import dashboard from `infra/monitoring/grafana-dashboard-spire.json` (TODO: create).

---

## 🔐 Security Best Practices

1. **CA Key Protection**
   - Root CA keys: Store offline, encrypted
   - Server CA keys: Use KMS/Vault for production
   - Regular CA rotation (quarterly)

2. **Join Token Management**
   - Tokens are single-use
   - Tokens expire after 5 minutes
   - Audit all token usage

3. **Workload Selectors**
   - Least privilege principle
   - Explicit selectors (no wildcards)
   - Regular audit of registrations

4. **mTLS Configuration**
   - TLS 1.3 only
   - Strong cipher suites
   - Certificate pinning for critical services

---

## 🐛 Troubleshooting

### SPIRE Server not starting

```bash
# Check logs
kubectl logs -n spire-system spire-server-0

# Check config
kubectl get configmap spire-server-config -n spire-system -o yaml

# Verify CA files exist
kubectl exec -n spire-system spire-server-0 -- ls -la /run/spire/data
```

### SPIRE Agent not connecting

```bash
# Check agent logs
kubectl logs -n spire-system -l app=spire-agent --tail=100

# Verify server address
kubectl get configmap spire-agent-config -n spire-system -o yaml | grep server_address

# Test connectivity
kubectl exec -n spire-system <agent-pod> -- nc -zv spire-server.spire-system.svc.cluster.local 8081
```

### Workload API not accessible

```bash
# Check socket exists
kubectl exec -n spire-system <agent-pod> -- ls -la /run/spire/sockets/agent.sock

# Verify permissions
kubectl exec -n spire-system <agent-pod> -- stat /run/spire/sockets/agent.sock
```

---

## 📚 Next Steps

1. **Register Mesh Node Identities**
   ```python
   from src.security.spiffe import SPIFFEController
   
   controller = SPIFFEController(trust_domain="x0tta6bl4.mesh")
   controller.initialize(attestation_strategy="join_token", token="...")
   ```

2. **Enable mTLS for Mesh Services**
   - Integrate in `src/core/app.py` (FastAPI)
   - Integrate in `src/network/batman/topology.py` (mesh networking)

3. **Configure Certificate Rotation**
   - Automatic SVID rotation at 50% TTL
   - Monitor rotation health via Prometheus

---

## 📝 Files

- `spire-server-deployment.yaml` - SPIRE Server StatefulSet
- `spire-agent-daemonset.yaml` - SPIRE Agent DaemonSet
- `ca-bootstrap.sh` - CA certificate generation
- `mtls_spire_deployment.md` - Full deployment architecture
- `deploy_spiffe_to_mesh_nodes.py` - Mesh node bootstrap script

---

**Дата создания**: 2025-01-XX  
**Версия**: 1.0.0  
**Статус**: Ready for Deployment ✅

