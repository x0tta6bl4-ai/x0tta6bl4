# 🚀 Staging Deployment Plan - x0tta6bl4 v3.4

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4  
**Статус:** ⚠️ **READY TO START**

---

## 📋 Overview

План развертывания x0tta6bl4 v3.4 в staging environment для подготовки к beta testing.

---

## 🎯 Objectives

1. Развернуть x0tta6bl4 v3.4 в staging Kubernetes cluster
2. Настроить monitoring stack
3. Проверить работоспособность всех компонентов
4. Подготовить к beta testing

---

## 📅 Timeline

**Estimated Duration:** 2-3 дня

- **Day 1:** Cluster setup и initial deployment
- **Day 2:** Monitoring setup и verification
- **Day 3:** Final checks и beta preparation

---

## 🔧 Prerequisites

### Required
- [x] Kubernetes cluster (EKS/GKE/AKS/kind/minikube)
- [x] kubectl configured
- [x] helm installed
- [x] Docker images built
- [x] Helm charts ready

### Optional but Recommended
- [ ] Monitoring stack (Prometheus, Grafana)
- [ ] Logging stack (ELK/Loki)
- [ ] Ingress controller
- [ ] Certificate manager

---

## 📋 Step-by-Step Plan

### Step 1: Cluster Preparation

#### 1.1 Choose Platform

**Options:**
- **kind/minikube** - для локального тестирования
- **EKS** - AWS (production-like)
- **GKE** - Google Cloud
- **AKS** - Azure
- **Self-hosted** - собственный кластер

**Recommendation:** Начать с kind/minikube для тестирования, затем перейти на EKS/GKE для staging.

#### 1.2 Setup Cluster

```bash
# Option 1: kind (Kubernetes in Docker)
kind create cluster --name x0tta6bl4-staging

# Option 2: minikube
minikube start

# Option 3: EKS (requires AWS CLI)
# terraform apply -target=module.eks
```

#### 1.3 Verify Cluster

```bash
# Check cluster status
kubectl cluster-info
kubectl get nodes

# Verify cluster is ready
./scripts/validate_cluster.sh
```

**Expected Output:**
- All nodes in Ready state
- Cluster API accessible
- kubectl working

---

### Step 2: Namespace Setup

#### 2.1 Create Namespaces

```bash
# Create staging namespace
kubectl create namespace x0tta6bl4-staging

# Create monitoring namespace
kubectl create namespace monitoring

# Verify namespaces
kubectl get namespaces
```

#### 2.2 Setup RBAC (if needed)

```bash
# Apply service account
kubectl apply -f helm/x0tta6bl4/templates/serviceaccount.yaml -n x0tta6bl4-staging
```

---

### Step 3: Monitoring Stack (Optional but Recommended)

#### 3.1 Deploy Prometheus

```bash
# Using Prometheus Operator (recommended)
kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring

# Or using our custom configuration
kubectl apply -f monitoring/prometheus/ -n monitoring
```

#### 3.2 Deploy Grafana

```bash
# If using kube-prometheus-stack, Grafana is included
# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# Default credentials: admin/prom-operator
```

#### 3.3 Verify Monitoring

```bash
# Check Prometheus
kubectl get pods -n monitoring | grep prometheus

# Check Grafana
kubectl get pods -n monitoring | grep grafana

# Access Prometheus
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

---

### Step 4: Deploy x0tta6bl4

#### 4.1 Build Docker Image (if needed)

```bash
# Build production image
docker build -f Dockerfile.production -t x0tta6bl4:3.4.0 .

# Tag for registry (if using remote registry)
docker tag x0tta6bl4:3.4.0 <registry>/x0tta6bl4:3.4.0

# Push to registry
docker push <registry>/x0tta6bl4:3.4.0
```

#### 4.2 Deploy with Helm

```bash
# Deploy to staging
./scripts/deploy_staging.sh latest

