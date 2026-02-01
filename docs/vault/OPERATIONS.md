# Vault Operations Guide

This guide covers the operational aspects of running HashiCorp Vault in production on Kubernetes.

## Table of Contents

- [Daily Operations](#daily-operations)
- [Monitoring & Alerting](#monitoring--alerting)
- [Backup & Restore](#backup--restore)
- [Secret Rotation](#secret-rotation)
- [Incident Response](#incident-response)
- [Troubleshooting](#troubleshooting)

## Daily Operations

### Check Vault Status

```bash
# Check Vault status
kubectl exec -n vault vault-0 -- vault status

# Check all pods
kubectl get pods -n vault

# Check logs
kubectl logs -n vault vault-0 --tail=100
```

### View Secrets

```bash
# List all secrets
kubectl exec -n vault vault-0 -- vault kv list secret/

# List proxy secrets
kubectl exec -n vault vault-0 -- vault kv list secret/proxy

# Read a specific secret
kubectl exec -n vault vault-0 -- vault kv get secret/proxy/credentials/proxy-api
```

### Manage Policies

```bash
# List policies
kubectl exec -n vault vault-0 -- vault policy list

# Read a policy
kubectl exec -n vault vault-0 -- vault policy read proxy-api

# Update a policy
kubectl exec -n vault vault-0 -- vault policy write proxy-api - <<EOF
path "secret/data/proxy/*" {
  capabilities = ["read", "list"]
}
EOF
```

### Manage Auth Methods

```bash
# List auth methods
kubectl exec -n vault vault-0 -- vault auth list

# Check Kubernetes auth configuration
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/config

# List Kubernetes roles
kubectl exec -n vault vault-0 -- vault list auth/kubernetes/role
```

## Monitoring & Alerting

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `vault_core_unsealed` | Vault seal status | = 0 (Critical) |
| `vault_raft_leader` | Leader existence | = 0 (Critical) |
| `vault_core_handle_request_latency_seconds` | Request latency | > 1s (Warning) |
| `vault_expire_num_leases` | Active leases | > 10000 (Warning) |
| `vault_runtime_alloc_bytes` | Memory usage | > 80% (Warning) |

### Prometheus Queries

```promql
# Vault is sealed
vault_core_unsealed == 0

# High request latency
histogram_quantile(0.99, rate(vault_core_handle_request_latency_seconds_bucket[5m])) > 1

# Authentication failures
rate(vault_core_auth_request_failure_count[5m]) > 0.1

# Token expiry warning
vault_token_expiry_seconds < 3600
```

### Grafana Dashboard

Import the dashboard from `k8s/monitoring/grafana-vault-dashboard.json` into Grafana.

Access the dashboard at: `https://grafana.example.com/d/vault-cluster`

## Backup & Restore

### Automated Backups

Backups are configured to run automatically via CronJob:

```bash
# View backup CronJob
kubectl get cronjob -n vault vault-backup

# View backup history
kubectl get jobs -n vault | grep vault-backup
```

### Manual Backup

```bash
# Create a manual backup
cd k8s/vault/backup
./backup.sh --upload-s3 --s3-bucket my-vault-backups
```

### Restore from Backup

⚠️ **WARNING**: This will overwrite all current Vault data!

```bash
# Restore from a backup
cd k8s/vault/backup
./restore.sh /path/to/vault-backup-20240130_120000.snap --force
```

### Disaster Recovery

1. **Identify the issue**
   ```bash
   kubectl exec -n vault vault-0 -- vault status
   kubectl logs -n vault vault-0 --tail=500
   ```

2. **If Vault is corrupted, restore from backup**
   ```bash
   # Seal Vault
   kubectl exec -n vault vault-0 -- vault operator seal
   
   # Restore from backup
   ./restore.sh <backup-file>
   ```

3. **If a node is lost, rejoin to cluster**
   ```bash
   kubectl exec -n vault vault-1 -- vault operator raft join \
     https://vault-0.vault.svc.cluster.local:8200
   ```

## Secret Rotation

### Database Credentials

```python
from src.security.vault_rotation import DatabaseCredentialRotator
from src.security.vault_client import VaultClient

client = VaultClient(vault_addr="https://vault.vault.svc:8200")
await client.connect()

rotator = DatabaseCredentialRotator(
    client,
    db_host="postgres.default.svc",
    admin_username="postgres",
    admin_password="admin-password"
)

result = await rotator.rotate("main-db")
print(f"Rotation status: {result.status}")
```

### API Keys

```python
from src.security.vault_rotation import ApiKeyRotator

rotator = ApiKeyRotator(client)
result = await rotator.rotate_generic_api_key("proxy/api-keys/stripe")
```

### Scheduled Rotation

```python
from src.security.vault_rotation import RotationScheduler

scheduler = RotationScheduler(client)
scheduler.schedule_database_rotation("main-db", days=7)
scheduler.schedule_api_key_rotation("stripe", days=30)

await scheduler.start()
```

## Incident Response

### Vault is Sealed

**Symptoms**: Applications cannot retrieve secrets, `vault_core_unsealed == 0`

**Response**:
1. Check why Vault sealed (auto-seal on shutdown, manual seal, etc.)
2. If using auto-unseal (KMS), check KMS connectivity
3. If using Shamir, unseal with unseal keys:
   ```bash
   kubectl exec -n vault vault-0 -- vault operator unseal <key>
   ```

**Prevention**:
- Enable auto-unseal with cloud KMS
- Monitor for seal events
- Document unseal key locations securely

### Vault is Down

**Symptoms**: Pods not ready, connection refused

**Response**:
1. Check pod status:
   ```bash
   kubectl get pods -n vault
   kubectl describe pod -n vault vault-0
   ```

2. Check logs:
   ```bash
   kubectl logs -n vault vault-0 --previous
   ```

3. If persistent volume issue:
   ```bash
   kubectl get pvc -n vault
   kubectl describe pvc vault-storage -n vault
   ```

4. If needed, restore from backup

### Leader Election Issues

**Symptoms**: No leader, split-brain, `vault_raft_leader == 0`

**Response**:
1. Check Raft peers:
   ```bash
   kubectl exec -n vault vault-0 -- vault operator raft list-peers
   ```

2. If a node is not joined:
   ```bash
   kubectl exec -n vault vault-1 -- vault operator raft join \
     https://vault-0.vault.svc.cluster.local:8200
   ```

3. If leader is stuck, step down:
   ```bash
   kubectl exec -n vault vault-0 -- vault operator step-down
   ```

### High Latency

**Symptoms**: Slow secret retrieval, timeout errors

**Response**:
1. Check resource usage:
   ```bash
   kubectl top pod -n vault
   ```

2. Check storage backend:
   ```bash
   kubectl exec -n vault vault-0 -- vault debug -output=/tmp/debug
   ```

3. Scale resources if needed:
   ```bash
   kubectl patch statefulset vault -n vault -p '{"spec":{"template":{"spec":{"containers":[{"name":"vault","resources":{"limits":{"cpu":"2000m","memory":"2Gi"}}}]}}}}'
   ```

## Troubleshooting

### Common Issues

#### Authentication Failures

```bash
# Check Kubernetes auth configuration
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/config

# Check role configuration
kubectl exec -n vault vault-0 -- vault read auth/kubernetes/role/proxy-api

# Test authentication manually
kubectl run test-auth --rm -it --image=alpine/curl --restart=Never -- \
  curl -k -X POST https://vault.vault.svc:8200/v1/auth/kubernetes/login \
  -d '{"role":"proxy-api","jwt":"<service-account-token>"}'
```

#### Permission Denied

```bash
# Check token capabilities
kubectl exec -n vault vault-0 -- vault token capabilities <token> secret/data/proxy/test

# Check policy
kubectl exec -n vault vault-0 -- vault policy read proxy-api
```

#### Certificate Errors

```bash
# Check TLS certificates
kubectl exec -n vault vault-0 -- openssl s_client -connect localhost:8200 -showcerts

# Renew certificates if needed
kubectl exec -n vault vault-0 -- vault write pki/issue/vault \
  common_name=vault.vault.svc.cluster.local
```

### Debug Commands

```bash
# Get Vault configuration
kubectl exec -n vault vault-0 -- vault read sys/config/state/sanitized

# Get Raft configuration
kubectl exec -n vault vault-0 -- vault operator raft configuration

# Get audit log status
kubectl exec -n vault vault-0 -- vault audit list

# Generate debug bundle
kubectl exec -n vault vault-0 -- vault debug -duration=30s -output=/tmp/vault-debug
kubectl cp vault/vault-0:/tmp/vault-debug ./vault-debug
```

### Support Resources

- [Vault Documentation](https://www.vaultproject.io/docs)
- [Vault API Documentation](https://www.vaultproject.io/api-docs)
- [Vault GitHub Issues](https://github.com/hashicorp/vault/issues)
- [Vault Discussion Forum](https://discuss.hashicorp.com/c/vault)

## Maintenance Windows

### Regular Maintenance

- **Daily**: Check Vault status and alerts
- **Weekly**: Review audit logs, check certificate expiry
- **Monthly**: Test backup/restore procedures, rotate secrets
- **Quarterly**: Review policies, update Vault version

### Upgrade Procedure

1. **Pre-upgrade**
   - Create backup
   - Review changelog
   - Test in staging

2. **Upgrade**
   ```bash
   helm upgrade vault hashicorp/vault \
     --namespace vault \
     --values k8s/vault/helm-values.yaml \
     --set server.image.tag=1.16.0
   ```

3. **Post-upgrade**
   - Verify status
   - Check logs for errors
   - Test secret retrieval

## Contact

For operational support:
- On-call: #vault-oncall
- Slack: #vault-support
- Email: vault-ops@example.com