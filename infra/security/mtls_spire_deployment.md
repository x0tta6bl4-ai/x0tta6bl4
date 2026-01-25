# mTLS + SPIFFE/SPIRE Deployment Architecture

**Stage 2: Zero-Trust Security (Недели 15-20)**  
**Цель**: Развёртывание mTLS + SPIFFE/SPIRE на всех узлах mesh сети

---

## 🏗️ Архитектура развёртывания

```
┌─────────────────────────────────────────────────────────────┐
│                    SPIRE Server Cluster                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ SPIRE Server (StatefulSet)                            │  │
│  │  - Trust Domain: x0tta6bl4.mesh                       │  │
│  │  - Node Attestation: k8s_psat, join_token            │  │
│  │  - Workload Attestation: k8s, unix                    │  │
│  │  - Prometheus metrics :9988                           │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Trust Bundle Distribution
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼────────┐              ┌───────▼────────┐
│ Mesh Node A    │              │ Mesh Node B    │
│                │              │                │
│ ┌───────────┐ │              │ ┌───────────┐ │
│ │SPIRE Agent│ │              │ │SPIRE Agent│ │
│ │(DaemonSet)│ │              │ │(DaemonSet)│ │
│ └─────┬─────┘ │              │ └─────┬─────┘ │
│       │       │              │       │       │
│ ┌─────▼─────┐ │              │ ┌─────▼─────┐ │
│ │Workload   │ │              │ │Workload   │ │
│ │API Socket │ │              │ │API Socket │ │
│ └─────┬─────┘ │              │ └─────┬─────┘ │
│       │       │              │       │       │
│ ┌─────▼─────┐ │              │ ┌─────▼─────┐ │
│ │Mesh       │◄┼──mTLS───────┼►│Mesh       │ │
│ │Service    │ │             │ │Service    │ │
│ │(x0tta6bl4)│ │             │ │(x0tta6bl4)│ │
│ └───────────┘ │             │ └───────────┘ │
└───────────────┘             └───────────────┘
```

---

## 📋 Компоненты развёртывания

### 1. SPIRE Server

**Роль**: Центральный орган выдачи идентичностей (CA)

**Конфигурация**:
- Trust Domain: `x0tta6bl4.mesh`
- Node Attestation: `k8s_psat`, `join_token` (для mesh nodes)
- Workload Attestation: `k8s`, `unix:uid`
- Datastore: SQLite (production: PostgreSQL)
- Key Manager: Disk (production: AWS KMS, HashiCorp Vault)

**Deployment**:
- Kubernetes StatefulSet
- Persistent Volume для CA keys
- Service для SPIRE Agent connections

### 2. SPIRE Agent (DaemonSet)

**Роль**: Локальный агент на каждом узле mesh

**Конфигурация**:
- Socket: `/tmp/spire-agent/public/api.sock`
- Workload API: Unix domain socket
- Node Attestation: `k8s_psat`, `join_token`
- Prometheus metrics: `:9989`

**Deployment**:
- Kubernetes DaemonSet (для k8s nodes)
- Systemd service (для bare-metal mesh nodes)

### 3. Mesh Node Integration

**Роль**: Интеграция SPIFFE с mesh networking

**Требования**:
- Каждый mesh node получает SPIFFE ID: `spiffe://x0tta6bl4.mesh/node/{node_id}`
- Mesh services получают SPIFFE ID: `spiffe://x0tta6bl4.mesh/service/{service_name}`
- Все межсервисные коммуникации используют mTLS с SPIFFE validation

---

## 🔧 Deployment Steps

### Phase 1: SPIRE Server Setup (Week 15)

1. **Generate Root CA** (offline, secure)
   ```bash
   ./scripts/generate_spire_ca.sh
   ```

2. **Deploy SPIRE Server**
   ```bash
   kubectl apply -f infra/security/spire-server.yaml
   ```

3. **Verify Server Health**
   ```bash
   kubectl logs -n spire-system spire-server-0
   ```

### Phase 2: SPIRE Agent Deployment (Week 16)

1. **Deploy SPIRE Agent DaemonSet**
   ```bash
   kubectl apply -f infra/security/spire-agent-daemonset.yaml
   ```

2. **Verify Agent Registration**
   ```bash
   ./scripts/verify_spire_agents.sh
   ```

### Phase 3: Mesh Node Integration (Week 17-18)

1. **Bootstrap Mesh Nodes with SPIFFE**
   ```bash
   python scripts/deploy_spiffe_to_mesh_nodes.py --nodes all
   ```

