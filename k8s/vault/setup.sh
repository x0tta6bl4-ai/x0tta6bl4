#!/bin/bash
#
# Vault Setup Script for Kubernetes - Full Automation
#
# This script initializes and configures Vault in a Kubernetes cluster.
# It handles initialization, unsealing, auth method setup, policies, and secrets.
#
# Usage: ./setup.sh [--auto-unseal] [--cloud-provider aws|gcp|azure]

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
PROXY_API_NAMESPACE="${PROXY_API_NAMESPACE:-default}"
PROXY_API_SA="${PROXY_API_SA:-proxy-api}"
VAULT_ADDR="${VAULT_ADDR:-https://vault.${VAULT_NAMESPACE}.svc.cluster.local:8200}"

# Flags
AUTO_UNSEAL=false
CLOUD_PROVIDER=""
KMS_KEY_ID=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --auto-unseal)
            AUTO_UNSEAL=true
            shift
            ;;
        --cloud-provider)
            CLOUD_PROVIDER="$2"
            shift 2
            ;;
        --kms-key-id)
            KMS_KEY_ID="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --auto-unseal              Enable auto-unseal with cloud KMS"
            echo "  --cloud-provider PROVIDER  Cloud provider (aws, gcp, azure)"
            echo "  --kms-key-id KEY_ID        KMS key ID for auto-unseal"
            echo "  --help                     Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

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

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    Vault Setup Script for Kubernetes   ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
log_step "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_error "jq is not installed"
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster"
    exit 1
fi

log_info "Prerequisites met ✓"
echo ""

# Check if Vault namespace exists
if ! kubectl get namespace ${VAULT_NAMESPACE} &> /dev/null; then
    log_step "Creating Vault namespace..."
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${VAULT_NAMESPACE}
  labels:
    app: vault
EOF
fi

# Wait for Vault pods to be ready
log_step "Waiting for Vault pods to be ready..."
if ! kubectl wait --for=condition=ready pod/${VAULT_POD} -n ${VAULT_NAMESPACE} --timeout=300s 2>/dev/null; then
    log_error "Vault pods are not ready. Please deploy Vault first."
    log_info "You can deploy Vault with: helm install vault hashicorp/vault -n ${VAULT_NAMESPACE} -f helm-values.yaml"
    exit 1
fi
log_info "Vault is ready ✓"
echo ""

# Function to execute vault commands
vault_exec() {
    kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault "$@"
}

# Check Vault status
log_step "Checking Vault status..."
VAULT_STATUS=$(vault_exec status -format=json 2>/dev/null || echo '{"initialized": false}')
INIT_STATUS=$(echo "$VAULT_STATUS" | jq -r '.initialized')
SEAL_STATUS=$(echo "$VAULT_STATUS" | jq -r '.sealed // true')

