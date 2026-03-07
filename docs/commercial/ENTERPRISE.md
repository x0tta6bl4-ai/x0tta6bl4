# x0tta6bl4 MaaS — Enterprise Features

**Version:** v1.0.0 | 99.99% availability tier

---

## High Availability

| Component | Replicas | Strategy | Recovery |
|-----------|---------|---------|---------|
| API Gateway | 5 (min) | Anti-affinity across nodes | PDB minAvailable=3 |
| Redis | 3-node Sentinel | Leader election | Auto-failover < 10s |
| PostgreSQL | Primary + 2 replicas | Streaming replication | Switchover via Patroni |
| Mesh Nodes | DaemonSet (all nodes) | RollingUpdate maxUnavailable=1 | MAPE-K auto-heal |
| MCP Server | 2 | RollingUpdate | Stateless, instant restart |

**Target availability:** 98.5% SLA (99.99% with HA tier) — measured from simulated runs; not yet measured from production traffic

### Zero-Downtime Deployments
Blue-green slot switching with automated traffic cutover — see [release/v1.0.0.sh](../../release/v1.0.0.sh).

---

## Multi-Tenancy

Each tenant is fully isolated:

```
x0tta-production (control plane)
├── x0tta-alpha/           ← Tenant A namespace
│   ├── NetworkPolicy      ← deny cross-tenant traffic
│   ├── ResourceQuota      ← CPU/memory caps
│   ├── RBAC               ← per-tenant service accounts
│   └── MeshCluster CRD    ← tenant's mesh config
└── x0tta-beta/            ← Tenant B namespace
    └── ...
```

### Tenant Tiers

| Tier | Max Nodes | PQC Algorithm | Support SLA |
|------|----------|--------------|------------|
| Starter | 10 | Kyber-768 | 48h response |
| Business | 100 | Kyber-768 | 4h response |
| Enterprise | 500 | Kyber-1024 | 1h response + dedicated CSM |
| Dedicated | Unlimited | Kyber-1024 + Dilithium5 | 15min SRE hotline |

### Provisioning a Tenant

```bash
# Add tenant to values-enterprise.yaml and upgrade
helm upgrade x0tta oci://registry.gitlab.com/x0tta/charts/x0tta6bl4-commercial \
  --set "global.tenants[0].name=new-tenant" \
  --set "global.tenants[0].namespace=x0tta-new-tenant" \
  --set "global.tenants[0].tier=business" \
  --set "global.tenants[0].maxNodes=100" \
  --reuse-values
```

---

## Federation (Cross-DC)

Connect mesh clusters across data centers / clouds:

```yaml
# values-enterprise.yaml
global:
  federation:
    enabled: true
    relays:
      - id: relay-eu-west
        endpoint: relay.eu-west.x0tta6bl4.io:9000
        region: eu-west-1
      - id: relay-us-east
        endpoint: relay.us-east.x0tta6bl4.io:9000
        region: us-east-1
```

Bootstrap relays establish PQC-encrypted tunnels between clusters.
Federation topology is managed by the x0tta Operator (`MeshCluster` CRD).

### Cross-DC Topology Query
```
GET /mesh/topology?scope=global
→ Returns merged nodes/edges across all federated clusters
```

---

## SLA Guarantees

| Metric | Target | Measurement |
|--------|--------|------------|
| Uptime | 95% (Enterprise: 99.99%) | Monthly rolling |
| MTTR | < 2.5s (p95) | Prometheus `mesh_heal_duration_seconds` |
| API Latency | < 100ms p99 | `http_request_duration_seconds` |
| PQC Handshake | < 50ms p99 | `pqc_handshake_duration_seconds` |
| Throughput | 10+ Mbps | `mesh_bytes_forwarded_total` |

SLA breach credits are issued automatically via Stripe (annual contracts).

---

## External Database (Production)

x0tta6bl4 supports external managed databases — do **not** use bundled PostgreSQL in production:

```yaml
externalDatabase:
  host: pg.x0tta-prod.internal
  port: 5432
  database: x0tta_maas
  username: x0tta_app
  existingSecret: x0tta-db-secret
  sslMode: require
  poolMin: 5
  poolMax: 20
```

Required schema migrations run automatically on startup via Alembic.

---

## Monitoring & Alerting

Pre-configured PagerDuty integration:

```yaml
monitoring:
  pagerduty:
    enabled: true
    integrationKey: pd_XXXXXXXX   # from PagerDuty service
```

SLO dashboards are pre-loaded in Grafana:
- **Mesh Topology Overview** — node/edge counts, registration rate
- **SLA Metrics** — uptime, MTTR, throughput gauges with SLA lines
- **PQC Handshake Performance** — latency heatmap, failure rates
- **Self-Healing Events** — MAPE-K cycle duration, remediation history

---

## DAO Governance

Enterprise deployments include on-chain governance for:
- Component upgrade proposals (Snapshot vote → L2 execution)
- Parameter changes (key rotation intervals, quorum thresholds)
- Emergency actions (circuit-breaker, revoke node access)

```bash
# Submit an upgrade proposal via MCP agent
gemini-cli tool call propose_upgrade \
  --component api-gateway \
  --new_image_tag v1.1.0 \
  --title "Performance improvements" \
  --voting_period_hours 48
```
