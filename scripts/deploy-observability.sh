#!/bin/bash
# WEST-0105-2 Deployment Script
# Purpose: Deploy Grafana dashboards, Prometheus alerts, and AlertManager rules
# Usage: ./deploy-observability.sh
# Time: ~30 minutes (automated)

set -e  # Exit on error

echo "======================================================================"
echo "WEST-0105-2: Observability Layer Deployment"
echo "======================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_API_KEY="${GRAFANA_API_KEY:-admin:admin}"

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PROMETHEUS_ALERTS_DIR="${PROJECT_ROOT}/prometheus/alerts"
ALERTMANAGER_CONFIG_DIR="${PROJECT_ROOT}/alertmanager"
GRAFANA_DASHBOARDS_DIR="${PROJECT_ROOT}/grafana/dashboards"

# =====================================================================
# FUNCTION: Print colored output
# =====================================================================
print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# =====================================================================
# FUNCTION: Check if service is running
# =====================================================================
check_service() {
    local service_name=$1
    local service_url=$2
    
    print_step "Checking if $service_name is running..."
    
    if curl -s "$service_url" > /dev/null 2>&1; then
        print_success "$service_name is running at $service_url"
        return 0
    else
        print_error "$service_name is NOT running at $service_url"
        return 1
    fi
}

# =====================================================================
# FUNCTION: Validate YAML syntax
# =====================================================================
validate_yaml() {
    local file=$1
    
    print_step "Validating YAML: $file"
    
    if command -v yamllint &> /dev/null; then
        if yamllint "$file"; then
            print_success "YAML validation passed"
            return 0
        else
            print_error "YAML validation failed"
            return 1
        fi
    else
        print_warning "yamllint not installed, skipping YAML validation"
        python3 -c "import yaml; yaml.safe_load(open('$file'))" && \
            print_success "YAML parsing successful" || \
            (print_error "YAML parsing failed"; return 1)
    fi
}

# =====================================================================
# STEP 1: Pre-flight checks
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 1: Pre-flight Checks ===${NC}"
echo ""

print_step "Checking prerequisites..."

# Check if required directories exist
if [ ! -d "$PROMETHEUS_ALERTS_DIR" ]; then
    print_error "Prometheus alerts directory not found: $PROMETHEUS_ALERTS_DIR"
    exit 1
fi
print_success "Prometheus alerts directory exists"

if [ ! -d "$ALERTMANAGER_CONFIG_DIR" ]; then
    print_error "AlertManager config directory not found: $ALERTMANAGER_CONFIG_DIR"
    exit 1
fi
print_success "AlertManager config directory exists"

# Check if configuration files exist
if [ ! -f "$PROMETHEUS_ALERTS_DIR/charter-alerts.yml" ]; then
    print_error "Alert rules file not found: $PROMETHEUS_ALERTS_DIR/charter-alerts.yml"
    exit 1
fi
print_success "Alert rules file exists"

if [ ! -f "$ALERTMANAGER_CONFIG_DIR/config.yml" ]; then
    print_error "AlertManager config file not found: $ALERTMANAGER_CONFIG_DIR/config.yml"
    exit 1
fi
print_success "AlertManager config file exists"

# =====================================================================
# STEP 2: Service health checks
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 2: Service Health Checks ===${NC}"
echo ""

check_service "Prometheus" "$PROMETHEUS_URL" || exit 1
check_service "AlertManager" "$ALERTMANAGER_URL" || exit 1
check_service "Grafana" "$GRAFANA_URL" || exit 1

# =====================================================================
# STEP 3: Validate alert rules
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 3: Validate Alert Rules ===${NC}"
echo ""

validate_yaml "$PROMETHEUS_ALERTS_DIR/charter-alerts.yml" || exit 1

# =====================================================================
# STEP 4: Validate AlertManager config
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 4: Validate AlertManager Config ===${NC}"
echo ""

validate_yaml "$ALERTMANAGER_CONFIG_DIR/config.yml" || exit 1

# =====================================================================
# STEP 5: Deploy Prometheus alerts
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 5: Deploy Prometheus Alert Rules ===${NC}"
echo ""

print_step "Deploying alert rules..."

# Note: This would need actual deployment procedure
# For now, just validate and show instruction
print_warning "Manual deployment required for Prometheus:"
echo "  1. Copy $PROMETHEUS_ALERTS_DIR/charter-alerts.yml to /etc/prometheus/rules/"
echo "  2. Add to /etc/prometheus/prometheus.yml:"
echo "     rule_files:"
echo "       - '/etc/prometheus/rules/charter-alerts.yml'"
echo "  3. Reload Prometheus: curl -X POST http://localhost:9090/-/reload"
echo ""

print_step "Verifying Prometheus can load alert rules (dry-run)..."
# Try to load the YAML in Python to validate
python3 << 'PYTHON_END'
import yaml
import sys

try:
    with open(sys.argv[1], 'r') as f:
        config = yaml.safe_load(f)
    alert_count = 0
    for group in config.get('groups', []):
        alert_count += len(group.get('rules', []))
    print(f"✓ Found {alert_count} alert rules in configuration")
    sys.exit(0)
