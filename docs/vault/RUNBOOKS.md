# Vault Incident Response Runbooks

This document contains step-by-step procedures for handling common Vault incidents.

## Table of Contents

1. [Vault is Sealed](#vault-is-sealed)
2. [Vault Leader Election Failure](#vault-leader-election-failure)
3. [High Memory Usage](#high-memory-usage)
4. [Authentication Failures](#authentication-failures)
5. [Storage Backend Issues](#storage-backend-issues)
6. [Certificate Expiry](#certificate-expiry)
7. [Secret Leak Response](#secret-leak-response)
8. [Complete Cluster Failure](#complete-cluster-failure)

---

## Vault is Sealed

### Symptoms
- `vault_core_unsealed == 0`
- Applications cannot retrieve secrets
- Error: "Vault is sealed"

### Severity
**Critical** - Service is unavailable

### Response Steps

#### 1. Identify the Cause

```bash
# Check Vault status
kubectl exec -n vault vault-0 -- vault status

# Check logs for seal reason
kubectl logs -n vault vault-0 --tail=100 | grep -i seal
```

Common causes:
- Manual seal operation
- Auto-seal on shutdown/restart
- Seal after key ceremony
- Auto-unseal failure

#### 2. If Using Auto-Unseal (KMS)

```bash
# Check KMS connectivity
kubectl exec -n vault vault-0 -- nslookup kms.<region>.amazonaws.com

# Check IAM permissions
kubectl exec -n vault vault-0 -- vault operator unseal
# Should auto-unseal if KMS is working
```

If KMS is unavailable:
1. Restore KMS connectivity
2. Restart Vault pods
3. Verify auto-unseal works

#### 3. If Using Shamir (Manual Unseal)

```bash
# Retrieve unseal keys (from secure location)
# You need 3 of 5 keys

# Unseal Vault
kubectl exec -n vault vault-0 -- vault operator unseal <key-1>
kubectl exec -n vault vault-0 -- vault operator unseal <key-2>
kubectl exec -n vault vault-0 -- vault operator unseal <key-3>

# Verify
kubectl exec -n vault vault-0 -- vault status
```

#### 4. Verify Recovery

```bash
# Test secret retrieval
kubectl exec -n vault vault-0 -- vault kv get secret/proxy/credentials/proxy-api

# Check application logs
kubectl logs -n default deployment/proxy-api --tail=50
```

### Post-Incident

- Document why Vault sealed
- Review auto-unseal configuration
- Consider enabling auto-unseal if not already enabled

---

## Vault Leader Election Failure

### Symptoms
- `vault_raft_leader == 0`
- Multiple nodes claim leadership
- Requests timing out

### Severity
**Critical** - Cluster is inconsistent

### Response Steps

#### 1. Check Cluster Status

```bash
# List all pods
kubectl get pods -n vault

# Check Raft peers on each node
for pod in vault-0 vault-1 vault-2; do
  echo "=== $pod ==="
  kubectl exec -n vault $pod -- vault operator raft list-peers 2>/dev/null || echo "Failed"
done
```

#### 2. Identify the Leader

```bash
# Check which node is the leader
kubectl exec -n vault vault-0 -- vault status | grep "HA Mode"
```

#### 3. If No Leader Exists

Force a new election:

```bash
# Step down on all nodes
for pod in vault-0 vault-1 vault-2; do
  kubectl exec -n vault $pod -- vault operator step-down 2>/dev/null || true
done

# Wait for election
sleep 10

# Check status
kubectl exec -n vault vault-0 -- vault status
```

#### 4. If Node is Not Joined

```bash
# Check if node is in the cluster
kubectl exec -n vault vault-1 -- vault operator raft list-peers

# If not joined, join it
kubectl exec -n vault vault-1 -- vault operator raft join \
  https://vault-0.vault.svc.cluster.local:8200
```

#### 5. If Node is Unhealthy

Remove and re-add the node:

```bash
# Remove unhealthy node (from leader)
kubectl exec -n vault vault-0 -- vault operator raft remove-peer vault-2

# Restart the pod
kubectl delete pod -n vault vault-2

# Wait for restart
kubectl wait --for=condition=ready pod/vault-2 -n vault --timeout=120s

# Rejoin
kubectl exec -n vault vault-2 -- vault operator raft join \
  https://vault-0.vault.svc.cluster.local:8200
```

### Post-Incident

- Review cluster autopilot settings
- Check network connectivity between nodes
- Monitor for split-brain conditions

---

## High Memory Usage

### Symptoms
- `vault_runtime_alloc_bytes / vault_runtime_sys_bytes > 0.8`
- OOMKilled pods
- Slow response times

### Severity
**Warning** - Performance degraded

### Response Steps

#### 1. Identify Memory Usage

```bash
# Check memory usage
kubectl top pod -n vault

# Check Vault memory metrics
kubectl exec -n vault vault-0 -- vault debug -output=/tmp/debug
kubectl cp vault/vault-0:/tmp/debug /tmp/vault-debug
```

#### 2. Check for Memory Leaks

```bash
# Check goroutine count
kubectl exec -n vault vault-0 -- wget -qO- http://localhost:9090/metrics | grep vault_runtime_num_goroutines

# Check lease count
kubectl exec -n vault vault-0 -- wget -qO- http://localhost:9090/metrics | grep vault_expire_num_leases
```

#### 3. Reduce Memory Pressure

```bash
# Revoke expired leases
kubectl exec -n vault vault-0 -- vault lease revoke -prefix -force auth/token/

# Force GC (if needed)
kubectl exec -n vault vault-0 -- vault debug -force-gc
```

#### 4. Scale Resources

```bash
# Increase memory limits
kubectl patch statefulset vault -n vault --type='json' -p='[{
  "op": "replace",
  "path": "/spec/template/spec/containers/0/resources/limits/memory",
  "value": "4Gi"
}]'

# Wait for rollout
kubectl rollout status statefulset/vault -n vault
```

### Post-Incident

- Review lease TTLs
- Tune garbage collection
- Consider horizontal scaling

---

## Authentication Failures

### Symptoms
- `vault_auth_failures_total` increasing
- Applications getting 403 errors
- Kubernetes auth failing

### Severity
**Warning** - Service degradation

### Response Steps

#### 1. Check Auth Method Status

```bash
# Check Kubernetes auth config
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/config

# Check if JWT is valid
kubectl create token proxy-api -n default
```

#### 2. Verify Role Configuration

```bash
# Check role exists
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/role/proxy-api

# Check bound service accounts
kubectl get sa proxy-api -n default
```

#### 3. Test Authentication

```bash
# Get service account token
SA_TOKEN=$(kubectl create token proxy-api -n default)

# Test login
kubectl exec -n vault vault-0 -- vault write auth/kubernetes/login \
  role=proxy-api \
  jwt="$SA_TOKEN"
```

#### 4. Fix Common Issues

**Issue**: JWT token expired
```bash
# Service account tokens are now short-lived (1 hour by default)
# Ensure applications re-authenticate or use TokenRequest API
```

**Issue**: Wrong Kubernetes host
```bash
# Update Kubernetes auth config
kubectl exec -n vault vault-0 -- vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc" \
  token_reviewer_jwt="@$(kubectl create token vault -n vault)" \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
```

### Post-Incident

- Review token TTLs
- Update applications to handle re-authentication
- Monitor auth failure rates

---

## Storage Backend Issues

### Symptoms
- `vault_raft_storage_error_count` increasing
- Write failures
- Data inconsistency

### Severity
**Critical** - Data at risk

### Response Steps

#### 1. Check Storage Health

```bash
# Check Raft peers
kubectl exec -n vault vault-0 -- vault operator raft list-peers

# Check autopilot status
kubectl exec -n vault vault-0 -- vault operator raft autopilot state
```

#### 2. Check Disk Space

```bash
# Check PVC usage
kubectl get pvc -n vault
kubectl describe pvc vault-storage -n vault

# Check disk usage in pod
kubectl exec -n vault vault-0 -- df -h /vault/data
```

#### 3. If Disk is Full

```bash
# Expand PVC (if supported)
kubectl patch pvc vault-storage -n vault -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'

# Or clean up old audit logs
kubectl exec -n vault vault-0 -- find /vault/logs -name "*.log" -mtime +7 -delete
```

#### 4. If Data is Corrupted

⚠️ **WARNING**: This may result in data loss!

```bash
# Create backup first
kubectl exec -n vault vault-0 -- vault operator raft snapshot save /tmp/emergency-backup.snap
kubectl cp vault/vault-0:/tmp/emergency-backup.snap ./emergency-backup.snap

# Remove corrupted node
kubectl exec -n vault vault-0 -- vault operator raft remove-peer vault-2

# Delete and recreate pod
kubectl delete pod -n vault vault-2
kubectl wait --for=condition=ready pod/vault-2 -n vault

# Rejoin cluster
kubectl exec -n vault vault-2 -- vault operator raft join \
  https://vault-0.vault.svc.cluster.local:8200
```

### Post-Incident

- Review storage capacity planning
- Set up storage alerts
- Test backup/restore procedures

---

## Certificate Expiry

### Symptoms
- TLS handshake errors
- Certificate expiry warnings
- Clients cannot connect

### Severity
**Warning** - Service degradation

### Response Steps

#### 1. Check Certificate Expiry

```bash
# Check Vault server certificate
kubectl exec -n vault vault-0 -- openssl s_client -connect localhost:8200 -servername vault.vault.svc 2>/dev/null | openssl x509 -noout -dates

# Check client certificates (if using mTLS)
kubectl exec -n vault vault-0 -- vault list auth/cert/certs
```

#### 2. Renew Server Certificate

```bash
# Generate new certificate
kubectl exec -n vault vault-0 -- vault write pki/issue/vault \
  common_name=vault.vault.svc.cluster.local \
  alt_names="vault,vault.vault,vault.vault.svc,vault.vault.svc.cluster.local" \
  ttl=8760h

# Update TLS secret
kubectl create secret tls vault-tls \
  --cert=new-cert.pem \
  --key=new-key.pem \
  -n vault --dry-run=client -o yaml | kubectl apply -f -

# Restart Vault to pick up new certificate
kubectl rollout restart statefulset/vault -n vault
```

#### 3. Renew Client Certificates

```bash
# Issue new client certificate
kubectl exec -n vault vault-0 -- vault write pki/issue/client \
  common_name=proxy-api \
  ttl=2160h

# Update application secret
kubectl create secret tls proxy-api-client-tls \
  --cert=client-cert.pem \
  --key=client-key.pem \
  -n default
```

### Post-Incident

- Set up certificate expiry alerts (30, 14, 7 days)
- Automate certificate renewal
- Document certificate rotation procedures

---

## Secret Leak Response

### Symptoms
- Suspicious activity in audit logs
- Unauthorized access detected
- Secret values exposed

### Severity
**Critical** - Security incident

### Response Steps

#### 1. Identify Leaked Secrets

```bash
# Check audit logs
kubectl exec -n vault vault-0 -- cat /vault/logs/audit.log | grep -i "error\|unauthorized"

# Check access patterns
kubectl exec -n vault vault-0 -- vault read sys/metrics | jq '.data.token'
```

#### 2. Revoke Compromised Secrets

```bash
# Revoke specific secret
kubectl exec -n vault vault-0 -- vault kv metadata delete secret/proxy/credentials/compromised

# Revoke all leases for a path
kubectl exec -n vault vault-0 -- vault lease revoke -prefix -force secret/proxy/credentials/

# Revoke specific token
kubectl exec -n vault vault-0 -- vault token revoke <token-id>
```

#### 3. Rotate All Potentially Compromised Secrets

```bash
# Rotate database credentials
python -c "
import asyncio
from src.security.vault_rotation import DatabaseCredentialRotator
from src.security.vault_client import VaultClient

async def rotate():
    client = VaultClient(vault_addr='https://vault.vault.svc:8200')
    await client.connect()
    
    rotator = DatabaseCredentialRotator(client, db_host='postgres.default.svc')
    await rotator.rotate('main-db')
    await rotator.close()

asyncio.run(rotate())
"

# Rotate API keys
python -c "
import asyncio
from src.security.vault_rotation import ApiKeyRotator
from src.security.vault_client import VaultClient

async def rotate():
    client = VaultClient(vault_addr='https://vault.vault.svc:8200')
    await client.connect()
    
    rotator = ApiKeyRotator(client)
    await rotator.rotate_generic_api_key('proxy/api-keys/stripe')

asyncio.run(rotate())
"
```

#### 4. Review Access Policies

```bash
# Check who has access
kubectl exec -n vault vault-0 -- vault policy read proxy-api

# Update policies to be more restrictive
kubectl exec -n vault vault-0 -- vault policy write proxy-api - <<EOF
path "secret/data/proxy/database/main-db" {
  capabilities = ["read"]
}

path "secret/data/proxy/api-keys/stripe" {
  capabilities = ["read"]
}
EOF
```

#### 5. Enable Enhanced Auditing

```bash
# Enable file audit device with more detail
kubectl exec -n vault vault-0 -- vault audit enable file \
  file_path=/vault/logs/audit-detailed.log \
  log_raw=true
```

### Post-Incident

- Conduct security review
- Update incident response plan
- Train team on secret handling
- Consider implementing automated secret rotation

---

## Complete Cluster Failure

### Symptoms
- All Vault pods down
- Complete data loss
- Cannot recover from existing backups

### Severity
**Critical** - Complete service outage

### Response Steps

#### 1. Assess the Damage

```bash
# Check pod status
kubectl get pods -n vault

# Check PVC status
kubectl get pvc -n vault
kubectl describe pvc vault-storage -n vault

# Check events
kubectl get events -n vault --sort-by='.lastTimestamp'
```

#### 2. If Data is Recoverable

Follow [Backup & Restore procedures](#backup--restore) to restore from the latest backup.

#### 3. If Complete Data Loss

**Reinitialize Vault**:

```bash
# Delete existing PVCs (WARNING: Destructive!)
kubectl delete pvc -n vault --all

# Recreate PVCs
kubectl apply -f k8s/vault/storage.yaml

# Restart Vault
kubectl rollout restart statefulset/vault -n vault

# Wait for pods
kubectl wait --for=condition=ready pod/vault-0 -n vault

# Reinitialize
kubectl exec -n vault vault-0 -- vault operator init \
  -key-shares=5 -key-threshold=3 \
  -format=json > vault-init-new.json

# Unseal
for i in 0 1 2; do
  kubectl exec -n vault vault-$i -- vault operator unseal $(cat vault-init-new.json | jq -r ".unseal_keys_b64[$i]")
done
```

**Reconfigure Vault**:

```bash
# Run setup script
export VAULT_NAMESPACE=vault
export PROXY_API_NAMESPACE=default
./k8s/vault/setup.sh
```

**Restore Secrets from Secondary Source**:

If you have secrets documented elsewhere:

```bash
# Recreate secrets
kubectl exec -n vault vault-0 -- vault kv put secret/proxy/credentials/proxy-api \
  api_key="$(openssl rand -hex 32)" \
  secret="$(openssl rand -hex 32)"
```

#### 4. Verify Recovery

```bash
# Check Vault status
kubectl exec -n vault vault-0 -- vault status

# Test secret retrieval
kubectl exec -n vault vault-0 -- vault kv get secret/proxy/credentials/proxy-api

# Test application connectivity
kubectl logs -n default deployment/proxy-api --tail=50
```

### Post-Incident

- **Immediate**: Document what happened
- **24 hours**: Conduct blameless post-mortem
- **1 week**: Implement improvements
- **1 month**: Test disaster recovery procedures

### Prevention

- Regular automated backups (hourly)
- Multi-region backup storage
- Document all secrets in secure location
- Regular DR drills (quarterly)
- Monitor backup success/failure

---

## Contact Information

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-call Engineer | #vault-oncall | 0 min |
| Vault Team Lead | vault-lead@example.com | 15 min |
| Security Team | security@example.com | 30 min |
| Engineering Manager | eng-manager@example.com | 1 hour |

## Useful Links

- [Vault Status Page](https://status.hashicorp.com)
- [Vault Documentation](https://www.vaultproject.io/docs)
- [Vault API Docs](https://www.vaultproject.io/api-docs)
- [Internal Wiki](https://wiki.internal/vault)