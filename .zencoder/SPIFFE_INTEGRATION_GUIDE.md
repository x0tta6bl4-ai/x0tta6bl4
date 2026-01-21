# SPIFFE/SPIRE Integration Guide for x0tta6bl4

**Status**: ✅ Ready for Development | Production Testing Required  
**Version**: P0 #1 Implementation  
**Last Updated**: January 13, 2026

---

## Quick Start (5 minutes)

### 1. Start SPIRE Server & Agent with Docker Compose

```bash
# From project root
docker-compose -f docker-compose.spire.yml up -d

# Wait for services to be healthy
docker-compose -f docker-compose.spire.yml ps

# Should show:
# CONTAINER ID  IMAGE                  STATUS
# spire-server  spire-server:1.8.5    healthy
# spire-agent   spire-agent:1.8.5     healthy
```

### 2. Verify SPIRE is Running

```bash
# Check server health
docker exec spire-server /opt/spire/bin/spire-server healthcheck

# Check agent health
docker exec spire-agent /opt/spire/bin/spire-agent healthcheck -socketPath /run/spire/sockets/agent.sock

# List registered workloads
docker exec spire-server /opt/spire/bin/spire-server entry list \
  -registrationUDS /var/lib/spire/sockets/registration.sock
```

### 3. Enable SPIFFE in x0tta6bl4

Set environment variable:
```bash
export SPIFFE_ENABLED=true
export SPIFFE_ENDPOINT_SOCKET=/run/spire/sockets/agent.sock  # If using local agent
```

Or in `.env`:
```env
SPIFFE_ENABLED=true
SPIFFE_ENDPOINT_SOCKET=/run/spire/sockets/agent.sock
```

### 4. Start x0tta6bl4 with SPIFFE

```bash
# With SPIFFE enabled
python -m src.core.app

# Should log:
# 🔐 Initializing SPIFFE/SPIRE for Zero Trust security...
# ✅ SPIFFE/mTLS initialized - Zero Trust enabled, Auto-Renew started
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           x0tta6bl4 Application (Port 8080)                 │
│  ┌─────────────────────────────────────────────────────────┐
│  │  FastAPI with SPIFFE/SPIRE Integration                  │
│  │  - Workload Identity (SVID)                             │
│  │  - mTLS for service-to-service communication            │
│  │  - Automatic credential rotation (every 50% TTL)        │
│  │  - Zero-Trust policy enforcement                        │
│  └─────────────────────────────────────────────────────────┘
│         ↑                                    ↑
│         │ SVID Request                      │ mTLS Cert Validation
│         ↓                                    ↓
├─────────────────────────────────────────────────────────────┤
│          SPIRE Agent (Port 8082)                            │
│  ┌─────────────────────────────────────────────────────────┐
│  │  Workload API (/run/spire/sockets/agent.sock)           │
│  │  - Unix socket for local process access                 │
│  │  - Docker workload attestation                          │
│  │  - Kubernetes pod attestation                           │
│  └─────────────────────────────────────────────────────────┘
│         ↑
│         │ SVID Fetch/Renew
│         ↓
├─────────────────────────────────────────────────────────────┤
│        SPIRE Server (Port 8081)                             │
│  ┌─────────────────────────────────────────────────────────┐
│  │  Registration & Certificate Authority                  │
│  │  - Issue SVIDs (valid for 1 hour)                       │
│  │  - Store workload identity mappings                     │
│  │  - Manage trust bundles                                 │
│  └─────────────────────────────────────────────────────────┘
│         ↑
│         │ Node & Workload Registration
│         ↓
├─────────────────────────────────────────────────────────────┤
│   Registration (Initial Setup)                              │
│  - Agent joins with token                                   │
│  - Workloads registered via registration.sock              │
│  - Trust domain: x0tta6bl4.mesh                             │
└─────────────────────────────────────────────────────────────┘
```

---

## SPIFFE/SPIRE Components

### SPIRE Server (`spire-server:1.8.5`)
- **Role**: Certificate Authority for SVIDs
- **Configuration**: `infra/spire/server/server.conf`
- **Port**: 8081 (Agent API)
- **Socket**: `/var/lib/spire/sockets/registration.sock` (Registration)
- **Storage**: SQLite by default (can switch to PostgreSQL)

**Key Settings**:
- Trust Domain: `x0tta6bl4.mesh`
- SVID TTL: 3600s (1 hour)
- Node Attestors: join_token, aws_iid, k8s_sat
- Workload Attestors: unix, docker, k8s

### SPIRE Agent (`spire-agent:1.8.5`)
- **Role**: Local workload identity provider
- **Configuration**: `infra/spire/agent/agent.conf`
- **Socket**: `/run/spire/sockets/agent.sock` (Workload API)
- **Port**: 8088 (Prometheus metrics)

