# Security Hardening Guide for Production
**Дата:** 2026-01-07  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ⏳ В процессе подготовки

---

## 📋 Overview

**Цель:** Security hardening checklist для production deployment

**Области:**
- Post-Quantum Cryptography
- Zero Trust (SPIFFE/SPIRE)
- Network Security
- Container Security
- Secrets Management
- Access Control

---

## 🔒 Security Checklist

### 1. Post-Quantum Cryptography ✅

**Status:** ✅ Implemented

**Configuration:**
- [x] ML-KEM-768 enabled
- [x] ML-DSA-65 enabled
- [x] Hybrid mode (classical + PQC)
- [ ] Production certificates configured
- [ ] Certificate rotation automated
- [ ] Key management in production

**Actions:**
```bash
# Verify PQC is enabled
kubectl exec -n x0tta6bl4-staging <pod-name> -- \
  python3 -c "from src.security.post_quantum_liboqs import LIBOQS_AVAILABLE; print('PQC:', LIBOQS_AVAILABLE)"

# Check PQC metrics
curl -s http://localhost:8080/metrics | grep pqc_handshake
```

---

### 2. Zero Trust (SPIFFE/SPIRE) ✅

**Status:** ✅ Implemented (code ready)

**Configuration:**
- [x] SPIFFE/SPIRE integration implemented
- [x] Workload API client ready
- [x] Certificate validation ready
- [ ] SPIRE Server deployed in production
- [ ] SPIRE Agent deployed on all nodes
- [ ] Trust domain configured
- [ ] Attestation strategies tested

**Actions:**
```bash
# Deploy SPIRE Server
kubectl apply -f infra/spire/spire-server.yaml

# Deploy SPIRE Agent
kubectl apply -f infra/spire/spire-agent.yaml

# Verify SPIFFE identity
kubectl exec -n x0tta6bl4-staging <pod-name> -- \
  cat /run/spiffe/sockets/agent.sock
```

---

### 3. Network Security

**Configuration:**
- [x] Network policies implemented
- [ ] Network policies applied in production
- [ ] Ingress/egress rules configured
- [ ] Service mesh (if applicable) configured
- [ ] DDoS protection enabled

**Actions:**
```bash
# Apply network policies
kubectl apply -f k8s/network-policies/

# Verify network policies
kubectl get networkpolicies -n x0tta6bl4-staging

# Test connectivity
kubectl exec -n x0tta6bl4-staging <pod-name> -- \
  ping -c 3 <other-pod-ip>
```

---

### 4. Container Security

**Configuration:**
- [x] Multi-stage Docker builds
- [x] Non-root user in containers
- [x] Minimal base images
- [ ] Image scanning enabled
- [ ] Runtime security (Falco) enabled
- [ ] Resource limits configured
- [ ] Security contexts configured

**Actions:**
```bash
# Scan image for vulnerabilities
trivy image localhost:5001/x0tta6bl4:3.4.0-fixed2

# Check security context
kubectl get pod <pod-name> -n x0tta6bl4-staging -o jsonpath='{.spec.securityContext}'

# Verify non-root user
kubectl exec -n x0tta6bl4-staging <pod-name> -- whoami
```

---

### 5. Secrets Management

**Configuration:**
- [x] Secrets not in code
- [x] Kubernetes Secrets used
- [ ] External secrets manager (Vault/AWS Secrets Manager)
- [ ] Secret rotation automated
- [ ] Secret encryption at rest
- [ ] Secret encryption in transit

**Actions:**
```bash
# Check secrets
kubectl get secrets -n x0tta6bl4-staging

# Verify secrets are not in logs
kubectl logs -n x0tta6bl4-staging <pod-name> | grep -i "password\|secret\|key" || echo "OK"

# Rotate secrets (example)
kubectl create secret generic x0tta6bl4-certs \
  --from-file=cert.pem=./certs/new-cert.pem \
  --from-file=key.pem=./certs/new-key.pem \
  -n x0tta6bl4-staging
```

---

### 6. Access Control

