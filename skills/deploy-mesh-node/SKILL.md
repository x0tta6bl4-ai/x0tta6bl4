---
name: deploy-mesh-node
description: >
  Step-by-step deployment of x0tta6bl4 mesh nodes to Docker or Kubernetes.
  Use when user says "deploy node", "add mesh node", "scale cluster",
  "deploy to k8s", "docker deploy", or "onboard new node".
  Covers Docker Compose, Kubernetes, and local development setups.
metadata:
  author: x0tta6bl4
  version: 1.0.0
  category: deployment
  tags: [mesh, deployment, docker, kubernetes]
---

# Deploy Mesh Node

## Instructions

### Step 1: Determine Deployment Target

Ask the user which deployment target they need:
- **Docker Compose** (development/staging)
- **Kubernetes** (production)
- **Local** (development only)

### Step 2: Pre-flight Checks

Before deploying, verify prerequisites:

```bash
# Docker target
docker --version && docker-compose --version

# Kubernetes target
kubectl cluster-info && kubectl get nodes

# Local target
python3 --version && pip install -r requirements-core.txt
```

Verify environment configuration:
```bash
# Check .env exists and has required vars
test -f .env || cp .env.example .env
```

Required environment variables:
- `X0TTA6BL4_NODE_ID` - unique node identifier
- `X0TTA6BL4_SPIFFE` - SPIFFE identity mode (true/false)
- `YGGDRASIL_PEERS` - comma-separated peer addresses
- `DATABASE_URL` - PostgreSQL connection string

### Step 3: Deploy

#### Docker Compose
```bash
# Minimal (testing)
docker-compose -f docker-compose.minimal.yml up -d

# Staging
docker-compose -f docker-compose.staging.yml up -d

# Production
docker-compose up -d
```

#### Kubernetes
```bash
# Apply namespace
kubectl apply -f deploy/k8s/namespace.yaml

# Apply all manifests via Kustomize
kubectl apply -k deploy/k8s/

# Verify pods are running
kubectl get pods -n x0tta6bl4
```

#### Local
```bash
pip install -r requirements-core.txt
alembic upgrade head
uvicorn src.core.app:app --host 0.0.0.0 --port 8080
```

### Step 4: Post-deploy Verification

```bash
# Health check
curl -s http://localhost:8080/health | python3 -m json.tool

# Mesh connectivity
curl -s http://localhost:8080/api/v1/mesh/status

# Run post-deploy tests
pytest tests/integration/ -m "not slow" -v --tb=short
```

Expected health response:
```json
{"status": "healthy", "version": "3.2.0", "uptime": "..."}
```

### Step 5: Register Node in Mesh

After the node is healthy:
1. It auto-registers via Yggdrasil peer discovery
2. SPIFFE identity is issued by the SPIRE server
3. MAPE-K loop begins monitoring

Verify mesh membership:
```bash
curl -s http://localhost:8080/api/v1/mesh/peers
```

## Troubleshooting

### Error: Database connection refused
Cause: PostgreSQL not running or wrong DATABASE_URL
Solution: Check `docker-compose ps` for db service, verify DATABASE_URL in .env

### Error: SPIFFE workload API unavailable
Cause: SPIRE agent not running
Solution: Set `X0TTA6BL4_SPIFFE=false` for development, or start SPIRE agent

### Error: Yggdrasil peers unreachable
Cause: No peers configured or firewall blocking port 443
Solution: Add at least one public peer to YGGDRASIL_PEERS in .env

## Rollback

If deployment fails:
```bash
# Docker
docker-compose down && docker-compose up -d --force-recreate

# Kubernetes
kubectl rollout undo deployment/proxy-api -n x0tta6bl4
```