# Or manually
helm upgrade --install x0tta6bl4 ./helm/x0tta6bl4 \
    --namespace x0tta6bl4-staging \
    --create-namespace \
    --set image.tag=3.4.0 \
    --set production.enabled=false \
    --set replicaCount=2 \
    --set resources.requests.cpu=250m \
    --set resources.requests.memory=512Mi \
    --set resources.limits.cpu=1000m \
    --set resources.limits.memory=2Gi \
    --wait \
    --timeout 10m
```

#### 4.3 Verify Deployment

```bash
# Check pods
kubectl get pods -n x0tta6bl4-staging

# Check services
kubectl get svc -n x0tta6bl4-staging

# Check deployment status
kubectl rollout status deployment/x0tta6bl4 -n x0tta6bl4-staging
```

**Expected:**
- All pods in Running state
- Services accessible
- Deployment successful

---

### Step 5: Health Verification

#### 5.1 Port Forward

```bash
# Port forward to service
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4 8000:8000
```

#### 5.2 Health Checks

```bash
# Health check
curl http://localhost:8000/health

# Dependencies check
curl http://localhost:8000/health/dependencies

# Metrics
curl http://localhost:8000/metrics
```

**Expected:**
- Health status: `healthy`
- All dependencies: `available`
- Metrics: accessible

#### 5.3 Monitor Deployment

```bash
# Monitor for 5 minutes
./scripts/monitor_deployment.sh x0tta6bl4-staging 300
```

---

### Step 6: Monitoring Integration

#### 6.1 Verify ServiceMonitor

```bash
# Check ServiceMonitor
kubectl get servicemonitor -n x0tta6bl4-staging

# Verify Prometheus is scraping
# Access Prometheus UI and check targets
```

#### 6.2 Import Grafana Dashboard

```bash
# Dashboard is in monitoring/grafana/dashboards/x0tta6bl4-overview.json
# Import via Grafana UI or:
kubectl apply -f monitoring/grafana/dashboards/ -n monitoring
```

#### 6.3 Verify Alerts

```bash
# Check alert rules
kubectl get prometheusrules -n monitoring

# Verify alerts are configured
# Access Prometheus UI and check alerts
```

---

### Step 7: Final Verification

#### 7.1 Run Test Scenarios

```bash
# Run basic test scenarios from docs/beta/BETA_TEST_SCENARIOS.md
# Scenario 1: Basic Deployment
# Scenario 2: Mesh Network Connectivity
# Scenario 3: Post-Quantum Cryptography
```

#### 7.2 Load Testing

```bash
# Run load test
./scripts/load_test.sh http://localhost:8000 60s 10
```

#### 7.3 Documentation

- [ ] Document deployment process
- [ ] Document any issues encountered
- [ ] Update runbooks if needed

---

## ✅ Success Criteria

### Deployment
- [ ] All pods running
- [ ] Services accessible
- [ ] Health checks passing
- [ ] Dependencies available

### Monitoring
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboards working
- [ ] Alerts configured
- [ ] Logs accessible

### Functionality
- [ ] Health endpoints working
- [ ] Metrics exposed
- [ ] Basic functionality verified
- [ ] Load test passed

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** Pods not starting
```bash
# Check pod logs
kubectl logs -n x0tta6bl4-staging deployment/x0tta6bl4

# Check pod events
kubectl describe pod -n x0tta6bl4-staging <pod-name>
```

**Issue:** Health check failing
```bash
# Check dependencies
python3 scripts/check_dependencies.py

# Check service
kubectl get svc -n x0tta6bl4-staging
kubectl get endpoints -n x0tta6bl4-staging
```

**Issue:** Monitoring not working
```bash
# Check Prometheus
kubectl get pods -n monitoring
kubectl logs -n monitoring deployment/prometheus

# Check ServiceMonitor
kubectl get servicemonitor -n x0tta6bl4-staging
```

---

## 📚 Next Steps

After successful staging deployment:

1. **Internal Beta Testing**
   - Invite 5-10 internal testers
   - Collect feedback
   - Fix issues

2. **External Beta Launch**
   - Recruit 20-50 beta testers
   - Launch beta program
   - Monitor usage

3. **Production Preparation**
   - Review staging experience
   - Optimize based on feedback
   - Prepare for production

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4  
**Статус:** ⚠️ **READY TO START**





















