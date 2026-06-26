# SPIRE Cross-Trust Federation — x0tta6bl4 Mesh

## Current Architecture

```
NL SPIRE (89.125.1.107:8081, bundle endpoint :10443)
  trust_domain = x0tta6bl4.mesh
  ├─ nl-node-1 (join_token, :9100) → SVD_BYPASS=true
  └─ nl-node-2 (join_token, :9101) → SVD_BYPASS=true

Docker SPIRE (localhost:8081)
  trust_domain = x0tta6bl4.mesh
  ├─ local-node (join_token)
  ├─ node-a (:9100) → SVD_BYPASS=true
  ├─ node-b (:9101) → SVD_BYPASS=true
  └─ node-nl-bridge (:9102) → SVD_BYPASS=true
```

## SVD_BYPASS

All mesh nodes currently run with `SVD_BYPASS=true`. This means SVID
verification failures are logged but NOT blocking. Reason: Docker SPIRE
and NL SPIRE are independent CAs in the same trust domain. Cross-SPIRE
consensus messages fail SVID verification because each side's CA
signed different root keys.

Without bypass: HTTP 403 → peer unreachable → no consensus.
With bypass: consensus proceeds (anomaly data evaluated on content,
not on signature).

## Production Path (remove bypass)

### Prerequisites
- NL SPIRE server: bind 0.0.0.0:8081 ✅, bundle endpoint :10443 ✅
- Docker SPIRE server: needs UpstreamAuthority pointing to NL SPIRE

### Steps to remove bypass
1. Generate join token on NL SPIRE (done: `docker-downstream` SVID)
2. Run `spire-agent` sidecar in Docker that connects to 89.125.1.107:8081
3. Mount agent socket to Docker SPIRE server
4. Configure Docker SPIRE server with:
   ```
   UpstreamAuthority "spire" {
       plugin_data {
           server_address = "89.125.1.107"
           server_port = "8081"
       }
   }
   ```
5. Restart Docker SPIRE server → it gets CA chain from NL
6. All nodes get SVID from same hierarchy → full verification
7. Set SVD_BYPASS=false on all nodes

### Docker compose service (ready, needs .env with token)
```yaml
  spire-agent-nl:
    image: spire-agent:latest
    container_name: spire-agent-nl
    hostname: spire-agent-nl
    environment:
      - SPIRE_SERVER_ADDRESS=89.125.1.107
      - SPIRE_SERVER_PORT=8081
      - JOIN_TOKEN=${NL_JOIN_TOKEN}
    volumes:
      - spire-socket-nl:/tmp/spire-agent
    networks:
      mesh-net:
        aliases:
          - spire-agent-nl
    restart: always
```
