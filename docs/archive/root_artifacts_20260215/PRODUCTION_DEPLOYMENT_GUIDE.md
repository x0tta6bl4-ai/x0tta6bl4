# Production Deployment Guide: x0tta6bl4 v2.0

**Version:** 2.0.0  
**Last Updated:** January 1, 2026

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Deployment](#docker-deployment)
3. [Kubernetes Deployment](#kubernetes-deployment)
4. [Monitoring Setup](#monitoring-setup)
5. [Security Hardening](#security-hardening)
6. [Troubleshooting](#troubleshooting)

---

## 🔧 Prerequisites

### System Requirements

- **OS:** Linux (Ubuntu 20.04+, Debian 11+, or RHEL 8+)
- **CPU:** 2+ cores (4+ recommended)
- **Memory:** 4GB+ RAM (8GB+ recommended)
- **Disk:** 20GB+ free space
- **Network:** Stable internet connection

### Software Requirements

- **Docker:** 20.10+ (for Docker deployment)
- **Kubernetes:** 1.24+ (for K8s deployment)
- **Python:** 3.10+ (for direct installation)
- **IPFS:** Optional (for distributed storage)

---

## 🐳 Docker Deployment

### Quick Start

```bash
# Clone repository
git clone https://github.com/x0tta6bl4/core.git
cd core

# Build image
docker build -t x0tta6bl4:2.0.0 .

# Run with docker-compose
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f x0tta6bl4-node
```

### Configuration

Edit `docker-compose.yml` to customize:

```yaml
environment:
  - NODE_ID=your-node-id
  - LOG_LEVEL=INFO
  - IPFS_ENABLED=true
  - PQC_CACHE_ENABLED=true
```

### Access Services

- **API:** http://localhost:8080
- **Metrics:** http://localhost:8081
- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **IPFS Gateway:** http://localhost:8080

---

## ☸️ Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- `kubectl` configured
- Storage class for persistent volumes

### Deploy

```bash
# Apply ConfigMap
kubectl apply -f k8s/configmap.yaml

# Deploy application
kubectl apply -f k8s/deployment.yaml

# Create service
kubectl apply -f k8s/service.yaml

# Check status
kubectl get pods -l app=x0tta6bl4
kubectl logs -f deployment/x0tta6bl4-node
```

### Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment x0tta6bl4-node --replicas=5

# Auto-scaling (requires metrics-server)
kubectl autoscale deployment x0tta6bl4-node \
  --min=3 --max=10 --cpu-percent=70
```

---

## 📊 Monitoring Setup

### Prometheus

Prometheus is automatically configured via `docker-compose.yml` or K8s manifests.

**Access:** http://localhost:9090

**Key Metrics:**
- `x0tta6bl4_mesh_nodes_total`
- `x0tta6bl4_pqc_handshake_duration_seconds`
- `x0tta6bl4_mapek_cycle_duration_seconds`
- `x0tta6bl4_cpu_percent`
- `x0tta6bl4_memory_percent`

### Grafana

**Access:** http://localhost:3000  
**Default credentials:** admin/admin

**Pre-configured Dashboards:**
- Mesh Network Health
- PQC Performance
- MAPE-K Metrics
- System Resources

---

## 🔒 Security Hardening

### 1. Secrets Management

```bash
# Use Kubernetes secrets
kubectl create secret generic x0tta6bl4-secrets \
  --from-literal=api-key=your-api-key \
  --from-literal=encryption-key=your-encryption-key

# Or use external secret manager (Vault, AWS Secrets Manager)
```

### 2. Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-network-policy
spec:
  podSelector:
    matchLabels:
      app: x0tta6bl4
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: x0tta6bl4
    ports:
    - protocol: TCP
      port: 8080
```

### 3. RBAC

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: x0tta6bl4-role
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
```

### 4. Security Audit

Run security audit checklist:
```bash
# Review SECURITY_AUDIT_CHECKLIST.md
# Complete all items before production
```

---

## 🔍 Troubleshooting

### Common Issues

#### 1. Container won't start

```bash
# Check logs
docker-compose logs x0tta6bl4-node

# Check health
curl http://localhost:8080/api/v1/health
```

#### 2. IPFS connection failed

```bash
# Check IPFS node
docker-compose logs ipfs-node

# Verify IPFS is running
curl http://localhost:5001/api/v0/version
```

#### 3. High memory usage

```bash
# Check memory limits in docker-compose.yml
# Adjust resources in k8s/deployment.yaml
# Enable PQC cache: PQC_CACHE_ENABLED=true
```

#### 4. Mesh network not connecting

```bash
# Check network configuration
docker network ls
docker network inspect x0tta6bl4-mesh

# Verify ports are open
netstat -tulpn | grep 4001
```

---

## 📈 Performance Tuning

### PQC Optimization

```yaml
environment:
  - PQC_CACHE_ENABLED=true      # Enable key caching
  - PQC_EBPF_ENABLED=true       # Enable eBPF (requires privileged)
  - PQC_BATCH_SIZE=10           # Batch handshakes
```

### Knowledge Storage

```yaml
environment:
  - STORAGE_CACHE_SIZE=1000     # Local cache size
  - VECTOR_INDEX_M=32           # HNSW parameter
  - VECTOR_INDEX_EF=256         # HNSW parameter
```

### MAPE-K Cycle

```yaml
environment:
  - MAPEK_CYCLE_INTERVAL=60     # Seconds between cycles
  - MAPEK_THREADS=4             # Parallel processing
```

---

## ✅ Pre-Production Checklist

- [ ] Security audit completed
- [ ] Monitoring configured
- [ ] Backups enabled
- [ ] Disaster recovery plan ready
- [ ] Load testing performed
- [ ] Documentation reviewed
- [ ] Team trained
- [ ] Rollback plan prepared

---

## 📞 Support

- **Documentation:** https://docs.x0tta6bl4.net
- **GitHub Issues:** https://github.com/x0tta6bl4/core/issues
- **Email:** support@x0tta6bl4.net

---

**Happy deploying!** 🚀

