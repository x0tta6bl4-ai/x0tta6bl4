#!/bin/bash
# Collect Baseline Metrics Script
# Collects initial metrics for performance analysis

set -euo pipefail

VPS_IP="${1:-89.125.1.107}"
VPS_USER="${2:-root}"
OUTPUT_DIR="${3:-./metrics_baseline}"
VPS_PASS="${VPS_PASS:?Set VPS_PASS in environment}"

mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     📊 COLLECTING BASELINE METRICS                            ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# 1. Health endpoint
log_info "Collecting health metrics..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "curl -s http://localhost:8081/health" > "$OUTPUT_DIR/health_$TIMESTAMP.json"

# 2. Prometheus metrics
log_info "Collecting Prometheus metrics..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "curl -s http://localhost:8081/metrics" > "$OUTPUT_DIR/metrics_$TIMESTAMP.prom"

# 3. System resources
log_info "Collecting system resources..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "free -h && echo '---' && df -h / && echo '---' && uptime" > "$OUTPUT_DIR/system_$TIMESTAMP.txt"

# 4. Container stats
log_info "Collecting container stats..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "docker stats x0t-node --no-stream" > "$OUTPUT_DIR/container_stats_$TIMESTAMP.txt"

# 5. Network connections
log_info "Collecting network info..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "netstat -tulpn | grep -E '8081|10809|39829|9091|3000'" > "$OUTPUT_DIR/network_$TIMESTAMP.txt"

# 6. Process info
log_info "Collecting process info..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "ps aux | grep -E 'x0t-node|xray|nginx' | grep -v grep" > "$OUTPUT_DIR/processes_$TIMESTAMP.txt"

# 7. Recent logs (last 50 lines)
log_info "Collecting recent logs..."
sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "docker logs x0t-node --tail 50 2>&1" > "$OUTPUT_DIR/logs_$TIMESTAMP.txt"

# Create summary
log_info "Creating summary..."
cat > "$OUTPUT_DIR/summary_$TIMESTAMP.md" <<EOF
# Baseline Metrics Summary

**Date:** $(date)
**VPS:** $VPS_IP
**Timestamp:** $TIMESTAMP

## Files Collected

1. \`health_$TIMESTAMP.json\` - Health endpoint response
2. \`metrics_$TIMESTAMP.prom\` - Prometheus metrics
3. \`system_$TIMESTAMP.txt\` - System resources
4. \`container_stats_$TIMESTAMP.txt\` - Container statistics
5. \`network_$TIMESTAMP.txt\` - Network connections
6. \`processes_$TIMESTAMP.txt\` - Running processes
7. \`logs_$TIMESTAMP.txt\` - Recent application logs

## Quick Stats

\`\`\`
$(cat "$OUTPUT_DIR/health_$TIMESTAMP.json" | python3 -m json.tool 2>/dev/null || cat "$OUTPUT_DIR/health_$TIMESTAMP.json")
\`\`\`

\`\`\`
$(head -20 "$OUTPUT_DIR/system_$TIMESTAMP.txt")
\`\`\`

\`\`\`
$(cat "$OUTPUT_DIR/container_stats_$TIMESTAMP.txt")
\`\`\`

EOF

log_info "✅ Baseline metrics collected!"
log_info "📁 Output directory: $OUTPUT_DIR"
log_info "📊 Summary: $OUTPUT_DIR/summary_$TIMESTAMP.md"

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ Collection complete!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
