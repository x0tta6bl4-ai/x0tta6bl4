# Quick Start

Get x0tta6bl4 running in 5 minutes.

## Prerequisites

- Kubernetes cluster (v1.28+)
- Helm (v3.0+)
- kubectl configured

## Installation

### Option 1: Helm (Recommended)

```bash
# Add repository
helm repo add x0tta6bl4 https://x0tta6bl4.github.io/helm-charts

# Install
helm install my-mesh x0tta6bl4/mesh-node \
  --namespace mesh-system \
  --create-namespace
```

### Option 2: Docker

```bash
docker run -d -p 8080:8080 ghcr.io/x0tta6bl4/mesh-core:v3.0.0
```

### Option 3: Local Development

```bash
git clone https://github.com/x0tta6bl4/mesh-core.git
cd mesh-core
pip install -r requirements.txt
uvicorn src.core.app:app --reload
```

## Verify Installation

```bash
# Check pods
kubectl get pods -n mesh-system

# Health check
curl http://localhost:8080/health

# View metrics
curl http://localhost:9091/metrics
```

## Next Steps

- [Configuration Guide](configuration.md)
- [Architecture Overview](../architecture/overview.md)
- [API Reference](../api.md)