**Key Settings**:
- Server Address: `spire-server:8081`
- Socket Permissions: 0755 (read for all, write for spire)
- SVID Check Interval: 10s (rotation check)
- Sync Interval: 30s (keep-alive with server)

### Registration Service
Automatically registers x0tta6bl4 workloads:
- Core services: `/service/api`, `/service/mesh-node`, `/service/mape-k`
- Network services: `/network/batman`, `/network/ebpf`, `/network/discovery`
- Security services: `/security/policy-engine`, `/security/threat-detection`
- ML services: `/ml/graphsage`, `/ml/rag-engine`, `/ml/anomaly-detector`
- DAO services: `/dao/governance`, `/dao/token-bridge`, `/dao/voting`

---

## Workload Registration

### Automatic Registration (on Docker startup)

The `spire-registration` service automatically registers workloads on container startup.

View registered entries:
```bash
docker exec spire-server /opt/spire/bin/spire-server entry list \
  -registrationUDS /var/lib/spire/sockets/registration.sock
```

Example output:
```
Found 18 entries:

Entry ID       : a1b2c3d4-e5f6-7890
SPIFFE ID      : spiffe://x0tta6bl4.mesh/service/api
Parent ID      : spiffe://x0tta6bl4.mesh/agent/docker/agent
Selectors      : unix:uid:0
TTL            : 3600
Expires At     : 2026-01-13 15:30:00
```

### Manual Registration

Register a specific workload:
```bash
docker exec spire-server /opt/spire/bin/spire-server entry create \
  -registrationUDS /var/lib/spire/sockets/registration.sock \
  -spiffeID spiffe://x0tta6bl4.mesh/service/custom \
  -selector unix:uid:0 \
  -ttl 3600
```

---

## Integration with x0tta6bl4

### In Application Code

```python
from src.security.spiffe.controller import SPIFFEController
from src.security.spiffe.workload import WorkloadAPIClientProduction
from src.security.spiffe.mtls import MTLSControllerProduction

# Initialize on startup
spiffe_controller = SPIFFEController(trust_domain="x0tta6bl4.mesh")
workload_api = WorkloadAPIClientProduction()
mtls_controller = MTLSControllerProduction(workload_api_client=workload_api)

# Get my identity
svid = workload_api.fetch_x509_svid()
print(f"My SPIFFE ID: {svid.spiffe_id}")

# Automatic renewal (happens in background)
# SVID renewed at 50% TTL (30 minutes for 1h TTL)
```

### In FastAPI Routes

```python
from fastapi import Depends, Header

async def verify_peer_spiffe_id(x_spiffe_id: str = Header(None)):
    """Verify peer identity from mTLS certificate"""
    if not x_spiffe_id:
        raise HTTPException(status_code=401, detail="Not authenticated via SPIFFE")
    return x_spiffe_id

@app.get("/api/secure")
async def secure_endpoint(spiffe_id: str = Depends(verify_peer_spiffe_id)):
    return {"peer": spiffe_id}
```

### mTLS HTTP Client

```python
from src.security.spiffe.mtls import MTLSControllerProduction

mtls_controller = MTLSControllerProduction(workload_api_client=workload_api)
mtls_context = mtls_controller.build_mtls_context()

# Use with httpx for mTLS requests
async with httpx.AsyncClient(
    verify=mtls_context.ca_certs_path,
    cert=(mtls_context.cert_path, mtls_context.key_path)
) as client:
    response = await client.get("https://peer-service.mesh/api/data")
```

---

## Testing SPIFFE Integration

### Unit Tests

```bash
# Run SPIFFE-specific tests
pytest tests/unit/spiffe/ -v

# Test SVID issuance
pytest tests/unit/spiffe/test_workload_api.py -v

# Test auto-renewal
pytest tests/unit/spiffe/test_auto_renewal.py -v
```

### Integration Tests

```bash
# Test with running SPIRE Server & Agent
pytest tests/integration/spiffe/ -v

# Test mTLS between services
pytest tests/integration/test_mtls_integration.py -v
```

### Manual Verification

```bash
# 1. Check agent socket
ls -la /run/spire/sockets/agent.sock

# 2. Fetch SVID (if spiffe CLI available)
spiffe-helper \
  -outputCert /tmp/cert.pem \
  -outputPrivateKey /tmp/key.pem \
  -cmd "cat /tmp/cert.pem"

# 3. Check certificate details
openssl x509 -in /tmp/cert.pem -text -noout | grep -E "Subject|Issuer|Not Before|Not After"
```

---

## Troubleshooting

### SPIRE Agent Socket Not Found

**Error**: `FileNotFoundError: /run/spire/sockets/agent.sock`

