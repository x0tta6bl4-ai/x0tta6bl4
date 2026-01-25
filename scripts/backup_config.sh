#!/bin/bash
# Configuration backup script
# Backs up Kubernetes configurations and Helm values

set -e

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
NAMESPACE=${1:-"x0tta6bl4"}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Configuration Backup Script                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "❌ helm not found"; exit 1; }

# Create backup directory
mkdir -p "$BACKUP_DIR"
echo "📁 Backup directory: $BACKUP_DIR"
echo ""

# Backup Kubernetes resources
echo "📦 Backing up Kubernetes resources..."
kubectl get all -n $NAMESPACE -o yaml > "$BACKUP_DIR/kubernetes-resources.yaml" 2>/dev/null || echo "⚠️  No resources found in namespace"
kubectl get configmap -n $NAMESPACE -o yaml > "$BACKUP_DIR/configmaps.yaml" 2>/dev/null || true
kubectl get secret -n $NAMESPACE -o yaml > "$BACKUP_DIR/secrets.yaml" 2>/dev/null || true
kubectl get pvc -n $NAMESPACE -o yaml > "$BACKUP_DIR/persistentvolumeclaims.yaml" 2>/dev/null || true

# Backup Helm release
echo "📋 Backing up Helm release..."
helm get values x0tta6bl4 -n $NAMESPACE > "$BACKUP_DIR/helm-values.yaml" 2>/dev/null || echo "⚠️  Helm release not found"
helm get manifest x0tta6bl4 -n $NAMESPACE > "$BACKUP_DIR/helm-manifest.yaml" 2>/dev/null || true

# Backup Helm chart
echo "📄 Backing up Helm chart..."
if [ -d "./helm/x0tta6bl4" ]; then
    cp -r ./helm/x0tta6bl4 "$BACKUP_DIR/helm-chart" 2>/dev/null || true
fi

# Backup Terraform state (if exists)
echo "🏗️  Backing up Terraform state..."
if [ -d "./terraform" ]; then
    cp -r ./terraform "$BACKUP_DIR/terraform" 2>/dev/null || true
fi

# Create backup info
cat > "$BACKUP_DIR/backup-info.txt" <<EOF
Backup Information
==================
Date: $(date)
Namespace: $NAMESPACE
Kubernetes Version: $(kubectl version --short 2>/dev/null | grep Server || echo "N/A")
Helm Version: $(helm version --short 2>/dev/null || echo "N/A")
EOF

# Create archive
echo "📦 Creating backup archive..."
cd "$(dirname "$BACKUP_DIR")"
tar -czf "$(basename "$BACKUP_DIR").tar.gz" "$(basename "$BACKUP_DIR")" 2>/dev/null || true

echo ""
echo "✅ Backup complete!"
echo "   Location: $BACKUP_DIR"
echo "   Archive: $(dirname "$BACKUP_DIR")/$(basename "$BACKUP_DIR").tar.gz"

