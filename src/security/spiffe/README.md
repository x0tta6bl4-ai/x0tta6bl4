# SPIFFE/SPIRE Identity Module

Zero Trust identity management for x0tta6bl4 mesh network using SPIFFE/SPIRE.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  SPIFFE Controller                      │
│  (High-level orchestration & policy enforcement)       │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐   ┌──────▼───────┐
│ SPIRE Agent  │   │ Workload API │
│  (Manager)   │   │   (Client)   │
└──────────────┘   └──────────────┘
```

## Components

### 1. Workload API (`workload/`)
Client for SPIFFE Workload API to fetch SVIDs:
- **X.509 SVIDs**: mTLS certificate + private key
- **JWT SVIDs**: Token-based authentication
- Automatic credential rotation
- Peer validation

### 2. SPIRE Agent (`agent/`)
Manages SPIRE Agent lifecycle:
- Start/stop agent process
- Node attestation (join token, AWS IID, K8s PSAT)
- Workload registration
- Health monitoring

### 3. Controller (`controller/`)
High-level orchestration:
- Initialize SPIFFE infrastructure
- Provision workload identities
- Establish mTLS connections
- Trust domain management

## Quick Start

```python
from src.security.spiffe import SPIFFEController, AttestationStrategy

# Initialize controller
controller = SPIFFEController(trust_domain="x0tta6bl4.mesh")

# Bootstrap SPIFFE infrastructure
controller.initialize(
    attestation_strategy=AttestationStrategy.JOIN_TOKEN,
    token="your-join-token"
)

# Get workload identity
identity = controller.get_identity()
print(f"My SPIFFE ID: {identity.spiffe_id}")

# Establish mTLS connection
connection = controller.establish_mtls_connection(
    peer_spiffe_id="spiffe://x0tta6bl4.mesh/service/api"
)
```

## Configuration

SPIRE Agent expects configuration at:
- **Config**: `/etc/spire/agent/agent.conf`
- **Socket**: `/run/spire/sockets/agent.sock`
- **Server**: `127.0.0.1:8081`

Example `agent.conf`:
```hcl
agent {
    data_dir = "/var/lib/spire/agent"
    log_level = "DEBUG"
    server_address = "127.0.0.1"
    server_port = "8081"
    trust_domain = "x0tta6bl4.mesh"
}

plugins {
    NodeAttestor "join_token" {
        plugin_data {}
    }
    
    KeyManager "disk" {
        plugin_data {
            directory = "/var/lib/spire/agent/keys"
        }
    }
    
    WorkloadAttestor "unix" {
        plugin_data {}
    }
}
```

## Attestation Strategies

### Join Token (Development)
```python
controller.initialize(
    attestation_strategy=AttestationStrategy.JOIN_TOKEN,
    token="your-secret-token"
)
```

### AWS Instance Identity (Production)
```python
controller.initialize(
    attestation_strategy=AttestationStrategy.AWS_IID
)
```

### Kubernetes PSAT (K8s Deployments)
```python
controller.initialize(
    attestation_strategy=AttestationStrategy.K8S_PSAT
)
```

## mTLS Integration

SPIFFE provides automatic mTLS for mesh connections:

```python
# Server side
identity = controller.get_identity()
# Use identity.cert_chain and identity.private_key for TLS

# Client side
connection = controller.establish_mtls_connection(
    peer_spiffe_id="spiffe://x0tta6bl4.mesh/node/worker-2"
)
```

## Trust Domain Federation

Support for multiple trust domains (future):
```python
controller.federate_trust_domain(
    remote_domain="external.mesh",
    bundle_endpoint="https://external.mesh/bundle"
)
```

## References

- [SPIFFE Specification](https://github.com/spiffe/spiffe)
- [SPIRE Documentation](https://spiffe.io/docs/latest/spire/)
- [Workload API](https://github.com/spiffe/spiffe/blob/main/standards/SPIFFE_Workload_API.md)

## Status

**P0.2 Implementation Status:**
- ✅ Workload API Client (production-ready with gRPC)
- ✅ SPIRE Agent Manager (process management implemented)
- ✅ SPIFFE Controller (full orchestration)
- ✅ gRPC integration (via spiffe-python SDK)
- ✅ Process management (start/stop/health check)
- ✅ Certificate validation (X.509 and JWT SVID validation)
- ✅ Auto-renewal (SVID rotation with threshold)
- ✅ Unit tests (test_spiffe_auto_renew.py exists, see tests/README.md)

**Production Features:**
- ✅ Real gRPC connection to SPIRE Agent
- ✅ Automatic SVID renewal (50% TTL threshold)
- ✅ mTLS context building
- ✅ Peer certificate validation
- ✅ Process lifecycle management
- ✅ Health monitoring

**Requirements:**
1. SPIRE binaries installed (`spire-agent`, `spire-server`)
2. gRPC Python library (`grpcio`)
3. spiffe-python SDK (optional, but recommended)
