#!/bin/bash
# Performance Analysis Script
# Analyzes collected metrics and compares with baseline

set -euo pipefail

BASELINE_DIR="${1:-./metrics_baseline}"
CURRENT_DIR="${2:-./metrics_current}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║
║     📊 PERFORMANCE ANALYSIS                                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [ ! -d "$BASELINE_DIR" ]; then
    log_error "Baseline directory not found: $BASELINE_DIR"
    log_info "Run: ./scripts/collect_baseline_metrics.sh first"
    exit 1
fi

# Find latest baseline
LATEST_BASELINE=$(ls -t "$BASELINE_DIR"/summary_*.md 2>/dev/null | head -1)
if [ -z "$LATEST_BASELINE" ]; then
    log_error "No baseline found in $BASELINE_DIR"
    exit 1
fi

log_info "Using baseline: $LATEST_BASELINE"
echo ""

# Extract key metrics from baseline
log_info "Analyzing baseline metrics..."

BASELINE_HEALTH=$(find "$BASELINE_DIR" -name "health_*.json" -type f | head -1)
if [ -n "$BASELINE_HEALTH" ]; then
    log_info "Baseline health:"
    cat "$BASELINE_HEALTH" | python3 -m json.tool 2>/dev/null || cat "$BASELINE_HEALTH"
    echo ""
fi

BASELINE_CONTAINER=$(find "$BASELINE_DIR" -name "container_stats_*.txt" -type f | head -1)
if [ -n "$BASELINE_CONTAINER" ]; then
    log_info "Baseline container stats:"
    cat "$BASELINE_CONTAINER"
    echo ""
fi

BASELINE_SYSTEM=$(find "$BASELINE_DIR" -name "system_*.txt" -type f | head -1)
if [ -n "$BASELINE_SYSTEM" ]; then
    log_info "Baseline system resources:"
    cat "$BASELINE_SYSTEM"
    echo ""
fi

# If current metrics exist, compare
if [ -d "$CURRENT_DIR" ] && [ -n "$(ls -A $CURRENT_DIR 2>/dev/null)" ]; then
    log_info "Comparing with current metrics..."
    
    CURRENT_HEALTH=$(find "$CURRENT_DIR" -name "health_*.json" -type f | head -1)
    if [ -n "$CURRENT_HEALTH" ]; then
        log_info "Current health:"
        cat "$CURRENT_HEALTH" | python3 -m json.tool 2>/dev/null || cat "$CURRENT_HEALTH"
        echo ""
    fi
else
    log_warn "No current metrics found. Collect current metrics first:"
    log_info "  ./scripts/collect_baseline_metrics.sh 89.125.1.107 root ./metrics_current"
fi

log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ Analysis complete!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