# Initialize Vault if needed
if [ "$INIT_STATUS" != "true" ]; then
    log_step "Initializing Vault..."
    
    if [ "$AUTO_UNSEAL" = true ] && [ -n "$CLOUD_PROVIDER" ]; then
        log_info "Using auto-unseal with ${CLOUD_PROVIDER} KMS"
        
        # Configure auto-unseal in Vault
        case $CLOUD_PROVIDER in
            aws)
                if [ -z "$KMS_KEY_ID" ]; then
                    log_error "KMS key ID is required for AWS auto-unseal"
                    exit 1
                fi
                vault_exec operator init \
                    -recovery-shares=5 \
                    -recovery-threshold=3 \
                    -format=json > vault-init.json
                ;;
            gcp)
                if [ -z "$KMS_KEY_ID" ]; then
                    log_error "KMS key ID is required for GCP auto-unseal"
                    exit 1
                fi
                vault_exec operator init \
                    -recovery-shares=5 \
                    -recovery-threshold=3 \
                    -format=json > vault-init.json
                ;;
            azure)
                if [ -z "$KMS_KEY_ID" ]; then
                    log_error "KMS key ID is required for Azure auto-unseal"
                    exit 1
                fi
                vault_exec operator init \
                    -recovery-shares=5 \
                    -recovery-threshold=3 \
                    -format=json > vault-init.json
                ;;
            *)
                log_error "Unsupported cloud provider: $CLOUD_PROVIDER"
                exit 1
                ;;
        esac
    else
        # Manual unseal with Shamir keys
        vault_exec operator init \
            -key-shares=5 \
            -key-threshold=3 \
            -format=json > vault-init.json
    fi
    
    log_info "Vault initialized. Keys saved to vault-init.json"
    log_warn "IMPORTANT: Keep vault-init.json secure! It contains unseal keys and root token."
    
    # Set restrictive permissions on init file
    chmod 600 vault-init.json
    
    # Unseal Vault if not using auto-unseal
    if [ "$AUTO_UNSEAL" != true ]; then
        log_step "Unsealing Vault..."
        
        UNSEAL_KEYS=$(cat vault-init.json | jq -r '.unseal_keys_b64[]')
        KEY_COUNT=0
        
        for KEY in $UNSEAL_KEYS; do
            if [ $KEY_COUNT -lt 3 ]; then
                vault_exec operator unseal "$KEY" > /dev/null
                KEY_COUNT=$((KEY_COUNT + 1))
            fi
        done
        log_info "Vault unsealed ✓"
    fi
else
    log_info "Vault is already initialized"
    
    # Check if sealed
    if [ "$SEAL_STATUS" = "true" ] && [ "$AUTO_UNSEAL" != true ]; then
        log_warn "Vault is sealed. Please provide unseal keys."
        
        if [ -f vault-init.json ]; then
            log_step "Unsealing Vault with saved keys..."
            UNSEAL_KEYS=$(cat vault-init.json | jq -r '.unseal_keys_b64[]')
            KEY_COUNT=0
            
            for KEY in $UNSEAL_KEYS; do
                if [ $KEY_COUNT -lt 3 ]; then
                    vault_exec operator unseal "$KEY" > /dev/null
                    KEY_COUNT=$((KEY_COUNT + 1))
                fi
            done
            log_info "Vault unsealed ✓"
        else
            log_error "Vault is sealed and vault-init.json not found."
            log_error "Please unseal Vault manually or provide unseal keys."
            exit 1
        fi
    fi
fi

# Get root token
if [ -f vault-init.json ]; then
    ROOT_TOKEN=$(cat vault-init.json | jq -r '.root_token')
else
    log_error "vault-init.json not found. Cannot proceed without root token."
    exit 1
fi

# Login to Vault
log_step "Authenticating to Vault..."
vault_exec login "$ROOT_TOKEN" > /dev/null
log_info "Authenticated ✓"
echo ""

# Enable and configure secrets engines
log_step "Configuring secrets engines..."

# Enable KV v2 at secret/
if ! vault_exec secrets list | grep -q "^secret/"; then
    log_info "Enabling KV v2 secrets engine..."
    vault_exec secrets enable -version=2 -path=secret kv
else
    log_info "KV secrets engine already enabled"
fi

# Enable database secrets engine for dynamic credentials
if ! vault_exec secrets list | grep -q "^database/"; then
    log_info "Enabling database secrets engine..."
    vault_exec secrets enable database
else
    log_info "Database secrets engine already enabled"
fi

# Enable PKI for certificates
if ! vault_exec secrets list | grep -q "^pki/"; then
    log_info "Enabling PKI secrets engine..."
    vault_exec secrets enable pki
    vault_exec secrets tune -max-lease-ttl=8760h pki
else
    log_info "PKI secrets engine already enabled"
fi

log_info "Secrets engines configured ✓"
echo ""

# Enable and configure Kubernetes auth
log_step "Configuring Kubernetes authentication..."

if ! vault_exec auth list | grep -q "^kubernetes/"; then
    log_info "Enabling Kubernetes auth method..."
    vault_exec auth enable kubernetes
else
    log_info "Kubernetes auth method already enabled"
fi

