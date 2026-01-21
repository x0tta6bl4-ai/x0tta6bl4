#!/bin/bash
# x0tta6bl4 Staging Deployment Script
# Multi-Cloud Deployment: AWS + Azure + GCP

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 x0tta6bl4 Staging Deployment"
echo "================================"
echo ""

# Configuration
DEPLOY_TARGET="${1:-all}"  # aws, azure, gcp, all
NODE_COUNT="${2:-50}"      # Nodes per region

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check Terraform (optional)
    if ! command -v terraform &> /dev/null; then
        log_warn "Terraform not found. Infrastructure provisioning will be skipped."
    fi
    
    # Check AWS CLI (if AWS deployment)
    if [[ "$DEPLOY_TARGET" == "aws" || "$DEPLOY_TARGET" == "all" ]]; then
        if ! command -v aws &> /dev/null; then
            log_warn "AWS CLI not found. AWS deployment will be skipped."
        fi
    fi
    
    # Check Azure CLI (if Azure deployment)
    if [[ "$DEPLOY_TARGET" == "azure" || "$DEPLOY_TARGET" == "all" ]]; then
        if ! command -v az &> /dev/null; then
            log_warn "Azure CLI not found. Azure deployment will be skipped."
        fi
    fi
    
    # Check GCP CLI (if GCP deployment)
    if [[ "$DEPLOY_TARGET" == "gcp" || "$DEPLOY_TARGET" == "all" ]]; then
        if ! command -v gcloud &> /dev/null; then
            log_warn "GCP CLI not found. GCP deployment will be skipped."
        fi
    fi
    
    log_info "Prerequisites check complete"
}

build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build app image
    docker build -f Dockerfile.app -t x0tta6bl4-app:staging .
    
    # Build mesh node image (use app image if no specific mesh-node Dockerfile)
    if [ -f "Dockerfile.mesh-node" ]; then
        docker build -f Dockerfile.mesh-node -t x0tta6bl4-mesh-node:staging .
    else
        # Use app image for mesh nodes
        docker tag x0tta6bl4-app:staging x0tta6bl4-mesh-node:staging
    fi
    
    log_info "Docker images built successfully"
}

deploy_aws() {
    log_info "Deploying to AWS us-east-1..."
    
    if ! command -v aws &> /dev/null; then
        log_warn "AWS CLI not found. Skipping AWS deployment."
        return
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure'."
        return
    fi
    
    # Provision infrastructure (if Terraform available)
    if command -v terraform &> /dev/null && [ -d "$SCRIPT_DIR/terraform/aws" ]; then
        log_info "Provisioning AWS infrastructure..."
        cd "$SCRIPT_DIR/terraform/aws"
        terraform init
        terraform apply -var="node_count=$NODE_COUNT" -auto-approve
        cd "$PROJECT_ROOT"
    fi
    
    # Deploy application
    log_info "Deploying application to AWS..."
    
    # Get AWS configuration
    AWS_REGION="${AWS_REGION:-us-east-1}"
    AWS_ECR_REGISTRY="${AWS_ECR_REGISTRY:-$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com}"
    AWS_ECS_CLUSTER="${AWS_ECS_CLUSTER:-x0tta6bl4-cluster}"
    AWS_ECS_SERVICE="${AWS_ECS_SERVICE:-x0tta6bl4-service}"
    
    # Build and tag image
    IMAGE_NAME="x0tta6bl4-app"
    IMAGE_TAG="${IMAGE_TAG:-staging}"
    ECR_IMAGE="${AWS_ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    log_info "Building Docker image..."
    docker build -f Dockerfile.app -t ${IMAGE_NAME}:${IMAGE_TAG} .
    
    # Login to ECR
    log_info "Logging into ECR..."
    aws ecr get-login-password --region ${AWS_REGION} | \
        docker login --username AWS --password-stdin ${AWS_ECR_REGISTRY}
    
    # Create ECR repository if it doesn't exist
    if ! aws ecr describe-repositories --repository-names ${IMAGE_NAME} --region ${AWS_REGION} &> /dev/null; then
        log_info "Creating ECR repository..."
        aws ecr create-repository --repository-name ${IMAGE_NAME} --region ${AWS_REGION}
    fi
    
    # Tag and push image
    log_info "Tagging and pushing image to ECR..."
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_IMAGE}
    docker push ${ECR_IMAGE}
    
    # Update ECS service
    if aws ecs describe-services --cluster ${AWS_ECS_CLUSTER} --services ${AWS_ECS_SERVICE} --region ${AWS_REGION} &> /dev/null; then
        log_info "Updating ECS service..."
        aws ecs update-service \
            --cluster ${AWS_ECS_CLUSTER} \
            --service ${AWS_ECS_SERVICE} \
            --force-new-deployment \
            --region ${AWS_REGION}
        
        log_info "Waiting for service to stabilize..."
        aws ecs wait services-stable \
            --cluster ${AWS_ECS_CLUSTER} \
            --services ${AWS_ECS_SERVICE} \
            --region ${AWS_REGION}
    else
        log_warn "ECS service ${AWS_ECS_SERVICE} not found. Create it manually or use Terraform."
    fi
    
    log_info "✅ AWS deployment complete: ${ECR_IMAGE}"
}

