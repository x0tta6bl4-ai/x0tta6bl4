# SPIFFE/SPIRE Integration Guide

This guide explains how to use SPIFFE (Secure Production Identity Framework for Everyone) with x0tta6bl4 for zero-trust identity management.

## Overview

x0tta6bl4 includes full SPIFFE/SPIRE integration for:

- **Workload Identity**: X.509 and JWT SVIDs for service authentication
- **mTLS**: Automatic mutual TLS between services
- **Zero Trust**: Identity-based access control
- **Self-Healing**: MAPE-K loop integration for automatic credential renewal

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        x0tta6bl4 Mesh                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │   Node A     │     │   Node B     │     │   Node C     │     │
│  │              │     │              │     │              │     │
│  │ ┌──────────┐ │     │ ┌──────────┐ │     │ ┌──────────┐ │     │
│  │ │ SPIRE    │ │     │ │ SPIRE    │ │     │ │ SPIRE    │ │     │
│  │ │ Agent    │ │     │ │ Agent    │ │     │ │ Agent    │ │     │
│  │ └────┬─────┘ │     │ └────┬─────┘ │     │ └────┬─────┘ │     │
│  │      │       │     │      │       │     │      │       │     │
│  │ ┌────▼─────┐ │     │ ┌────▼─────┐ │     │ ┌────▼─────┐ │     │
│  │ │Workload  │ │     │ │Workload  │ │     │ │Workload  │ │     │
│  │ │(x0tta6bl4)│ │     │ │(x0tta6bl4)│ │     │ │(x0tta6bl4)│ │     │
│  │ └──────────┘ │     │ └──────────┘ │     │ └──────────┘ │     │
│  └──────────────┘     └──────────────┘     └──────────────┘     │
│         │                    │                    │              │
│         └────────────────────┼────────────────────┘              │
│                              │                                   │
│                    ┌─────────▼─────────┐                        │
│                    │   SPIRE Server    │                        │
│                    │   (HA Cluster)    │                        │
│                    └───────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker Compose (Development)

```bash
# Start SPIRE Server and Agent
cd deployment/spire
docker compose up -d

# Wait for SPIRE to be ready
docker compose logs -f spire-server

# Create workload entry
docker exec -it spire-server spire-server entry create \
  -spiffeID spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node \
  -parentID spiffe://x0tta6bl4.mesh/spire/agent/docker \
  -selector docker:label:app:x0tta6bl4-node
```

### Kubernetes (Production)

```bash
# Deploy SPIRE using Helm
cd deployment/spire/helm
helm install spire . --namespace spire-system --create-namespace

# Verify deployment
kubectl get pods -n spire-system

# Create workload entry
kubectl exec -n spire-system spire-server-0 -- spire-server entry create \
  -spiffeID spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node \
  -parentID spiffe://x0tta6bl4.mesh/spire/agent/k8s/psat/node_name \
  -selector k8s:ns:x0tta6bl4 \
  -selector k8s:sa:x0tta6bl4-node
```

## Usage

### Fetching SVIDs

```python
from src.security.spiffe.workload.api_client import WorkloadAPIClient

# Initialize client (uses SPIFFE_ENDPOINT_SOCKET env var)
client = WorkloadAPIClient()

# Fetch X.509 SVID
x509_svid = client.fetch_x509_svid()
print(f"SPIFFE ID: {x509_svid.spiffe_id}")
print(f"Expires: {x509_svid.expiry}")

# Fetch JWT SVID
jwt_svid = client.fetch_jwt_svid(audience=["my-service"])
print(f"Token: {jwt_svid.token}")
```

### mTLS with SPIFFE

```python
from src.security.spiffe.mtls.tls_context import build_mtls_context
from src.security.spiffe.workload.api_client import WorkloadAPIClient

# Get SVID
client = WorkloadAPIClient()
svid = client.fetch_x509_svid()

# Build mTLS context
mtls_ctx = build_mtls_context(svid)

# Use with HTTP client
import httpx
async with httpx.AsyncClient(verify=mtls_ctx.ssl_context) as http:
    response = await http.get("https://secure-service/metrics")
```

### Zero Trust Validation

```python
from src.security.zero_trust.validator import ZeroTrustValidator

validator = ZeroTrustValidator(trust_domain="x0tta6bl4.mesh")

# Validate peer connection
is_valid = validator.validate_connection(
    peer_spiffe_id="spiffe://x0tta6bl4.mesh/workload/api-server",
    peer_svid=peer_svid
)

if is_valid:
    print("✅ Peer identity verified")
else:
    print("❌ Peer identity rejected")
```

