# Disaster Recovery Plan
**Дата:** 2026-01-07  
**Версия:** x0tta6bl4 v3.4.0-fixed2  
**Статус:** ⏳ В процессе подготовки

---

## 📋 Overview

**Цель:** План восстановления после катастрофических сбоев

**Сценарии:**
- Complete cluster failure
- Data loss
- Security breach
- Network partition
- Storage failure

---

## 🎯 Recovery Objectives

### RTO (Recovery Time Objective)
- **Critical Services:** <1 hour
- **Standard Services:** <4 hours
- **Non-Critical:** <24 hours

### RPO (Recovery Point Objective)
- **Critical Data:** <15 minutes
- **Standard Data:** <1 hour
- **Non-Critical Data:** <24 hours

---

## 🔄 Backup Strategy

### Configuration Backups

**Daily Backups:**
```bash
# Backup Helm values
helm get values x0tta6bl4-staging -n x0tta6bl4-staging > backups/values-$(date +%Y%m%d).yaml

# Backup Kubernetes resources
kubectl get all -n x0tta6bl4-staging -o yaml > backups/k8s-resources-$(date +%Y%m%d).yaml

# Backup ConfigMaps and Secrets (encrypted)
kubectl get configmap,secret -n x0tta6bl4-staging -o yaml > backups/config-$(date +%Y%m%d).yaml
```

**Storage:** Encrypted S3 bucket or secure storage

### Application State Backups

**What to backup:**
- Mesh network topology
- Node configurations
- Security certificates
- ML model states (if applicable)

**Frequency:** Every 6 hours

---

## 🚨 Disaster Scenarios

### Scenario 1: Complete Cluster Failure

**Symptoms:**
- All pods down
- Kubernetes API unavailable
- No connectivity

**Recovery Steps:**
1. **Assess damage:**
   - Check cluster status
   - Verify data availability
   - Check backup integrity

2. **Restore cluster:**
   ```bash
   # Recreate cluster (if needed)
   kind create cluster --name x0tta6bl4-staging
   
   # Restore from backup
   kubectl apply -f backups/k8s-resources-YYYYMMDD.yaml
   ```

3. **Restore application:**
   ```bash
   # Deploy from Helm
   helm install x0tta6bl4-staging ./helm/x0tta6bl4 \
     -f backups/values-YYYYMMDD.yaml \
     -n x0tta6bl4-staging
   ```

4. **Verify:**
   ```bash
   kubectl get pods -n x0tta6bl4-staging
   curl http://localhost:8080/health
   ```

**RTO:** <1 hour  
**RPO:** <15 minutes (from last backup)

---

### Scenario 2: Data Loss

**Symptoms:**
- Persistent volumes corrupted
- Database data missing
- Configuration lost

**Recovery Steps:**
1. **Stop writes:**
   ```bash
   kubectl scale deployment/x0tta6bl4-staging --replicas=0 -n x0tta6bl4-staging
   ```

2. **Restore from backup:**
   ```bash
   # Restore volumes
   kubectl apply -f backups/persistent-volumes-YYYYMMDD.yaml
   
   # Restore data
   # (depends on storage solution)
   ```

3. **Verify data integrity:**
   ```bash
   # Check data consistency
   kubectl exec -n x0tta6bl4-staging <pod-name> -- verify-data
   ```

4. **Resume operations:**
   ```bash
   kubectl scale deployment/x0tta6bl4-staging --replicas=5 -n x0tta6bl4-staging
   ```

**RTO:** <2 hours  
**RPO:** <1 hour (from last backup)

---

### Scenario 3: Security Breach

**Symptoms:**
- Unauthorized access detected
- Certificates compromised
- Suspicious activity

**Recovery Steps:**
1. **Isolate affected systems:**
   ```bash
   # Scale down to 0
   kubectl scale deployment/x0tta6bl4-staging --replicas=0 -n x0tta6bl4-staging
   ```

2. **Rotate credentials:**
   ```bash
   # Rotate certificates
   kubectl delete secret x0tta6bl4-certs -n x0tta6bl4-staging
   # Generate new certificates
   ```