# Get Kubernetes configuration
K8S_HOST="${K8S_HOST:-https://kubernetes.default.svc}"
if [ -z "$K8S_HOST" ] || [ "$K8S_HOST" = "https://kubernetes.default.svc" ]; then
    K8S_HOST=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}' 2>/dev/null || echo "https://kubernetes.default.svc")
fi

# Get CA cert
CA_CERT_FILE=$(mktemp)
kubectl get configmap -n kube-system extension-apiserver-authentication -o=jsonpath='{.data.client-ca-file}' > "$CA_CERT_FILE" 2>/dev/null || \
kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d > "$CA_CERT_FILE"

# Get service account token for Vault
SA_TOKEN=$(kubectl create token vault -n ${VAULT_NAMESPACE} --duration=24h 2>/dev/null || \
           kubectl get secret -n ${VAULT_NAMESPACE} $(kubectl get sa vault -n ${VAULT_NAMESPACE} -o jsonpath='{.secrets[0].name}') -o jsonpath='{.data.token}' | base64 -d)

# Configure Kubernetes auth
log_info "Configuring Kubernetes auth..."
kubectl cp "$CA_CERT_FILE" ${VAULT_NAMESPACE}/${VAULT_POD}:/tmp/ca.crt
vault_exec write auth/kubernetes/config \
    token_reviewer_jwt="$SA_TOKEN" \
    kubernetes_host="${K8S_HOST}" \
    kubernetes_ca_cert=@/tmp/ca.crt \
    issuer="https://kubernetes.default.svc.cluster.local"

rm -f "$CA_CERT_FILE"
log_info "Kubernetes authentication configured ✓"
echo ""

# Create Vault policies
log_step "Creating Vault policies..."

# Proxy API policy
cat > /tmp/proxy-api-policy.hcl <<'EOF'
# Read proxy secrets
path "secret/data/proxy/*" {
  capabilities = ["read", "list"]
}

# Read database credentials
path "secret/data/proxy/database/*" {
  capabilities = ["read"]
}

# Read API keys
path "secret/data/proxy/api-keys/*" {
  capabilities = ["read"]
}

# Read certificates
path "secret/data/proxy/certificates/*" {
  capabilities = ["read"]
}

# Read tokens
path "secret/data/proxy/tokens/*" {
  capabilities = ["read"]
}

# Read encryption keys
path "secret/data/proxy/encryption/*" {
  capabilities = ["read"]
}

# Generate database credentials
path "database/creds/proxy-api" {
  capabilities = ["read"]
}

# Check Vault health
path "sys/health" {
  capabilities = ["read"]
}

# Check seal status
path "sys/seal-status" {
  capabilities = ["read"]
}
EOF

kubectl cp /tmp/proxy-api-policy.hcl ${VAULT_NAMESPACE}/${VAULT_POD}:/tmp/proxy-api-policy.hcl
vault_exec policy write proxy-api /tmp/proxy-api-policy.hcl
log_info "Created proxy-api policy"

# Admin policy
cat > /tmp/admin-policy.hcl <<'EOF'
# Manage all secrets
path "*" {
  capabilities = ["create", "read", "update", "delete", "list", "sudo"]
}

# Manage auth methods
path "sys/auth/*" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}

# Manage policies
path "sys/policies/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage secrets engines
path "sys/mounts/*" {
  capabilities = ["create", "read", "update", "delete"]
}
EOF

kubectl cp /tmp/admin-policy.hcl ${VAULT_NAMESPACE}/${VAULT_POD}:/tmp/admin-policy.hcl
vault_exec policy write admin /tmp/admin-policy.hcl
log_info "Created admin policy"

# Read-only policy for monitoring
cat > /tmp/readonly-policy.hcl <<'EOF'
# Read secrets
path "secret/data/*" {
  capabilities = ["read", "list"]
}

# Health checks
path "sys/health" {
  capabilities = ["read"]
}

# Metrics
path "sys/metrics" {
  capabilities = ["read"]
}
EOF