**Configuration:**
- [x] RBAC implemented
- [ ] RBAC policies applied
- [ ] Service accounts with minimal permissions
- [ ] Pod security policies (or Pod Security Standards)
- [ ] Admission controllers configured

**Actions:**
```bash
# Check RBAC
kubectl get rolebindings,clusterrolebindings -n x0tta6bl4-staging

# Check service accounts
kubectl get serviceaccounts -n x0tta6bl4-staging

# Verify permissions
kubectl auth can-i create pods --as=system:serviceaccount:x0tta6bl4-staging:default -n x0tta6bl4-staging
```

---

### 7. Monitoring & Alerting

**Configuration:**
- [x] Security metrics exported
- [x] Alert rules configured
- [ ] Security alerts tested
- [ ] Security incident response plan
- [ ] Security audit logging enabled

**Actions:**
```bash
# Check security metrics
curl -s http://localhost:8080/metrics | grep -E "security|auth|cert"

# Test security alerts
# (trigger a security event and verify alert fires)
```

---

### 8. Compliance

**Configuration:**
- [x] PQC (NIST FIPS 203/204 compliant)
- [ ] SOC 2 compliance (if applicable)
- [ ] GDPR compliance (if applicable)
- [ ] Audit logging enabled
- [ ] Data retention policies

**Actions:**
```bash
# Verify compliance
# (run compliance checks)
```

---

## 🔧 Security Hardening Steps

### Step 1: Enable Network Policies

**File:** `k8s/network-policies/x0tta6bl4-network-policy.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-network-policy
  namespace: x0tta6bl4-production
spec:
  podSelector:
    matchLabels:
      app: x0tta6bl4
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 9090
```

**Apply:**
```bash
kubectl apply -f k8s/network-policies/x0tta6bl4-network-policy.yaml
```

---

### Step 2: Configure Pod Security

**File:** `helm/x0tta6bl4/values-production.yaml`

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop:
      - ALL
```

---

### Step 3: Enable Image Scanning

**CI/CD Integration:**
```yaml
# .github/workflows/security-scan.yml
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: localhost:5001/x0tta6bl4:${{ github.sha }}
    format: 'sarif'
    output: 'trivy-results.sarif'
```

---

### Step 4: Configure Secrets Management

**Using External Secrets:**
```bash
# Install External Secrets Operator
kubectl apply -f https://raw.githubusercontent.com/external-secrets/external-secrets/main/deploy/charts/external-secrets/templates/crds/clusterexternalsecret.yaml

# Create secret from AWS Secrets Manager
kubectl apply -f k8s/secrets/external-secret.yaml
```

---

### Step 5: Enable Runtime Security

**Falco Configuration:**
```bash
# Deploy Falco
kubectl apply -f monitoring/falco/falco-exporter-deployment.yaml

# Verify Falco rules
kubectl get configmap falco-rules -n monitoring -o yaml
```

---

## 📊 Security Metrics

### Key Metrics to Monitor

- **PQC Handshake Success Rate:** >99.9%
- **Certificate Expiry:** Alert if <7 days
- **Authentication Failures:** <0.1%
- **Security Incidents:** 0
- **Vulnerability Count:** 0 critical, <5 high
- **Compliance Score:** 100%

---

## ✅ Verification Checklist

### Pre-Production
- [ ] All security configurations applied
- [ ] Network policies tested
- [ ] Secrets management verified
- [ ] Image scanning passed
- [ ] Security alerts tested
- [ ] Access control verified
- [ ] Compliance checks passed

### Post-Production
- [ ] Security metrics monitored
- [ ] Alerts configured and tested
- [ ] Incident response plan ready
- [ ] Security audit scheduled
- [ ] Penetration testing scheduled

---

## 🚨 Security Incident Response

### Incident Types

1. **Certificate Compromise**
   - Rotate certificates immediately
   - Revoke compromised certificates
   - Audit access logs

2. **Unauthorized Access**
   - Isolate affected systems
   - Rotate credentials
   - Audit logs

3. **Vulnerability Discovery**
   - Assess severity
   - Apply patches
   - Update security policies

---

**Статус:** ⏳ В процессе подготовки  
**Следующий шаг:** Apply security configurations в production cluster

