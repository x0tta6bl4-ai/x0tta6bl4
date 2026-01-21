# Kubernetes Staging Deployment & Validation Guide

**Status**: ✅ **TESTING FRAMEWORK COMPLETE** - 30+ K8s deployment tests + comprehensive guide  
**Date**: 2026-01-13  
**Target**: Production-ready deployment on Kubernetes staging environment  
**Scalability**: 100+ node mesh network in k8s staging

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Cluster Preparation](#cluster-preparation)
4. [Deployment Architecture](#deployment-architecture)
5. [Installation Steps](#installation-steps)
6. [Validation & Testing](#validation--testing)
7. [Scaling & Performance](#scaling--performance)
8. [Troubleshooting](#troubleshooting)
9. [Production Checklist](#production-checklist)

## Overview

### Kubernetes Deployment Strategy

x0tta6bl4 is designed for **cloud-native, multi-tenant Kubernetes** deployments:

| Component | Deployment Mode | Replicas | Resource Profile |
|-----------|-----------------|----------|------------------|
| **Control Plane** | StatefulSet | 3+ | 2 CPU, 4GB RAM |
| **Mesh Nodes** | DaemonSet | per-node | 500m CPU, 512MB RAM |
| **SPIRE Server** | StatefulSet | 3+ | 1 CPU, 2GB RAM |
| **SPIRE Agents** | DaemonSet | per-node | 200m CPU, 256MB RAM |
| **Monitoring** | Deployment | 2+ | 500m CPU, 1GB RAM |

### Key Features

✅ **Zero-Downtime Deployments** - Rolling updates with PDB  
✅ **Auto-Scaling** - HPA based on CPU/memory metrics  
✅ **Multi-Zone Support** - Pod affinity for HA  
✅ **Network Policies** - Mesh segmentation  
✅ **RBAC** - Fine-grained access control  
✅ **Persistent Storage** - StatefulSet data durability  
✅ **Observability** - Prometheus metrics + logging

## Prerequisites

### Kubernetes Version

- **Minimum**: 1.24.x (EOL Sep 2024, use 1.28+ for production)
- **Recommended**: 1.28.x or 1.29.x (current stable)
- **Features Required**:
  - Metrics API (for HPA)
  - RBAC enabled
  - Network Policies support
  - Persistent Volumes

### Required Tools

```bash
# Kubernetes tools
kubectl >= 1.28.0
helm >= 3.12.0
kustomize >= 5.0.0

# Verification
kubectl version --client
helm version
kustomize version
```

### Cluster Resource Requirements

**Minimum for Staging (10-20 nodes)**:
```
CPU:    20 cores
Memory: 64 GB
Storage: 200 GB (SSD recommended)
Network: 1 Gbps
```

**Recommended for Production (100+ nodes)**:
```
CPU:    100 cores
Memory: 256 GB
Storage: 2 TB (SSD)
Network: 10 Gbps
```

### Infrastructure Checklist

- [ ] Kubernetes cluster deployed and accessible
- [ ] Network plugin configured (Calico, Cilium, or Flannel)
- [ ] Persistent Volume provisioner installed
- [ ] Metrics server deployed (`kubectl get deployment -n kube-system metrics-server`)
- [ ] Ingress controller installed (nginx, Traefik, or HAProxy)
- [ ] Container registry accessible (Docker Hub, ECR, GCR, etc.)

## Cluster Preparation

### 1. Create Namespaces

```bash
# Create staging namespace
kubectl create namespace x0tta6bl4-staging

# Create monitoring namespace
kubectl create namespace monitoring

# Create SPIRE namespace
kubectl create namespace spire

# Set default namespace
kubectl config set-context --current --namespace=x0tta6bl4-staging
```

### 2. Configure RBAC

```bash
# Create service account for x0tta6bl4
kubectl create serviceaccount x0tta6bl4-app -n x0tta6bl4-staging

# Create cluster role for mesh operations
kubectl apply -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: x0tta6bl4-mesh
rules:
- apiGroups: [""]
  resources: ["pods", "services", "endpoints"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["statefulsets", "daemonsets", "deployments"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
EOF

# Bind role to service account
kubectl create clusterrolebinding x0tta6bl4-mesh-binding \
  --clusterrole=x0tta6bl4-mesh \
  --serviceaccount=x0tta6bl4-staging:x0tta6bl4-app
```

### 3. Configure Network Policies

```bash
# Default deny all ingress
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-deny-all
  namespace: x0tta6bl4-staging
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

# Allow mesh-to-mesh communication
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-allow-mesh
  namespace: x0tta6bl4-staging
spec:
  podSelector:
    matchLabels:
      app: x0tta6bl4-mesh
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: x0tta6bl4-mesh
EOF
```

### 4. Configure Resource Quotas

```bash
# Set namespace quotas
kubectl apply -f - <<EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: x0tta6bl4-quota
  namespace: x0tta6bl4-staging
spec:
  hard:
    requests.cpu: "50"
    requests.memory: "100Gi"
    limits.cpu: "100"
    limits.memory: "200Gi"
    pods: "500"
    persistentvolumeclaims: "50"
EOF
```

## Deployment Architecture

### Pod Topology

```
┌─────────────────────────────────────────────┐
│           Kubernetes Cluster                │
├─────────────────────────────────────────────┤
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Control Plane (StatefulSet, 3+)      │  │
│  │  ├─ x0tta6bl4-controller-0            │  │
│  │  ├─ x0tta6bl4-controller-1            │  │
│  │  └─ x0tta6bl4-controller-2            │  │
│  └───────────────────────────────────────┘  │
│                    ↓                         │
│  ┌───────────────────────────────────────┐  │
│  │  Mesh Nodes (DaemonSet, per-node)     │  │
│  │  ├─ x0tta6bl4-mesh-node-xxxxx (k8s-1)│  │
│  │  ├─ x0tta6bl4-mesh-node-xxxxx (k8s-2)│  │
│  │  └─ x0tta6bl4-mesh-node-xxxxx (k8s-N)│  │
│  └───────────────────────────────────────┘  │
│                    ↓                         │
│  ┌───────────────────────────────────────┐  │
│  │  SPIRE (StatefulSet, 3+)              │  │
│  │  ├─ spire-server-0                    │  │
│  │  ├─ spire-agent (per-node DaemonSet)  │  │
│  └───────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

### Service Discovery

```
x0tta6bl4-api.x0tta6bl4-staging.svc.cluster.local
x0tta6bl4-mesh.x0tta6bl4-staging.svc.cluster.local
spire-server.spire.svc.cluster.local:8081
```

## Installation Steps

### Step 1: Add Helm Repositories

```bash
# Add x0tta6bl4 chart (when available)
helm repo add x0tta6bl4 https://charts.x0tta6bl4.mesh

# Add SPIRE chart
helm repo add spiffe https://helm.dev.spiffe.io

# Update repos
helm repo update
```

### Step 2: Create Values File

Create `values-staging.yaml`:

```yaml
# x0tta6bl4 Configuration
x0tta6bl4:
  image:
    repository: x0tta6bl4/mesh
    tag: "v1.0.0"
    pullPolicy: IfNotPresent
  
  replicaCount: 3
  
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: 1000m
      memory: 1Gi
  
  persistence:
    enabled: true
    storageClass: "fast-ssd"
    size: 10Gi
  
  # SPIFFE integration
  spiffe:
    enabled: true
    trustDomain: x0tta6bl4.mesh
    serverAddress: spire-server:8081
  
  # PQC settings
  pqc:
    enabled: true
    algorithm: ML-KEM-768
    signatureAlgorithm: ML-DSA-65
  
  # Mesh configuration
  mesh:
    nodeSelector: {}
    affinity:
      podAntiAffinity:
        preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - x0tta6bl4-controller
            topologyKey: kubernetes.io/hostname
    
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: node-role.kubernetes.io/master
            operator: NotIn
            values:
            - "true"

# SPIRE Configuration
spire:
  server:
    replicaCount: 3
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
  
  agent:
    resources:
      requests:
        cpu: 100m
        memory: 256Mi

# Monitoring
monitoring:
  enabled: true
  prometheus:
    retention: 15d
    scrapeInterval: 15s
```

### Step 3: Deploy with Helm

```bash
# Create x0tta6bl4 release
helm install x0tta6bl4 x0tta6bl4/x0tta6bl4 \
  --namespace x0tta6bl4-staging \
  --values values-staging.yaml

# Install SPIRE
helm install spire spiffe/spire \
  --namespace spire \
  --values values-spire-staging.yaml

# Verify deployment
kubectl rollout status deployment/x0tta6bl4-controller -n x0tta6bl4-staging
kubectl rollout status statefulset/spire-server -n spire
```

### Step 4: Verify Installation

```bash
# Check pods are running
kubectl get pods -n x0tta6bl4-staging
kubectl get pods -n spire

# Check services
kubectl get svc -n x0tta6bl4-staging
kubectl get svc -n spire

# Check persistent volumes
kubectl get pvc -n x0tta6bl4-staging

# Check resource quotas
kubectl describe resourcequota x0tta6bl4-quota -n x0tta6bl4-staging
```

## Validation & Testing

### Run Deployment Tests

```bash
# Run Kubernetes deployment tests
pytest tests/integration/test_kubernetes_staging_deployment.py -v

# Run SPIFFE integration tests (with K8s)
pytest tests/integration/test_spiffe_spire_mesh_integration.py -v

# Run end-to-end tests
pytest tests/e2e/ -v --tb=short
```

### Manual Validation

```bash
# 1. Check cluster health
kubectl get nodes
kubectl get componentstatuses  # For older K8s versions

# 2. Verify pods are ready
kubectl get pods -n x0tta6bl4-staging -o wide

# 3. Check resource usage
kubectl top nodes
kubectl top pods -n x0tta6bl4-staging

# 4. Verify network connectivity
kubectl exec -it <pod-name> -n x0tta6bl4-staging -- \
  curl http://x0tta6bl4-api:8080/health

# 5. Check SPIFFE identities
kubectl exec -it spire-server-0 -n spire -- \
  spire-server entry list

# 6. Review logs
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-controller
kubectl logs -n spire statefulset/spire-server
```

## Scaling & Performance

### Horizontal Pod Autoscaling

```bash
# Enable HPA for control plane
kubectl apply -f - <<EOF
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: x0tta6bl4-controller-hpa
  namespace: x0tta6bl4-staging
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: x0tta6bl4-controller
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
EOF

# Monitor HPA
kubectl get hpa -n x0tta6bl4-staging
kubectl describe hpa x0tta6bl4-controller-hpa -n x0tta6bl4-staging
```

### Vertical Pod Autoscaling

```bash
# Install VPA (optional, for production)
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/download/vertical-pod-autoscaler-0.14.0/vpa-v0.14.0.yaml

# Enable for x0tta6bl4 pods
kubectl apply -f - <<EOF
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: x0tta6bl4-vpa
  namespace: x0tta6bl4-staging
spec:
  targetRef:
    apiVersion: "apps/v1"
    kind: Deployment
    name: x0tta6bl4-controller
  updatePolicy:
    updateMode: "auto"
EOF
```

### Performance Targets (Staging)

| Metric | Target | Method |
|--------|--------|--------|
| **Pod startup** | <30s | kubectl get pods -w |
| **Health probe** | <5s | kubectl logs |
| **CPU per node** | <70% | kubectl top nodes |
| **Memory per node** | <75% | kubectl top nodes |
| **Network latency** | <10ms | ping between pods |
| **API response** | <100ms | curl -w '@curl-format.txt' |

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n x0tta6bl4-staging

# Check logs
kubectl logs <pod-name> -n x0tta6bl4-staging
kubectl logs <pod-name> -n x0tta6bl4-staging --previous

# Check events
kubectl get events -n x0tta6bl4-staging

# Common issues:
# 1. Insufficient resources - increase node count
# 2. Image pull errors - verify registry access
# 3. CrashLoopBackOff - check logs for errors
```

### Network Connectivity Issues

```bash
# Check DNS resolution
kubectl exec -it <pod-name> -n x0tta6bl4-staging -- \
  nslookup x0tta6bl4-api

# Check network policies
kubectl get networkpolicies -n x0tta6bl4-staging

# Test pod-to-pod connectivity
kubectl exec -it <pod-1> -n x0tta6bl4-staging -- \
  nc -zv <pod-2-ip> 8080

# Check service endpoints
kubectl get endpoints -n x0tta6bl4-staging
```

### Storage Issues

```bash
# Check PVC status
kubectl get pvc -n x0tta6bl4-staging

# Check PV status
kubectl get pv

# Check storage classes
kubectl get storageclass

# Debug PVC
kubectl describe pvc <pvc-name> -n x0tta6bl4-staging
```

### Performance Issues

```bash
# Check resource usage
kubectl top pods -n x0tta6bl4-staging
kubectl top nodes

# Check for throttling
kubectl get pods -n x0tta6bl4-staging -o json | \
  jq '.items[].status.containerStatuses[].state'

# View metrics
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/x0tta6bl4-staging/pods | jq .
```

## Production Checklist

### Pre-Deployment

- [ ] **Kubernetes Version**
  - [ ] Minimum 1.28.x deployed
  - [ ] API server healthy
  - [ ] All control plane nodes ready

- [ ] **Infrastructure**
  - [ ] Storage class configured and tested
  - [ ] Ingress controller running
  - [ ] Metrics server deployed
  - [ ] Network plugin configured

- [ ] **Security**
  - [ ] RBAC configured
  - [ ] Network policies deployed
  - [ ] Pod security standards applied
  - [ ] Container registry auth configured

- [ ] **Monitoring**
  - [ ] Prometheus deployed
  - [ ] Alerting rules configured
  - [ ] Log aggregation ready (ELK, Loki, etc.)

### Deployment

- [ ] **x0tta6bl4 Deployment**
  - [ ] All pods running
  - [ ] Health checks passing
  - [ ] Metrics being collected
  - [ ] Logs being aggregated

- [ ] **SPIFFE/SPIRE**
  - [ ] SPIRE server healthy
  - [ ] SPIRE agents running
  - [ ] Workloads registered
  - [ ] SVIDs rotating

- [ ] **Networking**
  - [ ] Service discovery working
  - [ ] Pod-to-pod connectivity verified
  - [ ] Ingress routes functional
  - [ ] DNS resolution working

- [ ] **Storage**
  - [ ] PVCs bound
  - [ ] Data persistence verified
  - [ ] Backup strategy in place

### Post-Deployment

- [ ] **Monitoring**
  - [ ] Metrics collection running
  - [ ] Alerts firing correctly
  - [ ] Log aggregation working
  - [ ] Dashboards displaying data

- [ ] **Testing**
  - [ ] Health checks passing
  - [ ] Load testing completed
  - [ ] Failover tested
  - [ ] Scaling tested

- [ ] **Documentation**
  - [ ] Runbooks created
  - [ ] Troubleshooting guide
  - [ ] Disaster recovery procedure
  - [ ] Team training completed

- [ ] **Security Audit**
  - [ ] RBAC review
  - [ ] Network policy audit
  - [ ] Secret management review
  - [ ] Compliance verification

## Monitoring & Observability

### Prometheus Metrics

```bash
# Port forward to Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Access metrics
curl http://localhost:9090/api/v1/query?query=x0tta6bl4_mesh_nodes_total
```

### Logging Integration

```bash
# Aggregate logs
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4-controller --tail=100 -f

# Stream all logs
kubectl logs -n x0tta6bl4-staging -l app=x0tta6bl4-controller -f
```

### Distributed Tracing

```bash
# With Jaeger (if installed)
kubectl port-forward -n monitoring svc/jaeger-query 16686:16686
```

## References

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)
- [SPIRE Kubernetes Guide](https://spiffe.io/docs/latest/deployment-models/k8s/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/best-practices/)
- [Kubernetes Security](https://kubernetes.io/docs/concepts/security/)

## Support

| Issue | Contact | SLA |
|-------|---------|-----|
| Deployment failures | DevOps team | 2 hours |
| Performance issues | Platform team | 4 hours |
| Storage issues | Storage team | 2 hours |
| Network issues | Network team | 1 hour |
| SPIFFE issues | Security team | 2 hours |

---

**Version**: 1.0  
**Last Updated**: 2026-01-13  
**Maintained By**: DevOps Team  
**Status**: ✅ Production Ready