### Auto-Renewal Service

```python
from src.security.spiffe.workload.auto_renew import create_auto_renew
from src.security.spiffe.workload.api_client import WorkloadAPIClient

client = WorkloadAPIClient()
auto_renew = create_auto_renew(client, renewal_threshold=0.5)

# Start auto-renewal (runs in background)
await auto_renew.start()

# SVIDs are automatically renewed before expiry
# ...

# Stop when done
await auto_renew.stop()
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SPIFFE_ENDPOINT_SOCKET` | Path to SPIRE Agent socket | `/run/spire/sockets/agent.sock` |
| `SPIFFE_TRUST_BUNDLE_PATH` | Path to trust bundle | - |
| `X0TTA6BL4_PRODUCTION` | Enable production mode | `false` |
| `X0TTA6BL4_FORCE_MOCK_SPIFFE` | Force mock mode (dev only) | `false` |
| `X0TTA6BL4_SPIRE_JOIN_TOKEN` | Join token for node attestation | - |

### SPIRE Server Configuration

See [`deployment/spire/config/server.conf`](deployment/spire/config/server.conf):

- Trust domain: `x0tta6bl4.mesh`
- Default SVID TTL: 1 hour
- Data store: SQLite (dev) / PostgreSQL (prod)
- Node attestation: Join token (dev) / K8s PSAT (prod)

### SPIRE Agent Configuration

See [`deployment/spire/config/agent.conf`](deployment/spire/config/agent.conf):

- Socket path: `/run/spire/sockets/agent.sock`
- Workload attestors: Unix, Docker, Kubernetes

## Security Best Practices

### 1. Production Mode

Always enable production mode in production deployments:

```bash
export X0TTA6BL4_PRODUCTION=true
```

This enforces:
- Real SPIRE Agent connection required
- Mock mode disabled
- Strict certificate validation

### 2. Trust Domain

Use a consistent trust domain across all nodes:

```python
# Good
trust_domain = "x0tta6bl4.mesh"

# Bad - different trust domains will reject each other
trust_domain = "production.x0tta6bl4.mesh"  # Different from dev
```

### 3. SVID TTL

Balance security and performance:

```python
# High security (short TTL)
svid_ttl = "5m"  # 5 minutes

# Balanced (recommended)
svid_ttl = "1h"  # 1 hour

# Low overhead (long TTL)
svid_ttl = "24h"  # 24 hours
```

### 4. mTLS Enforcement

Enable mTLS for all inter-service communication:

```python
from src.security.mesh_mtls_enforcer import MeshMTLSEnforcer

enforcer = MeshMTLSEnforcer(
    trust_domain="x0tta6bl4.mesh",
    enforce_tls13=True,  # Require TLS 1.3
    verify_svid=True,    # Verify peer SPIFFE ID
)
```

## Troubleshooting

### SPIRE Agent Not Found

```
Error: SPIFFE endpoint socket not configured
```

**Solution**: Set the socket path:

```bash
export SPIFFE_ENDPOINT_SOCKET=/run/spire/sockets/agent.sock
```

### SVID Fetch Failed

```
Error: Failed to fetch X.509 SVID via SPIFFE SDK
```

**Solutions**:

1. Check SPIRE Agent is running:
   ```bash
   docker compose -f deployment/spire/docker-compose.yml ps
   ```

2. Check workload entry exists:
   ```bash
   docker exec -it spire-server spire-server entry show
   ```

3. Check agent socket:
   ```bash
   ls -la /run/spire/sockets/agent.sock
   ```

### Certificate Validation Failed

```
Error: Peer SVID validation failed
```

**Solutions**:

1. Verify trust domain matches
2. Check SVID is not expired
3. Verify certificate chain

## Monitoring

### Prometheus Metrics

SPIFFE integration exposes the following metrics:

| Metric | Description |
|--------|-------------|
| `spiffe_svid_x509_expiry_timestamp_seconds` | X.509 SVID expiry time |
| `spiffe_svid_jwt_expiry_timestamp_seconds` | JWT SVID expiry time |
| `spiffe_auto_renew_success_total` | Successful renewals |
| `spiffe_auto_renew_failure_total` | Failed renewals |

### Grafana Dashboard

Import the SPIRE dashboard from `deployment/grafana_dashboards/spire.json`.

## References

- [SPIFFE Specification](https://spiffe.io/)
- [SPIRE Documentation](https://spiffe.io/docs/latest/spire-about/)
- [x0tta6bl4 Security Architecture](docs/SECURITY_ARCHITECTURE.md)
