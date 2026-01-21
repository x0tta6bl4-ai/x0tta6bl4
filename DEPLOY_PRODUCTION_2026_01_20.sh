#!/bin/bash
# x0tta6bl4 v3.3.0 - Production Deployment Commands
# Copy-paste ready commands for production deployment
# Date: January 20, 2026

set -e

echo "🚀 x0tta6bl4 v3.3.0 - Production Deployment"
echo "============================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# SECTION 1: PRE-DEPLOYMENT CHECKS
# ============================================================================

echo -e "${BLUE}[1/5] Pre-Deployment Checks${NC}"
echo "================================"

# Check Docker
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker installed:${NC} $(docker --version)"
else
    echo -e "${RED}❌ Docker not found. Install from: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# Check kubectl (if using Kubernetes)
if command -v kubectl &> /dev/null; then
    echo -e "${GREEN}✅ kubectl installed:${NC} $(kubectl version --client --short 2>/dev/null || echo 'v1.20+')"
else
    echo -e "${YELLOW}⚠️  kubectl not found (only needed for Kubernetes deployment)${NC}"
fi

# Check Git
if command -v git &> /dev/null; then
    echo -e "${GREEN}✅ Git installed:${NC} $(git --version)"
else
    echo -e "${RED}❌ Git not found. Install from: https://git-scm.com/${NC}"
    exit 1
fi

echo ""

# ============================================================================
# SECTION 2: ENVIRONMENT SETUP
# ============================================================================

echo -e "${BLUE}[2/5] Environment Configuration${NC}"
echo "=================================="

# Create .env.production
cat > .env.production << 'EOF'
# API Configuration
X0TTA6BL4_ENV=production
X0TTA6BL4_LOG_LEVEL=INFO
X0TTA6BL4_PORT=8000
X0TTA6BL4_WORKERS=4

# Security (Generate these!)
ADMIN_TOKEN=CHANGE_ME_GENERATE_NEW
DATABASE_PASSWORD=CHANGE_ME_GENERATE_NEW
JWT_SECRET=CHANGE_ME_GENERATE_NEW

# Database
DATABASE_URL=postgresql://x0tta6bl4:PASSWORD@db.production/x0tta6bl4
DATABASE_POOL_SIZE=20

# Monitoring
PROMETHEUS_SCRAPE_INTERVAL=15s
PROMETHEUS_RETENTION=90d

# SPIFFE/SPIRE
SPIRE_SERVER_ADDRESS=spire.production.local:8081

# Feature Flags
ENABLE_PQC=true
ENABLE_MTLS=true
ENABLE_MONITORING=true
EOF

echo -e "${GREEN}✅ Created .env.production${NC}"
echo "   ⚠️  IMPORTANT: Update sensitive values before deploying!"
echo ""

# ============================================================================
# SECTION 3: QUICK DEPLOYMENT COMMANDS
# ============================================================================

echo -e "${BLUE}[3/5] Choose Deployment Option${NC}"
echo "=================================="
echo ""
echo "Select deployment method:"
echo ""
echo "Option 1: Docker Compose (Fastest)"
echo "  docker-compose -f docker-compose.yml up -d"
echo ""
echo "Option 2: Kubernetes (Production Recommended)"
echo "  helm install x0tta6bl4 ./helm/x0tta6bl4 -n x0tta6bl4 -f values.production.yaml"
echo ""
echo "Option 3: Terraform (Infrastructure as Code)"
echo "  cd terraform && terraform apply -var-file=production.tfvars"
echo ""

# ============================================================================
# SECTION 4: VALIDATION COMMANDS
# ============================================================================

echo -e "${BLUE}[4/5] Post-Deployment Validation${NC}"
echo "===================================="
echo ""
echo "Health Check:"
echo "  curl http://localhost:8000/health"
echo ""
echo "Metrics:"
echo "  curl http://localhost:9090/metrics | head"
echo ""
echo "Security Check:"
echo "  curl -H 'Authorization: Bearer invalid' http://localhost:8000/api/v1/users/stats"
echo ""

# ============================================================================
# SECTION 5: USEFUL COMMANDS
# ============================================================================

echo -e "${BLUE}[5/5] Useful Commands${NC}"
echo "====================="
echo ""
echo "Docker Compose:"
echo "  Logs:     docker-compose logs -f"
echo "  Stop:     docker-compose down"
echo "  Scale:    docker-compose up -d --scale api=3"
echo ""
echo "Kubernetes:"
echo "  Logs:     kubectl logs -f deployment/x0tta6bl4-api -n x0tta6bl4"
echo "  Scale:    kubectl scale deployment x0tta6bl4-api --replicas=5 -n x0tta6bl4"
echo "  Status:   kubectl get pods -n x0tta6bl4"
echo ""
echo "Monitoring:"
echo "  Grafana:  http://localhost:3000 (admin/admin)"
echo "  Prometheus: http://localhost:9090"
echo "  Jaeger:   http://localhost:16686"
echo ""

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Deployment Ready!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "Next Steps:"
echo "1. Choose your deployment option above"
echo "2. Run the command"
echo "3. Verify health checks"
echo "4. Check monitoring dashboards"
echo ""
echo "Documentation:"
echo "  - PRODUCTION_DEPLOYMENT_QUICKSTART_2026_01_20.md"
echo "  - docs/OPERATIONS.md"
echo "  - docs/TROUBLESHOOTING.md"
echo ""
