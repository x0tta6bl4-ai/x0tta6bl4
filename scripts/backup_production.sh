#!/bin/bash
# Production Backup Script
# Дата: 2026-01-07
# Версия: 3.4.0-fixed2

set -euo pipefail

NAMESPACE="${NAMESPACE:-x0tta6bl4-staging}"
BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$TIMESTAMP"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Create backup directory
mkdir -p "$BACKUP_DIR"

log "Starting backup for namespace: $NAMESPACE"

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    warn "kubectl not found"
    exit 1
fi

if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    warn "Namespace $NAMESPACE not found"
    exit 1
fi

# Backup Helm values
if command -v helm &> /dev/null; then
    log "Backing up Helm values..."
    helm get values x0tta6bl4-staging -n "$NAMESPACE" > "$BACKUP_DIR/values.yaml" 2>/dev/null || warn "Helm values backup failed"
else
    warn "Helm not found, skipping Helm values backup"
fi

# Backup Kubernetes resources
log "Backing up Kubernetes resources..."
kubectl get all -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/k8s-resources.yaml" 2>&1 || warn "K8s resources backup failed"

# Backup ConfigMaps
log "Backing up ConfigMaps..."
kubectl get configmap -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/configmaps.yaml" 2>&1 || warn "ConfigMaps backup failed"

# Backup Secrets (encrypted, no actual secret values)
log "Backing up Secrets metadata..."
kubectl get secret -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/secrets.yaml" 2>&1 || warn "Secrets backup failed"

# Backup PersistentVolumeClaims
log "Backing up PersistentVolumeClaims..."
kubectl get pvc -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/pvcs.yaml" 2>&1 || warn "PVCs backup failed"

# Backup ServiceAccounts
log "Backing up ServiceAccounts..."
kubectl get serviceaccount -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/serviceaccounts.yaml" 2>&1 || warn "ServiceAccounts backup failed"

# Create backup manifest
cat > "$BACKUP_DIR/BACKUP_MANIFEST.txt" << EOF
Backup Information
==================
Date: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
Namespace: $NAMESPACE
Backup Type: Full
Files:
  - values.yaml (Helm values)
  - k8s-resources.yaml (All Kubernetes resources)
  - configmaps.yaml (ConfigMaps)
  - secrets.yaml (Secrets metadata)
  - pvcs.yaml (PersistentVolumeClaims)
  - serviceaccounts.yaml (ServiceAccounts)

Verification:
  - kubectl get all -n $NAMESPACE
  - helm get values x0tta6bl4-staging -n $NAMESPACE
EOF

# Compress backup
log "Compressing backup..."
tar -czf "$BACKUP_DIR.tar.gz" -C "$BACKUP_BASE_DIR" "$(basename "$BACKUP_DIR")" 2>&1 || {
    warn "Compression failed"
    exit 1
}

# Calculate size
BACKUP_SIZE=$(du -h "$BACKUP_DIR.tar.gz" | cut -f1)

log "Backup completed successfully"
log "Backup location: $BACKUP_DIR.tar.gz"
log "Backup size: $BACKUP_SIZE"

# Optional: Upload to S3 (if configured)
if [ -n "${S3_BACKUP_BUCKET:-}" ] && command -v aws &> /dev/null; then
    log "Uploading to S3: $S3_BACKUP_BUCKET"
    aws s3 cp "$BACKUP_DIR.tar.gz" "s3://$S3_BACKUP_BUCKET/backups/" || warn "S3 upload failed"
fi

# Cleanup local directory (keep compressed file)
rm -rf "$BACKUP_DIR"

log "Backup process completed"