kubectl cp /tmp/readonly-policy.hcl ${VAULT_NAMESPACE}/${VAULT_POD}:/tmp/readonly-policy.hcl
vault_exec policy write readonly /tmp/readonly-policy.hcl
log_info "Created readonly policy"

log_info "Policies created ✓"
echo ""

# Create Kubernetes auth roles
log_step "Creating Kubernetes auth roles..."

# Create proxy-api role
vault_exec write auth/kubernetes/role/proxy-api \
    bound_service_account_names="${PROXY_API_SA}" \
    bound_service_account_namespaces="${PROXY_API_NAMESPACE}" \
    policies="proxy-api" \
    ttl=1h \
    max_ttl=24h

log_info "Created proxy-api role"

# Create readonly role for monitoring
vault_exec write auth/kubernetes/role/vault-monitor \
    bound_service_account_names="vault-monitor" \
    bound_service_account_namespaces="${VAULT_NAMESPACE}" \
    policies="readonly" \
    ttl=1h

log_info "Created vault-monitor role"
log_info "Kubernetes auth roles configured ✓"
echo ""

# Configure database secrets engine for PostgreSQL
log_step "Configuring database secrets engine..."

# Check if PostgreSQL is available
if kubectl get service postgres -n ${PROXY_API_NAMESPACE} &> /dev/null || \
   kubectl get service postgresql -n ${PROXY_API_NAMESPACE} &> /dev/null; then
    
    log_info "PostgreSQL service found, configuring database secrets engine..."
    
    # Get PostgreSQL connection details
    PG_HOST="${PG_HOST:-postgres.${PROXY_API_NAMESPACE}.svc.cluster.local}"
    PG_PORT="${PG_PORT:-5432}"
    PG_USER="${PG_USER:-postgres}"
    PG_PASSWORD="${PG_PASSWORD:-$(kubectl get secret postgres -n ${PROXY_API_NAMESPACE} -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || echo 'postgres')}"
    
    # Configure PostgreSQL connection
    vault_exec write database/config/postgresql \
        plugin_name=postgresql-database-plugin \
        allowed_roles="proxy-api" \
        connection_url="postgresql://{{username}}:{{password}}@${PG_HOST}:${PG_PORT}/postgres" \
        username="${PG_USER}" \
        password="${PG_PASSWORD}"
    
    # Create role for dynamic credentials
    vault_exec write database/roles/proxy-api \
        db_name=postgresql \
        creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
            GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
        default_ttl=1h \
        max_ttl=24h
    
    log_info "Database secrets engine configured ✓"
else
    log_warn "PostgreSQL service not found. Skipping database secrets engine configuration."
    log_info "You can configure it later with:"
    log_info "  vault write database/config/postgresql plugin_name=postgresql-database-plugin ..."
fi
echo ""

# Create initial secrets
log_step "Creating initial secrets..."

# Database credentials
log_info "Creating database credentials..."
vault_exec kv put secret/proxy/database/main-db \
    username="proxy_user" \
    password="$(openssl rand -base64 32)" \
    host="postgres.${PROXY_API_NAMESPACE}.svc.cluster.local" \
    port="5432" \
    database="proxy_db" \
    connection_string="postgresql://proxy_user:@postgres.${PROXY_API_NAMESPACE}.svc.cluster.local:5432/proxy_db" \
    2>/dev/null || log_warn "Failed to create database credentials (may already exist)"

# Proxy API credentials
log_info "Creating proxy-api credentials..."
PROXY_API_KEY=$(openssl rand -hex 32)
PROXY_SECRET=$(openssl rand -hex 32)
vault_exec kv put secret/proxy/credentials/proxy-api \
    api_key="${PROXY_API_KEY}" \
    secret="${PROXY_SECRET}" \
    2>/dev/null || log_warn "Failed to create proxy-api credentials (may already exist)"

# API keys placeholders
log_info "Creating API key placeholders..."
vault_exec kv put secret/proxy/api-keys/stripe \
    api_key="sk_test_placeholder" \
    api_secret="placeholder_secret" \
    2>/dev/null || log_warn "Failed to create Stripe API keys (may already exist)"

