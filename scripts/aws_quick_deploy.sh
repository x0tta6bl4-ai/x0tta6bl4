#!/bin/bash
# AWS Quick Deploy Script for x0tta6bl4
# Deploys to AWS ECS Fargate with ALB in 4-6 hours

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
ECR_REPO="x0tta6bl4-app"
CLUSTER_NAME="x0tta6bl4-staging"
SERVICE_NAME="x0tta6bl4-staging-service"
IMAGE_TAG="staging"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 AWS QUICK DEPLOY - x0tta6bl4                         ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    log_error "AWS CLI not found. Install: https://aws.amazon.com/cli/"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    log_error "Docker not found. Install: https://docs.docker.com/get-docker/"
    exit 1
fi

if [ -z "$AWS_ACCOUNT_ID" ]; then
    log_error "AWS credentials not configured. Run: aws configure"
    exit 1
fi

log_info "✅ Prerequisites check passed"
log_info "AWS Account: $AWS_ACCOUNT_ID"
log_info "Region: $AWS_REGION"
echo ""

# Step 1: ECR Setup
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "STEP 1: ECR Setup"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
ECR_IMAGE="$ECR_REGISTRY/$ECR_REPO:$IMAGE_TAG"

# Create ECR repository if not exists
if ! aws ecr describe-repositories --repository-names $ECR_REPO --region $AWS_REGION &> /dev/null; then
    log_info "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name $ECR_REPO \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true
else
    log_info "ECR repository already exists"
fi

# Login to ECR
log_info "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push image
log_info "Building Docker image..."
docker build -t x0tta6bl4-app:$IMAGE_TAG -f Dockerfile.app .

log_info "Tagging image for ECR..."
docker tag x0tta6bl4-app:$IMAGE_TAG $ECR_IMAGE

log_info "Pushing image to ECR (this may take 5-10 minutes)..."
docker push $ECR_IMAGE

log_info "✅ ECR setup complete: $ECR_IMAGE"
echo ""

# Step 2: ECS Cluster & Service
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "STEP 2: ECS Cluster & Service"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create CloudWatch log group
log_info "Creating CloudWatch log group..."
aws logs create-log-group \
    --log-group-name /ecs/$CLUSTER_NAME \
    --region $AWS_REGION 2>/dev/null || log_warn "Log group already exists"

# Get VPC and subnets
log_info "Getting VPC configuration..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[0:2].SubnetId" --output text --region $AWS_REGION | tr '\t' ',')

log_info "VPC ID: $VPC_ID"
log_info "Subnets: $SUBNET_IDS"

# Create Security Group
log_info "Creating Security Group..."
SG_ID=$(aws ec2 create-security-group \
    --group-name x0tta6bl4-staging-sg \
    --description "x0tta6bl4 staging security group" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --query 'GroupId' --output text 2>/dev/null || \
    aws ec2 describe-security-groups --filters "Name=group-name,Values=x0tta6bl4-staging-sg" --query "SecurityGroups[0].GroupId" --output text --region $AWS_REGION)

# Allow HTTP traffic
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION 2>/dev/null || log_warn "Security group rule may already exist"

log_info "Security Group: $SG_ID"

# Create ECS Cluster
log_info "Creating ECS cluster..."
aws ecs create-cluster \
    --cluster-name $CLUSTER_NAME \
    --region $AWS_REGION 2>/dev/null || log_warn "Cluster may already exist"

# Create Task Definition
log_info "Creating ECS Task Definition..."
cat > /tmp/task-def.json <<EOF
{
  "family": "$CLUSTER_NAME",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "x0tta6bl4-app",
      "image": "$ECR_IMAGE",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "NODE_ID", "value": "staging-control-plane"},
        {"name": "ENVIRONMENT", "value": "staging"},
        {"name": "LOG_LEVEL", "value": "INFO"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/$CLUSTER_NAME",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
EOF

aws ecs register-task-definition \
    --cli-input-json file:///tmp/task-def.json \
    --region $AWS_REGION

log_info "✅ ECS Task Definition created"
echo ""

# Step 3: Load Balancer
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "STEP 3: Load Balancer Setup"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create Target Group
log_info "Creating Target Group..."
TG_ARN=$(aws elbv2 create-target-group \
    --name x0tta6bl4-staging-tg \
    --protocol HTTP \
    --port 8080 \
    --vpc-id $VPC_ID \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --region $AWS_REGION \
    --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || \
    aws elbv2 describe-target-groups --names x0tta6bl4-staging-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region $AWS_REGION)

log_info "Target Group: $TG_ARN"

# Create Load Balancer
log_info "Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
    --name x0tta6bl4-staging-alb \
    --subnets $(echo $SUBNET_IDS | tr ',' ' ') \
    --security-groups $SG_ID \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || \
    aws elbv2 describe-load-balancers --names x0tta6bl4-staging-alb --query 'LoadBalancers[0].LoadBalancerArn' --output text --region $AWS_REGION)

# Wait for ALB to be active
log_info "Waiting for ALB to be active..."
aws elbv2 wait load-balancer-available --load-balancer-arns $ALB_ARN --region $AWS_REGION

# Get ALB DNS
ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].DNSName' --output text)

log_info "ALB DNS: $ALB_DNS"

# Create Listener
log_info "Creating ALB Listener..."
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $AWS_REGION 2>/dev/null || log_warn "Listener may already exist"

log_info "✅ Load Balancer setup complete"
echo ""

# Step 4: ECS Service
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "STEP 4: ECS Service"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Create or update service
if aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION &> /dev/null; then
    log_info "Updating existing service..."
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --task-definition $CLUSTER_NAME \
        --force-new-deployment \
        --region $AWS_REGION
else
    log_info "Creating new service..."
    aws ecs create-service \
        --cluster $CLUSTER_NAME \
        --service-name $SERVICE_NAME \
        --task-definition $CLUSTER_NAME \
        --desired-count 1 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$(echo $SUBNET_IDS | tr ',' ' ')],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
        --load-balancers "targetGroupArn=$TG_ARN,containerName=x0tta6bl4-app,containerPort=8080" \
        --region $AWS_REGION
fi

log_info "Waiting for service to stabilize (this may take 2-3 minutes)..."
aws ecs wait services-stable \
    --cluster $CLUSTER_NAME \
    --services $SERVICE_NAME \
    --region $AWS_REGION || log_warn "Service may still be starting"

log_info "✅ ECS Service created/updated"
echo ""

# Step 5: Verification
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "STEP 5: Verification"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

log_info "Waiting for ALB to be ready (30 seconds)..."
sleep 30

log_info "Testing health endpoint..."
if curl -s -f http://$ALB_DNS/health > /dev/null; then
    log_info "✅ Health check: PASSED"
    curl -s http://$ALB_DNS/health | python3 -m json.tool
else
    log_warn "⚠️ Health check: Waiting for service to start..."
    log_info "Service may need 1-2 more minutes to be fully ready"
fi

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ DEPLOYMENT COMPLETE!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "🌐 Your application is available at:"
log_info "   http://$ALB_DNS"
echo ""
log_info "📊 Useful commands:"
log_info "   Health check: curl http://$ALB_DNS/health"
log_info "   Metrics: curl http://$ALB_DNS/metrics"
log_info "   View logs: aws logs tail /ecs/$CLUSTER_NAME --follow --region $AWS_REGION"
log_info "   Service status: aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"
echo ""
log_info "💰 Estimated monthly cost: ~$70-100"
echo ""
log_info "🎆 CONGRATULATIONS! Your system is LIVE on AWS! 🎆"