**Solution**:
```bash
# Check if Docker container is running
docker ps | grep spire-agent

# Check socket exists in container
docker exec spire-agent ls -la /run/spire/sockets/

# Verify mount in docker-compose.spire.yml
grep -A 5 "volumes:" docker-compose.spire.yml | grep spire-agent
```

### SPIRE Agent Not Attesting Workload

**Error**: `ERROR fetching SVID: workload not found`

**Solution**:
```bash
# Check registration
docker exec spire-server /opt/spire/bin/spire-server entry list \
  -registrationUDS /var/lib/spire/sockets/registration.sock

# Check agent logs
docker logs spire-agent | tail -50 | grep -i "selector\|attest\|error"

# Re-register workload
bash infra/spire/register-workloads.sh
```

### SVID Expired

**Error**: `Certificate has expired`

**Solution**:
```bash
# Auto-renewal should handle this automatically
# Check if SPIFFEAutoRenew is running
ps aux | grep SPIFFEAutoRenew

# Manual renewal (in app code)
svid = workload_api.fetch_x509_svid()
if svid.is_expired():
    # Automatically fetches fresh SVID
    svid = workload_api.fetch_x509_svid()
```

### SPIRE Server Not Responding

**Error**: `Connection refused on spire-server:8081`

**Solution**:
```bash
# Check if server is healthy
docker exec spire-server /opt/spire/bin/spire-server healthcheck

# Check logs
docker logs spire-server | tail -50

# Restart both services
docker-compose -f docker-compose.spire.yml restart

# Check port binding
netstat -tuln | grep 8081  # Local machine
docker port spire-server | grep 8081  # If in container
```

---

## Configuration Reference

### Environment Variables

```bash
# Enable/disable SPIFFE
export SPIFFE_ENABLED=true

# Workload API socket path
export SPIFFE_ENDPOINT_SOCKET=/run/spire/sockets/agent.sock

# Trust bundle path (optional)
export SPIFFE_TRUST_BUNDLE_PATH=/etc/spiffe/trust-bundle.pem

# SVID TTL (server-side, in seconds)
export SPIFFE_SVID_TTL=3600

# Renewal check interval (in seconds)
export SPIFFE_RENEWAL_CHECK_INTERVAL=10
```

### Docker Compose Override

To customize SPIRE settings without modifying `docker-compose.spire.yml`:

```bash
# Create docker-compose.override.yml
cat > docker-compose.override.yml <<EOF
version: '3.8'
services:
  spire-server:
    environment:
      SPIRE_LOG_LEVEL: DEBUG
  spire-agent:
    environment:
      SPIRE_LOG_LEVEL: DEBUG
EOF

# Apply on startup
docker-compose -f docker-compose.spire.yml -f docker-compose.override.yml up -d
```

---

## Production Deployment

### Pre-Production Checklist

- [ ] SPIRE Server uses persistent storage (PostgreSQL recommended)
- [ ] SPIRE Server binds to trusted network only (not 0.0.0.0)
- [ ] KeyManager uses disk with encrypted keys (not memory)
- [ ] Trust bundle rotation configured (weekly or monthly)
- [ ] UpstreamCA configured with proper PKI
- [ ] Node attestation uses production method (AWS IID, K8s PSAT, etc.)
- [ ] Workload attestation strict (Docker + Unix for host, K8s for cluster)
- [ ] mTLS TLS 1.3 enforced
- [ ] SPIFFE auto-renewal tested under load
- [ ] Monitoring and alerting configured

### K8s Deployment

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: x0tta6bl4-spiffe
spec:
  serviceAccountName: x0tta6bl4
  containers:
  - name: app
    image: x0tta6bl4:3.3.0
    env:
    - name: SPIFFE_ENABLED
      value: "true"
    - name: SPIFFE_ENDPOINT_SOCKET
      value: /run/spire/sockets/agent.sock
    volumeMounts:
    - name: spiffe-workload-api
      mountPath: /run/spire/sockets
  volumes:
  - name: spiffe-workload-api
    hostPath:
      path: /run/spire/sockets
```

---

## References

- [SPIFFE Specification](https://github.com/spiffe/spiffe)
- [SPIRE Documentation](https://spiffe.io/docs/latest/spire/)
- [SPIRE Source Code](https://github.com/spiffe/spire)
- [Workload API Standard](https://github.com/spiffe/spiffe/blob/main/standards/SPIFFE_Workload_API.md)
- [SPIFFE Best Practices](https://spiffe.io/docs/latest/best-practices/)

---

## Support

For issues or questions:

1. Check logs: `docker logs spire-server/agent`
2. Run tests: `pytest tests/unit/spiffe/ -v`
3. Check SPIRE health: `docker exec spire-server spire-server healthcheck`
4. Review socket permissions: `ls -la /run/spire/sockets/`

---

**Status**: ✅ Ready for use  
**Next Steps**: Integration testing, production hardening, Kubernetes deployment