deploy_azure() {
    log_info "Deploying to Azure westeurope..."
    
    if ! command -v az &> /dev/null; then
        log_warn "Azure CLI not found. Skipping Azure deployment."
        return
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Azure not logged in. Run 'az login'."
        return
    fi
    
    # Provision infrastructure (if Terraform available)
    if command -v terraform &> /dev/null && [ -d "$SCRIPT_DIR/terraform/azure" ]; then
        log_info "Provisioning Azure infrastructure..."
        cd "$SCRIPT_DIR/terraform/azure"
        terraform init
        terraform apply -var="node_count=$NODE_COUNT" -auto-approve
        cd "$PROJECT_ROOT"
    fi
    
    # Deploy application
    log_info "Deploying application to Azure..."
    
    # Get Azure configuration
    AZURE_ACR_NAME="${AZURE_ACR_NAME:-x0tta6bl4acr}"
    AZURE_RG="${AZURE_RG:-x0tta6bl4-rg}"
    AZURE_AKS_CLUSTER="${AZURE_AKS_CLUSTER:-x0tta6bl4-aks}"
    AZURE_REGION="${AZURE_REGION:-westeurope}"
    
    IMAGE_NAME="x0tta6bl4-app"
    IMAGE_TAG="${IMAGE_TAG:-staging}"
    ACR_IMAGE="${AZURE_ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
    
    # Build and tag image
    log_info "Building Docker image..."
    docker build -f Dockerfile.app -t ${IMAGE_NAME}:${IMAGE_TAG} .
    
    # Login to ACR
    log_info "Logging into ACR..."
    az acr login --name ${AZURE_ACR_NAME}
    
    # Create ACR repository if it doesn't exist (ACR auto-creates on push)
    log_info "Tagging and pushing image to ACR..."
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ACR_IMAGE}
    docker push ${ACR_IMAGE}
    
    # Update AKS deployment
    log_info "Updating AKS deployment..."
    az aks get-credentials --resource-group ${AZURE_RG} --name ${AZURE_AKS_CLUSTER} --overwrite-existing
    
    # Update Kubernetes deployment
    if kubectl get deployment x0tta6bl4 &> /dev/null; then
        kubectl set image deployment/x0tta6bl4 x0tta6bl4=${ACR_IMAGE}
        kubectl rollout status deployment/x0tta6bl4
    else
        log_warn "Kubernetes deployment 'x0tta6bl4' not found. Create it manually or use Helm."
    fi
    
    log_info "✅ Azure deployment complete: ${ACR_IMAGE}"
}

