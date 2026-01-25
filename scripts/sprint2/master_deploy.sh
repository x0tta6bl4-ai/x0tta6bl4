#!/bin/bash
# scripts/sprint2/master_deploy.sh
# Universal Sprint 2 deployment orchestrator
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

prompt_user() { local prompt_text=$1; local var_name=$2; read -p "$(echo -e ${BLUE}${prompt_text}${NC})" "$var_name"; }

detect_environment() {
  log_info "Detecting Kubernetes environment..."
  if kubectl get nodes -o json 2>/dev/null | jq -e '.items[0].spec.providerID' | grep -q "aws"; then
    echo "eks"
  elif kubectl get nodes -o json 2>/dev/null | jq -e '.items[0].spec.providerID' | grep -q "gce"; then
    echo "gke"
  else
    echo "self-managed"
  fi
}

configure_eks() {
  log_info "Configuring for AWS EKS..."
  prompt_user "Enter EKS cluster name [mesh-production]: " CLUSTER_NAME; CLUSTER_NAME=${CLUSTER_NAME:-mesh-production}
  prompt_user "Enter AWS region [us-east-1]: " AWS_REGION; AWS_REGION=${AWS_REGION:-us-east-1}
  prompt_user "Enter node instance type [t3.medium]: " NODE_TYPE; NODE_TYPE=${NODE_TYPE:-t3.medium}
  export CLUSTER_NAME AWS_REGION NODE_TYPE
}

configure_gke() {
  log_info "Configuring for Google GKE..."
  prompt_user "Enter GKE cluster name [mesh-production]: " CLUSTER_NAME; CLUSTER_NAME=${CLUSTER_NAME:-mesh-production}
  prompt_user "Enter GCP zone [us-central1-a]: " ZONE; ZONE=${ZONE:-us-central1-a}
  prompt_user "Enter machine type [n1-standard-2]: " MACHINE_TYPE; MACHINE_TYPE=${MACHINE_TYPE:-n1-standard-2}
  export CLUSTER_NAME ZONE MACHINE_TYPE
}

configure_self_managed() {
  log_info "Configuring for self-managed cluster..."
  prompt_user "Enter node names (space-separated) [node-1 node-2 node-3]: " NODES; NODES=${NODES:-"node-1 node-2 node-3"}
  export NODES
}

pre_flight_checks() {
  log_info "Running pre-flight checks..."
  if ! command -v kubectl &>/dev/null; then log_error "kubectl not found"; exit 1; fi; log_success "kubectl found"
  if ! kubectl cluster-info &>/dev/null; then log_error "Cannot connect to Kubernetes cluster"; exit 1; fi; log_success "Cluster connectivity OK"
  local required_tools=("helm" "jq" "curl"); for tool in "${required_tools[@]}"; do
    if ! command -v "$tool" &>/dev/null; then log_warning "$tool not found"; else log_success "$tool found"; fi
  done
}

deploy_node_pool() { local env=$1; log_info "Deploying privileged node pool for $env..."; case $env in
  eks) bash scripts/sprint2/setup_privileged_node_pool_eks.sh;;
  gke) bash scripts/sprint2/setup_privileged_node_pool_gke.sh;;
  self-managed) bash scripts/sprint2/setup_privileged_nodes_self_managed.sh;;
  *) log_error "Unknown ENV $env"; return 1;; esac; log_success "Node pool deployed"; }

validate_deployment() { log_info "Validating node pool configuration..."; if bash scripts/sprint2/validate_node_pool.sh; then log_success "Node pool validation passed"; else log_error "Node pool validation failed"; return 1; fi }

deploy_security_controls() {
  log_info "Deploying AppArmor profiles..."; if bash scripts/sprint2/deploy_apparmor_profiles.sh; then log_success "AppArmor profiles deployed"; else log_warning "AppArmor deployment issues"; fi
  log_info "Deploying Falco runtime security..."; bash scripts/sprint2/deploy_falco.sh
  log_info "Deploying Falco exporter..."; kubectl apply -f monitoring/falco/falco-exporter-deployment.yaml || log_warning "Falco exporter issues"
}

deploy_batman() {
  log_info "Validating B.A.T.M.A.N. prerequisites..."; bash scripts/sprint2/validate_batman_prerequisites.sh
  log_info "Deploying B.A.T.M.A.N...."; bash scripts/sprint2/deploy_batman.sh
  log_info "Running B.A.T.M.A.N. tests..."; bash scripts/sprint2/test_batman_deployment.sh || log_warning "Some tests failed"
}

generate_reports() { log_info "Generating security audit report..."; bash scripts/sprint2/generate_security_audit_report.sh || log_warning "Report generation issues"; }

show_next_steps() {
  echo ""; echo "======================================"; log_success "Sprint 2 Deployment Complete!"; echo "======================================"; echo ""
  echo "Next steps:"; echo "1. Monitor security events: bash scripts/sprint2/monitor_security_events.sh"; echo "2. Review audit report: cat security_audit_*.md"; echo "3. Test mesh: kubectl exec -n mesh-network batman-adv-gateway-0 -c batman-adv -- batctl o"; echo "4. View Falco: kubectl logs -n falco-system -l app=falco -f"; }

main() {
  echo "======================================"; echo "  Sprint 2 Deployment Orchestrator"; echo "======================================"; echo ""
  pre_flight_checks
  ENV_TYPE=$(detect_environment); log_info "Detected environment: $ENV_TYPE"; prompt_user "Is this correct? [y/n]: " CONFIRM
  if [[ "${CONFIRM:-y}" != "y" ]]; then
    echo "Select environment: 1) EKS  2) GKE  3) Self-managed"; prompt_user "Enter choice [1-3]: " CHOICE
    case ${CHOICE:-1} in 1) ENV_TYPE=eks;; 2) ENV_TYPE=gke;; 3) ENV_TYPE=self-managed;; *) log_error "Invalid choice"; exit 1;; esac
  fi
  case $ENV_TYPE in eks) configure_eks;; gke) configure_gke;; self-managed) configure_self_managed;; esac
  echo ""; log_info "Starting deployment..."; echo ""
  deploy_node_pool "$ENV_TYPE"; sleep 2
  validate_deployment; sleep 2
  deploy_security_controls; sleep 2
  deploy_batman; sleep 2
  generate_reports
  show_next_steps
}

main "$@"
