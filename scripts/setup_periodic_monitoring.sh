#!/bin/bash
# Setup Periodic Monitoring
# Creates cron job for periodic monitoring

set -euo pipefail

VPS_IP="${1:-89.125.1.107}"
VPS_USER="${2:-root}"
MONITOR_INTERVAL="${3:-60}"  # minutes

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║
║     ⏰ SETUP PERIODIC MONITORING                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Copy monitoring script to VPS
log_info "Copying monitoring script to VPS..."
sshpass -p 'tSiy6Il0gP4CIF39c4' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    scripts/monitor_production.sh $VPS_USER@$VPS_IP:/root/monitor_production.sh

# Create cron job
log_info "Setting up cron job (every $MONITOR_INTERVAL minutes)..."
CRON_JOB="*/$MONITOR_INTERVAL * * * * /root/monitor_production.sh $VPS_IP $VPS_USER >> /var/log/x0tta6bl4_monitor.log 2>&1"

sshpass -p 'tSiy6Il0gP4CIF39c4' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    $VPS_USER@$VPS_IP "echo '$CRON_JOB' | crontab -"

log_info "✅ Periodic monitoring setup complete!"
log_info "📋 Cron job: Every $MONITOR_INTERVAL minutes"
log_info "📁 Logs: /var/log/x0tta6bl4_monitor.log"

echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "✅ Setup complete!"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