deploy_gcp() {
    log_info "Deploying to GCP asia-southeast1..."
    
    if ! command -v gcloud &> /dev/null; then
        log_warn "GCP CLI not found. Skipping GCP deployment."
        return
    fi
    
    # Check GCP login
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "GCP not logged in. Run 'gcloud auth login'."
        return
    fi
    
    # Provision infrastructure (if Terraform available)
    if command -v terraform &> /dev/null && [ -d "$SCRIPT_DIR/terraform/gcp" ]; then
        log_info "Provisioning GCP infrastructure..."
        cd "$SCRIPT_DIR/terraform/gcp"
        terraform init
        terraform apply -var="node_count=$NODE_COUNT" -auto-approve
        cd "$PROJECT_ROOT"
    fi
    
    # Deploy application
    log_info "Deploying application to GCP..."
    
    # Get GCP configuration
    GCP_PROJECT="${GCP_PROJECT:-$(gcloud config get-value project)}"
    GCP_REGION="${GCP_REGION:-asia-southeast1}"
    GCP_REPO="${GCP_REPO:-x0tta6bl4}"
    GCP_GKE_CLUSTER="${GCP_GKE_CLUSTER:-x0tta6bl4-cluster}"
    
    IMAGE_NAME="x0tta6bl4-app"
    IMAGE_TAG="${IMAGE_TAG:-staging}"
    GCR_IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${GCP_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
    
    # Build and tag image
    log_info "Building Docker image..."
    docker build -f Dockerfile.app -t ${IMAGE_NAME}:${IMAGE_TAG} .
    
    # Configure Docker for GCR
    log_info "Configuring Docker for GCR..."
    gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev
    
    # Create Artifact Registry repository if it doesn't exist
    if ! gcloud artifacts repositories describe ${GCP_REPO} \
        --location=${GCP_REGION} \
        --repository-format=docker &> /dev/null; then
        log_info "Creating Artifact Registry repository..."
        gcloud artifacts repositories create ${GCP_REPO} \
            --repository-format=docker \
            --location=${GCP_REGION} \
            --description="x0tta6bl4 Docker images"
    fi
    
    # Tag and push image
    log_info "Tagging and pushing image to GCR..."
    docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${GCR_IMAGE}
    docker push ${GCR_IMAGE}
    
    # Update GKE deployment
    log_info "Updating GKE deployment..."
    gcloud container clusters get-credentials ${GCP_GKE_CLUSTER} \
        --region=${GCP_REGION} \
        --project=${GCP_PROJECT}
    
    # Update Kubernetes deployment
    if kubectl get deployment x0tta6bl4 &> /dev/null; then
        kubectl set image deployment/x0tta6bl4 x0tta6bl4=${GCR_IMAGE}
        kubectl rollout status deployment/x0tta6bl4
    else
        log_warn "Kubernetes deployment 'x0tta6bl4' not found. Create it manually or use Helm."
    fi
    
    log_info "✅ GCP deployment complete: ${GCR_IMAGE}"
}

deploy_local() {
    log_info "Deploying locally with Docker Compose..."
    
    cd "$PROJECT_ROOT"
    
    # Create staging docker-compose file if not exists
    if [ ! -f "$SCRIPT_DIR/docker-compose.staging.yml" ]; then
        log_info "Creating staging docker-compose.yml..."
        cat > "$SCRIPT_DIR/docker-compose.staging.yml" <<EOF
version: '3.8'

services:
  control-plane:
    image: x0tta6bl4-app:staging
    container_name: x0tta6bl4-control-plane
    ports:
      - "8080:8080"
      - "9090:9090"
    environment:
      - NODE_ID=control-plane-staging
      - ENVIRONMENT=staging
      - LOG_LEVEL=INFO
    restart: unless-stopped
    networks:
      - x0tta6bl4_staging

  mesh-node-1:
    image: x0tta6bl4-mesh-node:staging
    container_name: x0tta6bl4-mesh-node-1
    environment:
      - NODE_ID=mesh-node-1-staging
      - ENVIRONMENT=staging
      - CONTROL_PLANE_URL=http://control-plane:8080
    restart: unless-stopped
    networks:
      - x0tta6bl4_staging
    depends_on:
      - control-plane

  prometheus:
    image: prom/prometheus:latest
    container_name: x0tta6bl4-prometheus
    ports:
      - "9091:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
    networks:
      - x0tta6bl4_staging

  grafana:
    image: grafana/grafana:latest
    container_name: x0tta6bl4-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - x0tta6bl4_staging
    depends_on:
      - prometheus

networks:
  x0tta6bl4_staging:
    driver: bridge

volumes:
  grafana-data:
EOF
    fi
    
    # Start services (use docker compose v2)
    log_info "Starting staging services..."
    docker compose -f "$SCRIPT_DIR/docker-compose.staging.yml" up -d
    
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Health check
    if curl -f http://localhost:8080/health &> /dev/null; then
        log_info "✅ Staging deployment successful!"
        log_info "Control Plane: http://localhost:8080"
        log_info "Prometheus: http://localhost:9091"
        log_info "Grafana: http://localhost:3000 (admin/admin)"
    else
        log_error "Health check failed. Check logs with: docker compose -f $SCRIPT_DIR/docker-compose.staging.yml logs"
        exit 1
    fi
}

run_smoke_tests() {
    log_info "Running smoke tests..."
    
    cd "$SCRIPT_DIR"
    
    if [ -f "smoke_tests.sh" ]; then
        bash smoke_tests.sh
    else
        log_warn "smoke_tests.sh not found. Skipping smoke tests."
    fi
}

# Main execution
main() {
    log_info "Starting staging deployment..."
    log_info "Target: $DEPLOY_TARGET"
    log_info "Nodes per region: $NODE_COUNT"
    echo ""
    
    # Pre-flight checks
    check_prerequisites
    echo ""
    
    # Build images
    build_images
    echo ""
    
    # Deploy based on target
    case "$DEPLOY_TARGET" in
        aws)
            deploy_aws
            ;;
        azure)
            deploy_azure
            ;;
        gcp)
            deploy_gcp
            ;;
        all)
            deploy_aws
            echo ""
            deploy_azure
            echo ""
            deploy_gcp
            ;;
        local)
            deploy_local
            ;;
        *)
            log_error "Unknown deployment target: $DEPLOY_TARGET"
            log_info "Usage: $0 [aws|azure|gcp|all|local] [node_count]"
            exit 1
            ;;
    esac
    
    echo ""
    log_info "Deployment complete!"
    
    # Run smoke tests
    if [[ "$DEPLOY_TARGET" != "local" ]]; then
        echo ""
        run_smoke_tests
    fi
    
    echo ""
    log_info "✅ Staging deployment successful!"
    log_info "Next steps:"
    log_info "  1. Monitor metrics: http://monitoring:9090"
    log_info "  2. Check Grafana dashboards"
    log_info "  3. Review logs: docker-compose -f staging/docker-compose.staging.yml logs"
}

# Run main function
main "$@"

