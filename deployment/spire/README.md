# SPIRE Deployment for x0tta6bl4

This directory contains deployment configurations for SPIRE (SPIFFE Runtime Environment).

## Quick Start

```bash
# Docker Compose (Development)
./quickstart.sh docker

# Kubernetes (Production)
./quickstart.sh k8s
```

## Directory Structure

```
deployment/spire/
├── docker-compose.yml      # Docker Compose configuration
├── quickstart.sh           # Quick start script
├── config/
│   ├── server.conf         # SPIRE Server configuration
│   └── agent.conf          # SPIRE Agent configuration
└── helm/
    └── spire/              # Helm chart for Kubernetes
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
            ├── server.yaml
            ├── agent.yaml
            ├── rbac.yaml
            └── _helpers.tpl
```

## Docker Compose

### Start SPIRE

```bash
docker compose up -d
```

### Check Status

```bash
docker compose ps
docker compose logs -f spire-server
```

### Create Workload Entry

```bash
# Generate join token
JOIN_TOKEN=$(docker exec spire-server spire-server token generate \
  -spiffeID spiffe://x0tta6bl4.mesh/spire/agent/docker \
  2>/dev/null | awk '{print $2}')

# Create entry for workload
docker exec spire-server spire-server entry create \
  -spiffeID spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node \
  -parentID spiffe://x0tta6bl4.mesh/spire/agent/docker \
  -selector docker:label:app:x0tta6bl4-node
```

### Verify SVID

```bash
# Check agent socket
docker exec spire-agent ls -la /run/spire/sockets/

# Test workload API (requires spiffe tool)
docker exec spire-agent spiffe-helper -config /dev/null
```

## Kubernetes

### Prerequisites

- Kubernetes cluster 1.24+
- Helm 3.0+
- kubectl configured

### Deploy

```bash
# Create namespace
kubectl create namespace spire-system

# Deploy with Helm
helm install spire ./helm/spire \
  --namespace spire-system \
  --set global.trustDomain=x0tta6bl4.mesh

# Verify
kubectl get pods -n spire-system
```

### Create Workload Entry

```bash
# Get node name
NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')

# Create entry
kubectl exec -n spire-system spire-server-0 -- \
  spire-server entry create \
  -spiffeID spiffe://x0tta6bl4.mesh/workload/x0tta6bl4-node \
  -parentID spiffe://x0tta6bl4.mesh/spire/agent/k8s/psat/$NODE_NAME \
  -selector k8s:ns:x0tta6bl4 \
  -selector k8s:sa:x0tta6bl4-node
```

### Configure Workload

Mount the SPIRE Agent socket to your workload:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: x0tta6bl4-node
  namespace: x0tta6bl4
spec:
  template:
    spec:
      containers:
        - name: app
          volumeMounts:
            - name: spire-socket
              mountPath: /run/spire/sockets
              readOnly: true
          env:
            - name: SPIFFE_ENDPOINT_SOCKET
              value: unix:///run/spire/sockets/agent.sock
      volumes:
        - name: spire-socket
          hostPath:
            path: /run/spire/sockets
            type: Directory
```

## Configuration

### Trust Domain

Default: `x0tta6bl4.mesh`

Change in:
- `config/server.conf`: `trust_domain`
- `config/agent.conf`: `trust_domain`
- Helm: `--set global.trustDomain=your.domain`

### SVID TTL

Default: 1 hour

Change in `config/server.conf`:
```
server {
    default_svid_ttl = "24h"
}
```

### Data Store

Development: SQLite
Production: PostgreSQL

For PostgreSQL, update `config/server.conf`:
```
plugins {
    DataStore "sql" {
        plugin_data {
            database_type = "postgres"
            connection_string = "postgres://user:pass@postgres:5432/spire?sslmode=disable"
        }
    }
}
```

## Troubleshooting

### SPIRE Server won't start

1. Check logs: `docker compose logs spire-server`
2. Verify data directory permissions
3. Check port 8081 is not in use

### SPIRE Agent won't connect

1. Verify server is running
2. Check join token is valid
3. Verify network connectivity

### Workload can't get SVID

1. Check entry exists: `spire-server entry show`
2. Verify workload selectors match
3. Check socket permissions: `ls -la /run/spire/sockets/`

## References

- [SPIRE Documentation](https://spiffe.io/docs/latest/spire-about/)
- [SPIFFE Specification](https://spiffe.io/)
- [x0tta6bl4 SPIFFE Integration](../../docs/SPIFFE_INTEGRATION.md)
