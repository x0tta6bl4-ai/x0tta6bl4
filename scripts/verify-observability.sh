#!/bin/bash
# WEST-0105 Verification Script
# Purpose: Verify observability stack health and configuration
# Usage: ./verify-observability.sh

set -e

echo "======================================================================"
echo "WEST-0105: Observability Stack Verification"
echo "======================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
CHARTER_API="${CHARTER_API:-http://localhost:8000}"

check_service() {
    local name=$1
    local url=$2
    
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name is running"
        return 0
    else
        echo -e "${RED}✗${NC} $name is NOT running: $url"
        return 1
    fi
}

echo -e "${BLUE}=== Service Health Checks ===${NC}"
echo ""

check_service "Prometheus" "$PROMETHEUS_URL" || true
check_service "AlertManager" "$ALERTMANAGER_URL" || true
check_service "Grafana" "$GRAFANA_URL" || true
check_service "Charter API" "$CHARTER_API/health" || true

echo ""
echo -e "${BLUE}=== Prometheus Alert Rules ===${NC}"
echo ""

# Check alert rules
ALERTS=$(curl -s "$PROMETHEUS_URL/api/v1/rules" 2>/dev/null | \
    python3 -c "import sys, json; data=json.load(sys.stdin); print(len([r for g in data.get('data', {}).get('groups', []) for r in g.get('rules', [])]))" 2>/dev/null || echo "0")

if [ "$ALERTS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Alert rules loaded: $ALERTS rules"
else
    echo -e "${YELLOW}!${NC} No alert rules found (expected 11)"
fi

echo ""
echo -e "${BLUE}=== Charter Metrics ===${NC}"
echo ""

# Check metrics
METRICS=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=count(westworld_charter_violations_total)" 2>/dev/null | \
    python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('data', {}).get('result', [])))" 2>/dev/null || echo "0")

if [ "$METRICS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Charter metrics flowing: westworld_charter_violations_total found"
else
    echo -e "${YELLOW}!${NC} No Charter metrics found yet (may need time to scrape)"
fi

echo ""
echo -e "${BLUE}=== Configuration Files ===${NC}"
echo ""

# Check configuration files
FILES=(
    "prometheus/alerts/charter-alerts.yml"
    "alertmanager/config.yml"
    "prometheus/prometheus.yml"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $file exists"
    else
        echo -e "${RED}✗${NC} $file NOT FOUND"
    fi
done

echo ""
echo -e "${BLUE}=== Documentation ===${NC}"
echo ""

DOCS=(
    "docs/PROMETHEUS_METRICS.md"
    "WEST_0105_2_IMPLEMENTATION_CHECKLIST.md"
    "WEST_0105_QUICK_REFERENCE.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "${GREEN}✓${NC} $doc exists"
    else
        echo -e "${RED}✗${NC} $doc NOT FOUND"
    fi
done

echo ""
echo -e "${GREEN}======================================================================"
echo "Verification Complete"
echo "======================================================================${NC}"
echo ""
echo "Next Steps:"
echo "  1. Follow: WEST_0105_2_IMPLEMENTATION_CHECKLIST.md"
echo "  2. Start: Phase 2A - Prometheus Alert Rules Deployment"
echo "  3. Reference: WEST_0105_QUICK_REFERENCE.md"
echo ""
