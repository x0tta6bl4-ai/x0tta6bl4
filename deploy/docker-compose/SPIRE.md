# SPIRE Integration — Local Mesh with SPIFFE Identity

## Prerequisites
- Docker + Docker Compose
- Network access to GitHub (for SPIRE binary download during build)

## Quick Start

```bash
cd /mnt/projects

# 1. Build mesh-node image (already done)
docker build --no-cache -t mesh-node:latest -f deploy/docker-compose/Dockerfile.mesh .

# 2. Build SPIRE images
docker compose -f deploy/docker-compose/compose.spire.yaml build

# 3. Generate join token and update agent config
docker compose -f deploy/docker-compose/compose.spire.yaml up -d spire-server
sleep 3
TOKEN=$(docker exec spire-server spire-server token generate \
  -spiffeID spiffe://x0tta6bl4.mesh/node/local-node)
echo "Token: $TOKEN"
# Update spire-agent.conf with the token, then rebuild agent

# 4. Start full stack
docker compose -f deploy/docker-compose/compose.spire.yaml up -d
```

## Architecture

```
spire-server:8081
    ↓ join_token
spire-agent → Workload API socket (/tmp/spire-agent/api.sock)
    ↓ SVID
mesh-node-a:9100 ←→ mesh-node-b:9101 (SVID-signed PBFT)
```

## SPIRE Workflow

1. `spire-server` starts → listens on :8081
2. Admin generates join token: `spire-server token generate -spiffeID ...`
3. `spire-agent` connects with join_token → receives SVID
4. Workloads (mesh-node) connect to Workload API via Unix socket
5. `SVIDSigner(mode="prod")` fetches JWT-SVID from SPIRE agent
6. PBFT messages signed with JWT-SVID → verified by peers

## Proxy Note

If behind SOCKS5 proxy (v2rayN :10818), Docker build may fail to download SPIRE.
Workaround: pre-download SPIRE tarball, mount as volume, or build on direct connection.
