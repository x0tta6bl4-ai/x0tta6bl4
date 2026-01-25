#!/bin/bash
# Production Restore Script
# Дата: 2026-01-07
# Версия: 3.4.0-fixed2

set -euo pipefail

BACKUP_FILE="${1:-}"
NAMESPACE="${NAMESPACE:-x0tta6bl4-staging}"
RESTORE_DIR="restore_$(date +%Y%m%d_%H%M%S)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check arguments
if [ -z "$BACKUP_FILE" ]; then
    error "Usage: $0 <backup-file.tar.gz>"
    error "Example: $0 backups/20260107_120000.tar.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Check prerequisites
if ! command -v kubectl &> /dev/null; then
    error "kubectl not found"
    exit 1
fi

log "Starting restore from: $BACKUP_FILE"

# Extract backup
log "Extracting backup..."
mkdir -p "$RESTORE_DIR"
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR" || {
    error "Failed to extract backup"
    exit 1
}

EXTRACTED_DIR=$(find "$RESTORE_DIR" -mindepth 1 -maxdepth 1 -type d | head -1)

if [ -z "$EXTRACTED_DIR" ]; then
    error "Backup extraction failed or backup is empty"
    exit 1
fi

log "Backup extracted to: $EXTRACTED_DIR"

# Verify backup contents
if [ ! -f "$EXTRACTED_DIR/k8s-resources.yaml" ]; then
    error "Backup appears to be invalid (missing k8s-resources.yaml)"
    exit 1
fi

# Confirm restore
read -p "This will restore resources to namespace '$NAMESPACE'. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    log "Restore cancelled"
    exit 0
fi

# Create namespace if it doesn't exist
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    log "Creating namespace: $NAMESPACE"
    kubectl create namespace "$NAMESPACE"
fi

# Restore Kubernetes resources
log "Restoring Kubernetes resources..."
kubectl apply -f "$EXTRACTED_DIR/k8s-resources.yaml" -n "$NAMESPACE" || warn "Some resources failed to restore"

# Restore ConfigMaps
if [ -f "$EXTRACTED_DIR/configmaps.yaml" ]; then
    log "Restoring ConfigMaps..."
    kubectl apply -f "$EXTRACTED_DIR/configmaps.yaml" -n "$NAMESPACE" || warn "ConfigMaps restore failed"
fi

# Restore Secrets (metadata only, actual secrets need to be recreated)
if [ -f "$EXTRACTED_DIR/secrets.yaml" ]; then
    warn "Secrets metadata restored, but actual secret values need to be recreated manually"
    kubectl apply -f "$EXTRACTED_DIR/secrets.yaml" -n "$NAMESPACE" || warn "Secrets restore failed"
fi

# Restore PersistentVolumeClaims
if [ -f "$EXTRACTED_DIR/pvcs.yaml" ]; then
    log "Restoring PersistentVolumeClaims..."
    kubectl apply -f "$EXTRACTED_DIR/pvcs.yaml" -n "$NAMESPACE" || warn "PVCs restore failed"
fi

# Restore ServiceAccounts
if [ -f "$EXTRACTED_DIR/serviceaccounts.yaml" ]; then
    log "Restoring ServiceAccounts..."
    kubectl apply -f "$EXTRACTED_DIR/serviceaccounts.yaml" -n "$NAMESPACE" || warn "ServiceAccounts restore failed"
fi

# Restore Helm deployment (if Helm values exist)
if [ -f "$EXTRACTED_DIR/values.yaml" ] && command -v helm &> /dev/null; then
    log "Restoring Helm deployment..."
    helm upgrade x0tta6bl4-staging ./helm/x0tta6bl4 \
      -f "$EXTRACTED_DIR/values.yaml" \
      -n "$NAMESPACE" \
      --install || warn "Helm restore failed"
fi

# Verify restore
log "Verifying restore..."
sleep 10

PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
RUNNING=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)

log "Pods: $RUNNING/$PODS Running"

# Check health
if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    log "✅ Health check passed"
else
    warn "⚠️ Health check failed (service may still be starting)"
fi

# Cleanup
log "Cleaning up temporary files..."
rm -rf "$RESTORE_DIR"

log "Restore completed"
log "Verify with: kubectl get all -n $NAMESPACE"

