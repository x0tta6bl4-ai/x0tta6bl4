#!/bin/bash
#
# Vault Restore Script for Raft Storage
#
# This script restores Vault from a Raft snapshot.
# WARNING: This will overwrite existing data. Use with caution!
#
# Usage: ./restore.sh <backup-file> [--force]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VAULT_NAMESPACE="${VAULT_NAMESPACE:-vault}"
VAULT_POD="${VAULT_NAMESPACE:-vault-0}"
FORCE=false

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Parse arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup-file> [--force]"
    echo ""
    echo "Arguments:"
    echo "  backup-file    Path to the backup snapshot file"
    echo "  --force        Skip confirmation prompt"
    exit 1
fi

BACKUP_FILE="$1"
shift

while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}      Vault Restore Script             ${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo -e "${RED}WARNING: This will restore Vault from a backup.${NC}"
echo -e "${RED}All current data will be replaced!${NC}"
echo ""

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Verify checksum if available
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [ -f "$CHECKSUM_FILE" ]; then
    log_step "Verifying backup checksum..."
    cd $(dirname $BACKUP_FILE)
    if sha256sum -c $(basename $CHECKSUM_FILE); then
        log_info "Checksum verified"
    else
        log_error "Checksum verification failed!"
        exit 1
    fi
    cd - > /dev/null
else
    log_warn "Checksum file not found. Proceeding without verification."
fi

# Confirmation prompt
if [ "$FORCE" != "true" ]; then
    echo ""
    read -p "Are you sure you want to restore Vault from $BACKUP_FILE? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi
fi

# Check prerequisites
log_step "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed"
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster"
    exit 1
fi

# Check Vault status
log_step "Checking Vault status..."
if ! kubectl get pod ${VAULT_POD} -n ${VAULT_NAMESPACE} &> /dev/null; then
    log_error "Vault pod ${VAULT_POD} not found in namespace ${VAULT_NAMESPACE}"
    exit 1
fi

# Check if Vault is initialized
VAULT_STATUS=$(kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status -format=json 2>/dev/null || echo '{}')
INIT_STATUS=$(echo "$VAULT_STATUS" | jq -r '.initialized // false')
SEAL_STATUS=$(echo "$VAULT_STATUS" | jq -r '.sealed // true')

if [ "$INIT_STATUS" != "true" ]; then
    log_error "Vault is not initialized. Cannot restore."
    exit 1
fi

# If Vault is not sealed, we need to seal it first
if [ "$SEAL_STATUS" != "true" ]; then
    log_warn "Vault is currently unsealed. It must be sealed before restore."
    
    if [ "$FORCE" != "true" ]; then
        read -p "Seal Vault now? (yes/no): " CONFIRM
        if [ "$CONFIRM" != "yes" ]; then
            log_info "Restore cancelled"
            exit 0
        fi
    fi
    
    log_step "Sealing Vault..."
    kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault operator seal
    log_info "Vault sealed"
fi

# Copy backup to pod
log_step "Copying backup to Vault pod..."
BACKUP_FILENAME=$(basename $BACKUP_FILE)
kubectl cp $BACKUP_FILE ${VAULT_NAMESPACE}/${VAULT_POD}:/tmp/${BACKUP_FILENAME}
log_info "Backup copied to pod"

# Perform restore
log_step "Restoring Vault from snapshot..."
kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- \
    vault operator raft snapshot restore /tmp/${BACKUP_FILENAME}
log_info "Restore completed"

# Unseal Vault
log_step "Unsealing Vault..."

# Check if auto-unseal is configured
SEAL_TYPE=$(kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status -format=json 2>/dev/null | jq -r '.seal_type // "shamir"')

if [ "$SEAL_TYPE" = "awskms" ] || [ "$SEAL_TYPE" = "gcpckms" ] || [ "$SEAL_TYPE" = "azurekeyvault" ]; then
    log_info "Auto-unseal is configured. Vault should unseal automatically."
    
    # Wait for auto-unseal
    for i in {1..30}; do
        sleep 2
        SEAL_STATUS=$(kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status -format=json 2>/dev/null | jq -r '.sealed // true')
        if [ "$SEAL_STATUS" = "false" ]; then
            log_info "Vault is unsealed"
            break
        fi
    done
else
    # Manual unseal with Shamir keys
    log_info "Manual unseal required. Please provide unseal keys."
    
    if [ -f vault-init.json ]; then
        log_info "Found vault-init.json, using saved keys..."
        UNSEAL_KEYS=$(cat vault-init.json | jq -r '.unseal_keys_b64[]')
        KEY_COUNT=0
        
        for KEY in $UNSEAL_KEYS; do
            if [ $KEY_COUNT -lt 3 ]; then
                kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault operator unseal "$KEY" > /dev/null
                KEY_COUNT=$((KEY_COUNT + 1))
            fi
        done
        log_info "Vault unsealed"
    else
        log_warn "vault-init.json not found. Please unseal Vault manually."
        log_info "Run: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault operator unseal <key>"
    fi
fi

# Verify restore
log_step "Verifying restore..."
sleep 5

VAULT_STATUS=$(kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status 2>/dev/null || true)
if echo "$VAULT_STATUS" | grep -q "Sealed.*false"; then
    log_info "Vault is unsealed and operational"
else
    log_warn "Vault status check failed. Please verify manually."
fi

# Cleanup
log_step "Cleaning up..."
kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- rm -f /tmp/${BACKUP_FILENAME}

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      Restore Complete!                ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Vault has been restored from: $BACKUP_FILE"
echo ""
echo "Next steps:"
echo "  1. Verify Vault status: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status"
echo "  2. Check secrets: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault kv list secret/"
echo "  3. Test application connectivity"
echo ""
echo "If you encounter issues, you may need to:"
echo "  - Restart Vault pods: kubectl rollout restart statefulset/vault -n ${VAULT_NAMESPACE}"
echo "  - Check logs: kubectl logs -n ${VAULT_NAMESPACE} ${VAULT_POD}"
echo ""

exit 0