# 🔒 Security Infrastructure Setup

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

---

## 📋 Overview

x0tta6bl4 требует следующих security компонентов:
- **SPIRE Server** - Identity issuance
- **SPIRE Agent** - Workload attestation
- **HashiCorp Vault** - Secrets management
- **Certificate Management** - TLS certificates

---

## 🛡️ SPIRE Server Setup

### Installation

```bash
# Create namespace
kubectl create namespace spire

# Deploy SPIRE Server
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: spire-server-config
  namespace: spire
data:
  server.conf: |
    server {
      bind_address = "0.0.0.0"
      bind_port = "8081"
      trust_domain = "x0tta6bl4.mesh"
      data_dir = "/run/spire/data"
      log_level = "INFO"
      
      plugins {
        NodeAttestor "k8s_psat" {
          plugin_data {
            clusters = {
              "x0tta6bl4-cluster" = {
                service_account_allow_list = ["spire:spire-agent"]
              }
            }
          }
        }
        
        KeyManager "memory" {
          plugin_data {}
        }
        
        DataStore "sql" {
          plugin_data {
            database_type = "sqlite3"
            connection_string = "/run/spire/data/datastore.sqlite3"
          }
        }
      }
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spire-server
  namespace: spire
spec:
  replicas: 1
  selector:
    matchLabels:
      app: spire-server
  template:
    metadata:
      labels:
        app: spire-server
    spec:
      serviceAccountName: spire-server
      containers:
        - name: spire-server
          image: ghcr.io/spiffe/spire-server:1.8.0
          args: ["-config", "/run/spire/config/server.conf"]
          volumeMounts:
            - name: spire-server-config
              mountPath: /run/spire/config
            - name: spire-server-data
              mountPath: /run/spire/data
      volumes:
        - name: spire-server-config
          configMap:
            name: spire-server-config
        - name: spire-server-data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: spire-server
  namespace: spire
spec:
  selector:
    app: spire-server
  ports:
    - port: 8081
      targetPort: 8081
EOF
```

### Verify

```bash
# Check SPIRE Server
kubectl get pods -n spire
kubectl logs -n spire -l app=spire-server

# Test connection
kubectl port-forward -n spire svc/spire-server 8081:8081
curl http://localhost:8081/health
```

---

## 🤖 SPIRE Agent Setup

### Installation

```bash
# Deploy SPIRE Agent as DaemonSet
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: spire-agent
  namespace: spire
spec:
  selector:
    matchLabels:
      app: spire-agent
  template:
    metadata:
      labels:
        app: spire-agent
    spec:
      serviceAccountName: spire-agent
      hostNetwork: true
      containers:
        - name: spire-agent
          image: ghcr.io/spiffe/spire-agent:1.8.0
          args: ["-config", "/run/spire/config/agent.conf"]
          volumeMounts:
            - name: spire-agent-config
              mountPath: /run/spire/config
            - name: spire-agent-socket
              mountPath: /run/spire/sockets
      volumes:
        - name: spire-agent-config
          configMap:
            name: spire-agent-config
        - name: spire-agent-socket
          hostPath:
            path: /run/spire/sockets
            type: DirectoryOrCreate
EOF
```

### Verify

```bash
# Check SPIRE Agent
kubectl get daemonset -n spire
kubectl logs -n spire -l app=spire-agent

# Check agent health
kubectl exec -n spire <spire-agent-pod> -- /opt/spire/bin/spire-agent healthcheck
```

---

## 🔐 HashiCorp Vault Setup

### Installation

```bash
# Add Helm repo
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update

# Install Vault
helm install vault hashicorp/vault \
  --namespace vault \
  --create-namespace \
  --set server.dev.enabled=true
```

### Configuration

```bash
# Initialize Vault
kubectl exec -n vault vault-0 -- vault operator init

# Unseal Vault
kubectl exec -n vault vault-0 -- vault operator unseal <unseal-key-1>
kubectl exec -n vault vault-0 -- vault operator unseal <unseal-key-2>
kubectl exec -n vault vault-0 -- vault operator unseal <unseal-key-3>

# Enable KV secrets engine
kubectl exec -n vault vault-0 -- vault secrets enable -path=secret kv-v2
```

### Integration with x0tta6bl4

```yaml
# In helm values
secrets:
  enabled: true
  vault:
    enabled: true
    address: "http://vault.vault.svc.cluster.local:8200"
    path: "secret/x0tta6bl4"
```

---

## 📜 Certificate Management

### Using cert-manager

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@x0tta6bl4.io
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
```

### Certificate for x0tta6bl4

```yaml
# In helm values
ingress:
  enabled: true
  tls:
    - secretName: x0tta6bl4-tls
      hosts:
        - x0tta6bl4.example.com
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

---

## 🔒 Network Policies

### Default Deny

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-default-deny
  namespace: x0tta6bl4
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### Allow Specific Traffic

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-allow
  namespace: x0tta6bl4
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: x0tta6bl4
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
          port: 8000
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: spire
      ports:
        - protocol: TCP
          port: 8081
```

---

## ✅ Verification

### SPIRE Health

```bash
# Server
kubectl exec -n spire <spire-server-pod> -- /opt/spire/bin/spire-server healthcheck

# Agent
kubectl exec -n spire <spire-agent-pod> -- /opt/spire/bin/spire-agent healthcheck
```

### Vault Health

```bash
kubectl exec -n vault vault-0 -- vault status
```

### Certificate Status

```bash
kubectl get certificates -n x0tta6bl4
kubectl describe certificate -n x0tta6bl4 x0tta6bl4-tls
```

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