3. **Audit logs:**
   ```bash
   # Collect logs
   kubectl logs -n x0tta6bl4-staging --all-containers > security-audit-$(date +%Y%m%d).log
   ```

4. **Restore from clean backup:**
   ```bash
   # Restore from pre-breach backup
   helm upgrade x0tta6bl4-staging ./helm/x0tta6bl4 \
     -f backups/values-pre-breach.yaml \
     -n x0tta6bl4-staging
   ```

5. **Verify security:**
   ```bash
   # Security scan
   kubectl exec -n x0tta6bl4-staging <pod-name> -- security-scan
   ```

**RTO:** <2 hours  
**RPO:** <15 minutes (from pre-breach backup)

---

### Scenario 4: Network Partition

**Symptoms:**
- Pods can't communicate
- Mesh network split
- Service discovery failing

**Recovery Steps:**
1. **Identify partition:**
   ```bash
   # Check pod connectivity
   kubectl exec -n x0tta6bl4-staging <pod-1> -- ping <pod-2-ip>
   ```

2. **Restore network:**
   ```bash
   # Restart network components
   kubectl delete pods -n x0tta6bl4-staging -l app=x0tta6bl4-staging
   ```

3. **Verify mesh convergence:**
   ```bash
   curl -s http://localhost:8080/mesh/status | jq .convergence_time
   ```

**RTO:** <30 minutes  
**RPO:** N/A (no data loss)

---

## 🔧 Recovery Tools

### Backup Script

**File:** `scripts/backup_production.sh`

```bash
#!/bin/bash
# Production backup script

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup Helm values
helm get values x0tta6bl4-staging -n x0tta6bl4-staging > "$BACKUP_DIR/values.yaml"

# Backup Kubernetes resources
kubectl get all -n x0tta6bl4-staging -o yaml > "$BACKUP_DIR/k8s-resources.yaml"

# Backup ConfigMaps and Secrets
kubectl get configmap,secret -n x0tta6bl4-staging -o yaml > "$BACKUP_DIR/config.yaml"

# Compress
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"

# Upload to S3 (if configured)
# aws s3 cp "$BACKUP_DIR.tar.gz" s3://x0tta6bl4-backups/

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### Restore Script

**File:** `scripts/restore_production.sh`

```bash
#!/bin/bash
# Production restore script

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file.tar.gz>"
    exit 1
fi

# Extract backup
tar -xzf "$BACKUP_FILE"
BACKUP_DIR=$(basename "$BACKUP_FILE" .tar.gz)

# Restore Kubernetes resources
kubectl apply -f "$BACKUP_DIR/k8s-resources.yaml"

# Restore configuration
kubectl apply -f "$BACKUP_DIR/config.yaml"

# Restore Helm deployment
helm upgrade x0tta6bl4-staging ./helm/x0tta6bl4 \
  -f "$BACKUP_DIR/values.yaml" \
  -n x0tta6bl4-staging

echo "Restore completed from: $BACKUP_FILE"
```

---

## ✅ Testing

### Disaster Recovery Test

**Frequency:** Quarterly

**Test Scenarios:**
1. Simulate cluster failure
2. Test backup restoration
3. Verify RTO/RPO
4. Document lessons learned

**Test Checklist:**
- [ ] Backup integrity verified
- [ ] Restore procedure tested
- [ ] RTO within target
- [ ] RPO within target
- [ ] Data integrity verified
- [ ] Services operational after restore

---

## 📝 Documentation

### Backup Log

**File:** `backups/BACKUP_LOG.md`

**Fields:**
- Date/Time
- Backup Type (Full/Incremental)
- Size
- Location
- Status
- Verification

### Recovery Log

**File:** `backups/RECOVERY_LOG.md`

**Fields:**
- Incident ID
- Date/Time
- Scenario
- Recovery Steps
- RTO Achieved
- RPO Achieved
- Issues Encountered
- Lessons Learned

---

**Статус:** ⏳ В процессе подготовки  
**Следующий шаг:** Create backup/restore scripts and test procedures

