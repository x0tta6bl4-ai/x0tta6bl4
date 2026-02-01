#!/bin/bash
#
# Vault Backup Script for Raft Storage
#
# This script creates snapshots of Vault's Raft storage and uploads them
# to a remote storage backend (S3, GCS, Azure Blob).
#
# Usage: ./backup.sh [--retention-days 30] [--upload-s3]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VAULT_NAMESPACE="${VAULT_NAMESPACE:-vault}"
VAULT_POD="${VAULT_POD:-vault-0}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/vault-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="vault-backup-${TIMESTAMP}.snap"

# Remote storage configuration
UPLOAD_S3="${UPLOAD_S3:-false}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-vault-backups}"
UPLOAD_GCS="${UPLOAD_GCS:-false}"
GCS_BUCKET="${GCS_BUCKET:-}"
UPLOAD_AZURE="${UPLOAD_AZURE:-false}"
AZURE_CONTAINER="${AZURE_CONTAINER:-}"

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
while [[ $# -gt 0 ]]; do
    case $1 in
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --upload-s3)
            UPLOAD_S3="true"
            shift
            ;;
        --s3-bucket)
            S3_BUCKET="$2"
            shift 2
            ;;
        --upload-gcs)
            UPLOAD_GCS="true"
            shift
            ;;
        --gcs-bucket)
            GCS_BUCKET="$2"
            shift 2
            ;;
        --upload-azure)
            UPLOAD_AZURE="true"
            shift
            ;;
        --azure-container)
            AZURE_CONTAINER="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --retention-days DAYS    Number of days to keep backups (default: 30)"
            echo "  --upload-s3              Upload to S3"
            echo "  --s3-bucket BUCKET       S3 bucket name"
            echo "  --upload-gcs             Upload to Google Cloud Storage"
            echo "  --gcs-bucket BUCKET      GCS bucket name"
            echo "  --upload-azure           Upload to Azure Blob Storage"
            echo "  --azure-container NAME   Azure container name"
            echo "  --help                   Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      Vault Backup Script              ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

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

# Check if Vault is initialized and unsealed
VAULT_STATUS=$(kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status -format=json 2>/dev/null || echo '{}')
INIT_STATUS=$(echo "$VAULT_STATUS" | jq -r '.initialized // false')
SEAL_STATUS=$(echo "$VAULT_STATUS" | jq -r '.sealed // true')

if [ "$INIT_STATUS" != "true" ]; then
    log_error "Vault is not initialized"
    exit 1
fi

if [ "$SEAL_STATUS" = "true" ]; then
    log_error "Vault is sealed. Cannot create backup."
    exit 1
fi

log_info "Vault is ready for backup"

# Create backup directory
log_step "Creating backup directory..."
mkdir -p "${BACKUP_DIR}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

# Create Raft snapshot
log_step "Creating Raft snapshot..."
kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- \
    vault operator raft snapshot save /tmp/${BACKUP_FILE}

# Copy snapshot from pod
log_step "Copying snapshot from Vault pod..."
kubectl cp ${VAULT_NAMESPACE}/${VAULT_POD}:/tmp/${BACKUP_FILE} ${BACKUP_PATH}

# Verify backup
log_step "Verifying backup..."
if [ -f "${BACKUP_PATH}" ]; then
    BACKUP_SIZE=$(du -h ${BACKUP_PATH} | cut -f1)
    log_info "Backup created successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    log_error "Backup file not found"
    exit 1
fi

# Calculate checksum
log_step "Calculating checksum..."
cd ${BACKUP_DIR}
sha256sum ${BACKUP_FILE} > ${BACKUP_FILE}.sha256
cd - > /dev/null
log_info "Checksum saved to ${BACKUP_FILE}.sha256"

# Upload to remote storage
if [ "$UPLOAD_S3" = "true" ] && [ -n "$S3_BUCKET" ]; then
    log_step "Uploading to S3..."
    
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    aws s3 cp ${BACKUP_PATH} s3://${S3_BUCKET}/${S3_PREFIX}/${BACKUP_FILE}
    aws s3 cp ${BACKUP_PATH}.sha256 s3://${S3_BUCKET}/${S3_PREFIX}/${BACKUP_FILE}.sha256
    
    log_info "Backup uploaded to S3: s3://${S3_BUCKET}/${S3_PREFIX}/${BACKUP_FILE}"
fi

if [ "$UPLOAD_GCS" = "true" ] && [ -n "$GCS_BUCKET" ]; then
    log_step "Uploading to GCS..."
    
    if ! command -v gsutil &> /dev/null; then
        log_error "gsutil is not installed"
        exit 1
    fi
    
    gsutil cp ${BACKUP_PATH} gs://${GCS_BUCKET}/${S3_PREFIX}/${BACKUP_FILE}
    gsutil cp ${BACKUP_PATH}.sha256 gs://${GCS_BUCKET}/${S3_PREFIX}/${BACKUP_FILE}.sha256
    
    log_info "Backup uploaded to GCS: gs://${GCS_BUCKET}/${S3_PREFIX}/${BACKUP_FILE}"
fi

if [ "$UPLOAD_AZURE" = "true" ] && [ -n "$AZURE_CONTAINER" ]; then
    log_step "Uploading to Azure Blob Storage..."
    
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed"
        exit 1
    fi
    
    az storage blob upload \
        --container-name ${AZURE_CONTAINER} \
        --file ${BACKUP_PATH} \
        --name ${S3_PREFIX}/${BACKUP_FILE}
    
    az storage blob upload \
        --container-name ${AZURE_CONTAINER} \
        --file ${BACKUP_PATH}.sha256 \
        --name ${S3_PREFIX}/${BACKUP_FILE}.sha256
    
    log_info "Backup uploaded to Azure: ${AZURE_CONTAINER}/${S3_PREFIX}/${BACKUP_FILE}"
fi

# Cleanup old backups
log_step "Cleaning up old backups (retention: ${RETENTION_DAYS} days)..."
find ${BACKUP_DIR} -name "vault-backup-*.snap" -mtime +${RETENTION_DAYS} -delete
find ${BACKUP_DIR} -name "vault-backup-*.snap.sha256" -mtime +${RETENTION_DAYS} -delete
log_info "Cleanup completed"

# Cleanup temp file from pod
log_step "Cleaning up temporary files..."
kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- rm -f /tmp/${BACKUP_FILE}

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}      Backup Complete!                 ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backup file: ${BACKUP_PATH}"
echo "Checksum: ${BACKUP_PATH}.sha256"
echo ""
echo "To restore from this backup:"
echo "  ./restore.sh ${BACKUP_PATH}"
echo ""

exit 0