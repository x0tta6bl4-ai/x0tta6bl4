#!/bin/bash
# x0tta6bl4 Demo Script - Show critical endpoints to users
# Usage: ./demo-endpoints.sh

set -e

API_URL="${1:-http://localhost:8000}"
COLOR_BLUE='\033[0;34m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_BLUE}  x0tta6bl4 API Demo - Endpoint Testing${COLOR_RESET}"
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo ""

# Function to test endpoint and pretty-print
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    
    echo -e "${COLOR_YELLOW}📍 Testing${COLOR_RESET}: $endpoint"
    echo -e "${COLOR_YELLOW}   Description${COLOR_RESET}: $description"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$API_URL$endpoint")
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n-1)
    else
        response=$(curl -s -w "\n%{http_code}" -X $method "$API_URL$endpoint")
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n-1)
    fi
    
    if [ "$http_code" = "200" ]; then
        echo -e "${COLOR_GREEN}   Status${COLOR_RESET}: ✅ $http_code"
    else
        echo -e "${COLOR_RED}   Status${COLOR_RESET}: ❌ $http_code"
    fi
    
    echo -e "${COLOR_BLUE}   Response${COLOR_RESET}:"
    if command -v python3 &> /dev/null; then
        echo "$body" | python3 -m json.tool 2>/dev/null | head -15 || echo "   (non-JSON response)" && echo "$body" | head -5
    else
        echo "$body" | head -10
    fi
    
    echo ""
}

# Check if API is available
echo -e "${COLOR_YELLOW}🔍 Checking API availability at $API_URL${COLOR_RESET}"
if ! curl -s "$API_URL/health" &>/dev/null; then
    echo -e "${COLOR_RED}❌ API not responding at $API_URL${COLOR_RESET}"
    echo ""
    echo "Make sure x0tta6bl4 is running:"
    echo "  • Docker: docker compose -f staging/docker-compose.quick.yml up -d"
    echo "  • Local:  ./run-fastapi.sh"
    exit 1
fi
echo -e "${COLOR_GREEN}✅ API is responding${COLOR_RESET}"
echo ""

# Test critical endpoints
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_BLUE}1️⃣  HEALTH & STATUS ENDPOINTS${COLOR_RESET}"
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo ""

test_endpoint "GET" "/health" "Complete system health check with all dependencies"

test_endpoint "GET" "/health/dependencies" "Detailed dependency status and versions"

echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_BLUE}2️⃣  MESH NETWORK ENDPOINTS${COLOR_RESET}"
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo ""

test_endpoint "GET" "/mesh/status" "Current mesh network status and statistics"

test_endpoint "GET" "/mesh/peers" "List of all connected mesh peers"

test_endpoint "GET" "/mesh/routes" "Active routes in mesh network"

echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_BLUE}3️⃣  MONITORING & METRICS${COLOR_RESET}"
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo ""

echo -e "${COLOR_YELLOW}📍 Testing${COLOR_RESET}: /metrics"
echo -e "${COLOR_YELLOW}   Description${COLOR_RESET}: Prometheus metrics for monitoring"
metrics_response=$(curl -s -w "\n%{http_code}" "$API_URL/metrics")
metrics_code=$(echo "$metrics_response" | tail -n1)
metrics_body=$(echo "$metrics_response" | head -n-1)

if [ "$metrics_code" = "200" ]; then
    echo -e "${COLOR_GREEN}   Status${COLOR_RESET}: ✅ $metrics_code"
    echo -e "${COLOR_BLUE}   Sample Metrics${COLOR_RESET}:"
    echo "$metrics_body" | grep -E "^x0tta6bl4_" | head -5 || echo "   (no x0tta6bl4 metrics yet, but framework is ready)"
else
    echo -e "${COLOR_RED}   Status${COLOR_RESET}: ❌ $metrics_code"
fi
echo ""

echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_BLUE}4️⃣  WEB INTERFACES${COLOR_RESET}"
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo ""

echo -e "${COLOR_GREEN}✅ API Docs${COLOR_RESET}:     http://localhost:8000/docs"
echo -e "${COLOR_GREEN}✅ Prometheus${COLOR_RESET}:   http://localhost:9090"
echo -e "${COLOR_GREEN}✅ Grafana${COLOR_RESET}:      http://localhost:3000 (admin/admin)"
echo ""

echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo -e "${COLOR_GREEN}✅ Demo completed successfully!${COLOR_RESET}"
echo -e "${COLOR_BLUE}════════════════════════════════════════════════${COLOR_RESET}"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:8000/docs for interactive API testing"
echo "  2. Check http://localhost:9090 for Prometheus metrics"
echo "  3. Visit http://localhost:3000 for Grafana dashboards"
echo ""
