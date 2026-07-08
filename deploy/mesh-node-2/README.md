# Second Mesh Node — Active-Passive Architecture

## Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACTIVE-PASSIVE MESH                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [NL VPS 89.125.1.107] ←── ACTIVE ──→ [SPB/SECOND VPS]        │
│    ├── SPIRE Server          SPIRE Agent ←──                    │
│    ├── SPIRE Agent                                         │
│    ├── Mesh Node (9100)     Mesh Node (9100)                  │
│    ├── Ghost VPN (4434)     Ghost VPN (4434)                  │
│    └── x-ui/xray (443)      └── x-ui/xray (443)              │
│                                                                  │
│  Failover: NL down → SPB takes over mesh routing               │
│  SPIRE: NL = upstream authority, SPB = downstream agent        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### NL VPS (Primary)
- SPIRE Server (trust domain root)
- SPIRE Agent
- Mesh Node (port 9100)
- Ghost VPN (port 4434)
- x-ui/xray (port 443)

### Second VPS (Standby)
- SPIRE Agent (connects to NL SPIRE Server)
- Mesh Node (port 9100)
- Ghost VPN (port 4434)
- x-ui/xray (port 443)

## Failover Strategy

1. **Health monitoring**: Each node monitors the other via mesh protocol
2. **Heartbeat**: Every 30 seconds, nodes exchange heartbeat
3. **Failover trigger**: If NL unreachable for >60 seconds, SPB becomes active
4. **State replication**: SQLite WAL replication for SPIRE datastore
5. **DNS failover**: Optional DNS round-robin or health-check based

## SPIRE Federation

- NL: SPIRE Server (upstream authority)
- SPB: SPIRE Agent (connects to NL)
- Trust domain: `x0tta6bl4.mesh`
- Federation endpoint: port 8443 on NL

## Deployment

### Prerequisites
1. VPS with Ubuntu 22.04+
2. Docker installed
3. SSH access from NL to SPB
4. Firewall: ports 8081, 8443, 9100, 4434, 443

### Steps
1. Deploy SPIRE Agent on SPB
2. Register SPB node in SPIRE Server (NL)
3. Deploy mesh node on SPB
4. Configure peer discovery
5. Test failover
