# x0tta6bl4 Helm Chart

Zero Trust Mesh Intelligence Platform with post-quantum security.

## Prerequisites

- Kubernetes 1.25+
- Helm 3.10+
- PV provisioner (for persistence)

## Installation

```bash
# Add repo (if published)
helm repo add x0tta6bl4 https://charts.x0tta6bl4.io

# Install with default values
helm install mesh x0tta6bl4/x0tta6bl4

# Install with custom values
helm install mesh x0tta6bl4/x0tta6bl4 -f my-values.yaml

# Install from local chart
helm install mesh ./infra/helm/x0tta6bl4
```

## Quick Start

```bash
# Minimal production deployment
helm install mesh ./infra/helm/x0tta6bl4 \
  --set mesh.replicaCount=3 \
  --set zeroTrust.enabled=true \
  --set prometheus.enabled=true \
  --set grafana.enabled=true
```

## Zero Trust Features

| Component | Description | Default |
|-----------|-------------|---------|
| ZKP Authentication | Schnorr/Pedersen zero-knowledge proofs | Enabled |
| Post-Quantum Crypto | NTRU hybrid encryption | Enabled |
| Device Attestation | Privacy-preserving device verification | Enabled |
| DIDs | Decentralized identity (W3C compliant) | Enabled |
| Policy Engine | ABAC with default-deny | Enabled |
| Continuous Verification | Adaptive session validation | Enabled |
| Auto-Isolation | Circuit breaker pattern | Enabled |
| Threat Intelligence | Distributed indicator sharing | Enabled |

## Configuration

### Core Settings

```yaml
mesh:
  replicaCount: 3
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
```

### Zero Trust

```yaml
zeroTrust:
  enabled: true
  
  zkp:
    algorithm: schnorr  # or pedersen
  
  postQuantum:
    algorithm: ntru-hybrid
    keyRotationDays: 30
  
  policyEngine:
    defaultEffect: deny
    cacheEnabled: true
```

### SPIFFE/SPIRE

```yaml
spiffe:
  enabled: true
  trustDomain: "your-domain.mesh"
```

### Anti-Censorship

```yaml
obfuscation:
  enabled: true
  defaultTransport: faketls
  
  faketls:
    sni: "www.google.com"
  
  shadowsocks:
    cipher: chacha20-poly1305
```

## Monitoring

```bash
# Port-forward Grafana
kubectl port-forward svc/mesh-grafana 3000:80

# Port-forward Prometheus
kubectl port-forward svc/mesh-prometheus 9090:9090
```

## Upgrade

```bash
helm upgrade mesh x0tta6bl4/x0tta6bl4 -f my-values.yaml
```

## Uninstall

```bash
helm uninstall mesh
```

## Values Reference

See [values.yaml](values.yaml) for all configurable options.

## Security Considerations

1. **Network Policies**: Enabled by default with Zero Trust
2. **Pod Security**: Non-root, read-only filesystem
3. **SPIFFE/SPIRE**: Recommended for production mTLS
4. **Secrets**: Use external secrets management (Vault, Sealed Secrets)

## License

MIT