vault_exec kv put secret/proxy/api-keys/sendgrid \
    api_key="SG.placeholder" \
    2>/dev/null || log_warn "Failed to create SendGrid API keys (may already exist)"

# Encryption keys
log_info "Creating encryption keys..."
vault_exec kv put secret/proxy/encryption/master-key \
    key="$(openssl rand -base64 32)" \
    2>/dev/null || log_warn "Failed to create encryption key (may already exist)"

log_info "Initial secrets created ✓"
echo ""

# Join HA nodes if applicable
HA_REPLICAS=$(kubectl get pods -n ${VAULT_NAMESPACE} -l app.kubernetes.io/name=vault --no-headers | wc -l)
if [ $HA_REPLICAS -gt 1 ]; then
    log_step "Joining HA nodes to the cluster..."
    
    LEADER_POD=${VAULT_POD}
    
    for POD in $(kubectl get pods -n ${VAULT_NAMESPACE} -l app.kubernetes.io/name=vault -o jsonpath='{.items[*].metadata.name}'); do
        if [ "$POD" != "$LEADER_POD" ]; then
            log_info "Joining ${POD}..."
            
            # Get CA cert for leader
            kubectl exec -n ${VAULT_NAMESPACE} ${LEADER_POD} -- cat /var/run/secrets/kubernetes.io/serviceaccount/ca.crt > /tmp/leader-ca.crt 2>/dev/null || true
            
            # Join the node
            kubectl exec -n ${VAULT_NAMESPACE} ${POD} -- \
                vault operator raft join \
                -leader-ca-cert=@/tmp/leader-ca.crt \
                https://${LEADER_POD}.${VAULT_NAMESPACE}.svc.cluster.local:8200 2>/dev/null || \
            kubectl exec -n ${VAULT_NAMESPACE} ${POD} -- \
                vault operator raft join \
                https://${LEADER_POD}.${VAULT_NAMESPACE}.svc.cluster.local:8200 2>/dev/null || \
            log_warn "Failed to join ${POD} (may already be joined)"
        fi
    done
    
    # List raft peers
    log_info "Raft peers:"
    vault_exec operator raft list-peers
    
    log_info "HA nodes joined ✓"
    echo ""
fi

# Enable audit logging
log_step "Configuring audit logging..."

if ! vault_exec audit list | grep -q "file/"; then
    log_info "Enabling file audit device..."
    vault_exec audit enable file file_path=/vault/logs/audit.log
    log_info "Audit logging enabled ✓"
else
    log_info "Audit logging already enabled"
fi
echo ""

# Print summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    Vault Setup Complete!              ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Vault is configured and ready to use."
echo ""
echo -e "${BLUE}Configuration Summary:${NC}"
echo "  Vault Address: ${VAULT_ADDR}"
echo "  Namespace: ${VAULT_NAMESPACE}"
echo "  Proxy API Role: proxy-api"
echo "  Service Account: ${PROXY_API_SA}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Update your application to use the Vault client:"
echo "     export VAULT_ADDR='${VAULT_ADDR}'"
echo "     export VAULT_K8S_ROLE='proxy-api'"
echo ""
echo "  2. Deploy your application with the ${PROXY_API_SA} service account"
echo ""
echo "  3. Test secret retrieval:"
echo "     kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault kv get secret/proxy/credentials/proxy-api"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  - View Vault status: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault status"
echo "  - List secrets: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault kv list secret/proxy"
echo "  - Read a secret: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault kv get secret/proxy/credentials/proxy-api"
echo "  - Check auth methods: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault auth list"
echo "  - Check policies: kubectl exec -n ${VAULT_NAMESPACE} ${VAULT_POD} -- vault policy list"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  - Keep vault-init.json secure (contains root token and unseal keys)"
echo "  - Enable auto-unseal for production (see helm-values.yaml)"
echo "  - Configure backup for Raft storage"
echo "  - Set up monitoring and alerting"
echo ""
echo -e "${GREEN}Done!${NC}"
echo ""