except Exception as e:
    print(f"✗ Error loading alert rules: {e}")
    sys.exit(1)
PYTHON_END "$PROMETHEUS_ALERTS_DIR/charter-alerts.yml"

print_success "Alert rules validation successful"

# =====================================================================
# STEP 6: Deploy AlertManager configuration
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 6: Deploy AlertManager Configuration ===${NC}"
echo ""

print_step "Deploying AlertManager configuration..."
print_warning "Manual deployment required for AlertManager:"
echo "  1. Copy $ALERTMANAGER_CONFIG_DIR/config.yml to /etc/alertmanager/"
echo "  2. Set environment variables:"
echo "     export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/YOUR/WEBHOOK/URL'"
echo "     export PAGERDUTY_SERVICE_KEY='your-pagerduty-service-key'"
echo "  3. Reload AlertManager: curl -X POST http://localhost:9093/-/reload"
echo ""

# =====================================================================
# STEP 7: Verify metrics are flowing
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 7: Verify Metrics Flow ===${NC}"
echo ""

print_step "Checking if Charter metrics are being scraped..."

# Query Prometheus for Charter metrics
METRICS_COUNT=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=count(count%20by%20(__name__)%20(%7Bjob%3D%22westworld-charter%22%7D))" | \
    python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('data', {}).get('result', [])))" 2>/dev/null || echo "0")

if [ "$METRICS_COUNT" -gt 0 ]; then
    print_success "Found $METRICS_COUNT Charter metrics in Prometheus"
else
    print_warning "No Charter metrics found yet - may need time to scrape"
    echo "  Wait 60 seconds for first scrape, then:"
    echo "  curl -s 'http://localhost:9090/api/v1/query?query=westworld_charter_violations_total' | jq '.'"
fi

# =====================================================================
# STEP 8: Grafana datasource
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 8: Configure Grafana Prometheus Datasource ===${NC}"
echo ""

print_step "Checking Grafana Prometheus datasource..."

# Try to get existing datasource
DATASOURCE_RESPONSE=$(curl -s -u "$GRAFANA_API_KEY" \
    "$GRAFANA_URL/api/datasources/name/Prometheus-Charter" 2>/dev/null || echo "")

if [ -z "$DATASOURCE_RESPONSE" ]; then
    print_warning "Prometheus-Charter datasource not found, would need to create manually:"
    echo "  1. Go to $GRAFANA_URL/datasources"
    echo "  2. Add new datasource"
    echo "  3. Type: Prometheus"
    echo "  4. Name: Prometheus-Charter"
    echo "  5. URL: http://prometheus:9090"
    echo "  6. Click 'Save & Test'"
else
    print_success "Prometheus-Charter datasource already configured"
fi

# =====================================================================
# STEP 9: Test alert firing
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 9: Test Alert Firing ===${NC}"
echo ""

print_step "Instructions for testing alert firing:"
echo ""
echo "  Manual Test:"
echo "    1. Trigger a test violation in Charter app:"
echo "       curl -X POST http://charter-api:8000/test/violation \\"
echo "         -H 'Content-Type: application/json' \\"
echo "         -d '{\"severity\": \"CRITICAL\", \"type\": \"data_extraction\", \"node\": \"test_node\"}'"
echo ""
echo "    2. Wait 1-2 minutes for Prometheus to scrape and evaluate"
echo ""
echo "    3. Check Prometheus alerts:"
echo "       http://localhost:9090/alerts"
echo ""
echo "    4. Check Slack #charter-security for notification"
echo ""

# =====================================================================
# STEP 10: Summary
# =====================================================================
echo ""
echo -e "${BLUE}=== STEP 10: Deployment Summary ===${NC}"
echo ""

print_success "Deployment validation complete!"
echo ""
echo "Next Steps:"
echo "  1. Copy alert rules to Prometheus (see Step 5)"
echo "  2. Copy AlertManager config (see Step 6)"
echo "  3. Configure Grafana datasource (see Step 8)"
echo "  4. Import Grafana dashboards (JSON files in $GRAFANA_DASHBOARDS_DIR)"
echo "  5. Test alert firing (see Step 9)"
echo ""
echo "Useful URLs:"
echo "  - Prometheus:   $PROMETHEUS_URL"
echo "  - AlertManager: $ALERTMANAGER_URL"
echo "  - Grafana:      $GRAFANA_URL"
echo ""
echo "Documentation:"
echo "  - Metrics Reference:   docs/PROMETHEUS_METRICS.md"
echo "  - Implementation Plan:  WEST_0105_2_DASHBOARDS_PLAN.md"
echo "  - Implementation Steps: WEST_0105_2_IMPLEMENTATION_CHECKLIST.md"
echo "  - Deployment Status:    WEST_0105_DEPLOYMENT_READY.md"
echo ""
echo -e "${GREEN}======================================================================"
echo "WEST-0105-2 Deployment Validation Complete ✓"
echo "=====================================================================${NC}"
echo ""