2. **Register Mesh Node Identities**
   ```python
   from src.security.spiffe import SPIFFEController
   
   controller = SPIFFEController(trust_domain="x0tta6bl4.mesh")
   controller.initialize(attestation_strategy="join_token", token="...")
   
   # Register mesh node
   controller.register_workload(
       spiffe_id="spiffe://x0tta6bl4.mesh/node/node-001",
       selectors={"mesh:node_id": "node-001"}
   )
   ```

3. **Enable mTLS for Mesh Services**
   ```python
   # In mesh service initialization
   from src.security.spiffe import SPIFFEController
   
   controller = SPIFFEController()
   controller.initialize()
   
   # Establish mTLS connection
   connection = controller.establish_mtls_connection(
       peer_spiffe_id="spiffe://x0tta6bl4.mesh/service/mesh-api"
   )
   ```

### Phase 4: Certificate Rotation (Week 19-20)

1. **Automatic SVID Rotation**
   - SPIRE Agent автоматически обновляет SVID при 50% TTL
   - Mesh services автоматически переподключаются

2. **Monitor Rotation Health**
   ```bash
   # Prometheus query
   rate(spire_agent_svid_rotations_total[5m])
   ```

---

## 📊 Monitoring & Observability

### Prometheus Metrics

**SPIRE Server**:
- `spire_server_svid_issued_total`: Количество выданных SVID
- `spire_server_node_attestations_total`: Node attestations
- `spire_server_ca_rotation_total`: CA rotations

**SPIRE Agent**:
- `spire_agent_svid_rotations_total`: SVID rotations
- `spire_agent_workload_api_connections`: Active workload connections
- `spire_agent_svid_cache_size`: Cached SVIDs

**mTLS Connections**:
- `mesh_mtls_handshakes_total`: mTLS handshakes
- `mesh_mtls_handshake_duration_seconds`: Handshake latency
- `mesh_mtls_auth_failures_total`: Authentication failures

### Grafana Dashboard

**Panel 1**: SPIRE Server Health
- SVIDs issued per minute
- Node attestation success rate
- CA rotation status

**Panel 2**: SPIRE Agent Status
- Agents registered per node
- SVID rotation frequency
- Workload API connections

**Panel 3**: mTLS Metrics
- mTLS handshake latency (p50, p95, p99)
- Authentication failure rate
- Active mTLS connections

---

## 🔐 Security Best Practices

1. **CA Key Protection**
   - Root CA keys хранятся offline
   - Server CA keys в encrypted storage (KMS/Vault)
   - Regular CA rotation (quarterly)

2. **Join Token Management**
   - Join tokens одноразовые
   - Токены expire через 5 минут
   - Audit log всех использований

3. **Workload Selectors**
   - Минимальные привилегии (least privilege)
   - Explicit selectors (не wildcards)
   - Regular audit workload registrations

4. **mTLS Configuration**
   - TLS 1.3 only
   - Strong cipher suites
   - Certificate pinning для критичных сервисов

---

## 🚀 Quick Start

### For Kubernetes Deployment

```bash
# 1. Generate CA (one-time, secure location)
./scripts/generate_spire_ca.sh

# 2. Deploy SPIRE Server
kubectl apply -f infra/security/spire-server.yaml

# 3. Deploy SPIRE Agent
kubectl apply -f infra/security/spire-agent-daemonset.yaml

# 4. Verify deployment
./scripts/verify_spire_deployment.sh
```

### For Mesh Node Deployment

```bash
# 1. Install SPIRE Agent on mesh node
./scripts/install_spire_agent_mesh.sh --node-id node-001

# 2. Bootstrap SPIFFE identity
python scripts/bootstrap_mesh_node_spiffe.py --node-id node-001 --join-token <token>

# 3. Verify identity
python -c "from src.security.spiffe import SPIFFEController; c = SPIFFEController(); c.initialize(); print(c.get_identity().spiffe_id)"
```

---

## 📝 Next Steps

1. ✅ Create SPIRE Server Kubernetes manifests
2. ✅ Create SPIRE Agent DaemonSet manifests
3. ✅ Create mesh node bootstrap script
4. ✅ Integrate mTLS with mesh networking layer
5. ✅ Add Prometheus metrics export
6. ✅ Create Grafana dashboard
7. ✅ Document certificate rotation process

---

**Дата создания**: 2025-01-XX  
**Версия**: 1.0.0  
**Статус**: Ready for Implementation

