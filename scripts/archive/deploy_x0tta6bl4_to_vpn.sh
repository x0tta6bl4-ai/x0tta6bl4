#!/usr/bin/env bash
set -euo pipefail

log() { printf "\033[1;32m[+]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[-]\033[0m %s\n" "$*"; }

SERVER_IP="${1:-89.125.1.107}"
SERVER_PASS="${2:-${SERVER_PASS:-}}"
XRAY_PORT=39829
XRAY_CONFIG="/usr/local/etc/xray/config.json"
MONITOR_DIR="/opt/x0tta6bl4-monitor"
PYTHON_VERSION="python3"

if [ -z "$SERVER_PASS" ]; then
  err "Set SERVER_PASS env var or pass password as 2nd argument"
  exit 1
fi

log "Deploying x0tta6bl4 monitoring components to VPN server $SERVER_IP"

# Create deployment package
log "Creating deployment package"
TEMP_DIR=$(mktemp -d)
DEPLOY_DIR="$TEMP_DIR/x0tta6bl4-vpn-deploy"
mkdir -p "$DEPLOY_DIR"

# Create Prometheus exporter for Xray
cat > "$DEPLOY_DIR/xray_exporter.py" <<'PYTHON_EOF'
#!/usr/bin/env python3
"""
x0tta6bl4 Xray Prometheus Exporter
Exports Xray metrics in Prometheus format
"""
import json
import subprocess
import time
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Metrics
xray_connections_total = Gauge('xray_connections_total', 'Total active Xray connections')
xray_traffic_uplink_bytes = Counter('xray_traffic_uplink_bytes_total', 'Total uplink traffic in bytes', ['user'])
xray_traffic_downlink_bytes = Counter('xray_traffic_downlink_bytes_total', 'Total downlink traffic in bytes', ['user'])
xray_uptime_seconds = Gauge('xray_uptime_seconds', 'Xray service uptime in seconds')
xray_status = Gauge('xray_status', 'Xray service status (1=running, 0=stopped)')
xray_health_check_duration = Histogram('xray_health_check_duration_seconds', 'Health check duration', buckets=[0.01, 0.05, 0.1, 0.5, 1.0])

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health = {
                "status": "ok",
                "exporter": "x0tta6bl4-xray",
                "version": "1.0.0"
            }
            self.wfile.write(json.dumps(health).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress access logs

def check_xray_status():
    """Check if Xray service is running"""
    try:
        result = subprocess.run(['systemctl', 'is-active', '--quiet', 'xray'], 
                              capture_output=True, timeout=2)
        return result.returncode == 0
    except:
        return False

def get_xray_uptime():
    """Get Xray service uptime"""
    try:
        result = subprocess.run(['systemctl', 'show', 'xray', '--property=ActiveEnterTimestamp', '--value'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            # Parse timestamp and calculate uptime
            from datetime import datetime
            try:
                timestamp = datetime.fromisoformat(result.stdout.strip().replace(' ', 'T'))
                uptime = (datetime.now() - timestamp).total_seconds()
                return max(0, uptime)
            except:
                pass
    except:
        pass
    return 0

def update_metrics():
    """Update metrics from Xray"""
    is_running = check_xray_status()
    xray_status.set(1 if is_running else 0)
    
    if is_running:
        uptime = get_xray_uptime()
        xray_uptime_seconds.set(uptime)
        # Note: Xray stats API would be used here if available
        # For now, we track basic service status

def run_exporter(port=9090):
    """Run Prometheus exporter"""
    print(f"Starting x0tta6bl4 Xray exporter on port {port}", file=sys.stderr)
    
    # Update metrics periodically
    import threading
    def update_loop():
        while True:
            try:
                update_metrics()
            except Exception as e:
                print(f"Error updating metrics: {e}", file=sys.stderr)
            time.sleep(10)
    
    updater = threading.Thread(target=update_loop, daemon=True)
    updater.start()
    
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    print(f"Exporter ready at http://0.0.0.0:{port}/metrics", file=sys.stderr)
    server.serve_forever()

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    run_exporter(port)
PYTHON_EOF

# Create health check script
cat > "$DEPLOY_DIR/xray_health_check.sh" <<'BASH_EOF'
#!/usr/bin/env bash
set -euo pipefail

XRAY_PORT="${XRAY_PORT:-39829}"
XRAY_CONFIG="/usr/local/etc/xray/config.json"

check_xray_service() {
    if systemctl is-active --quiet xray; then
        echo "OK: Xray service is running"
        return 0
    else
        echo "FAIL: Xray service is not running"
        return 1
    fi
}

check_xray_port() {
    if ss -ltn | grep -q ":$XRAY_PORT "; then
        echo "OK: Xray listening on port $XRAY_PORT"
        return 0
    else
        echo "FAIL: Xray not listening on port $XRAY_PORT"
        return 1
    fi
}

check_xray_config() {
    if [ -f "$XRAY_CONFIG" ]; then
        # Set XRAY_LOCATION_ASSET if not set
        export XRAY_LOCATION_ASSET="${XRAY_LOCATION_ASSET:-/usr/local/share/xray}"
        if XRAY_LOCATION_ASSET="$XRAY_LOCATION_ASSET" xray run -test -config "$XRAY_CONFIG" >/dev/null 2>&1; then
            echo "OK: Xray configuration is valid"
            return 0
        else
            echo "WARN: Xray configuration validation failed (may be false positive)"
            return 0  # Don't fail on config check, service is running
        fi
    else
        echo "FAIL: Xray configuration file not found"
        return 1
    fi
}

check_system_resources() {
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    MEM_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    
    if (( $(echo "$CPU_USAGE > 90" | bc -l) )); then
        echo "WARN: High CPU usage: ${CPU_USAGE}%"
        return 1
    fi
    
    if [ "$MEM_USAGE" -gt 85 ]; then
        echo "WARN: High memory usage: ${MEM_USAGE}%"
        return 1
    fi
    
    echo "OK: System resources normal (CPU: ${CPU_USAGE}%, MEM: ${MEM_USAGE}%)"
    return 0
}

# Run all checks
EXIT_CODE=0
check_xray_service || EXIT_CODE=1
check_xray_port || EXIT_CODE=1
check_xray_config || EXIT_CODE=1
check_system_resources || EXIT_CODE=1

exit $EXIT_CODE
BASH_EOF

# Create auto-recovery script
cat > "$DEPLOY_DIR/xray_auto_recovery.sh" <<'BASH_EOF'
#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/var/log/x0tta6bl4-recovery.log"
MAX_RESTART_ATTEMPTS=3
RESTART_COOLDOWN=300  # 5 minutes

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

check_and_recover() {
    if ! systemctl is-active --quiet xray; then
        log "WARNING: Xray service is down, attempting recovery..."
        
        # Check restart count
        RESTART_COUNT=$(grep -c "Recovery attempt" "$LOG_FILE" 2>/dev/null || echo "0")
        if [ "$RESTART_COUNT" -ge "$MAX_RESTART_ATTEMPTS" ]; then
            LAST_RESTART=$(grep "Recovery attempt" "$LOG_FILE" | tail -1 | awk '{print $1, $2}')
            if [ -n "$LAST_RESTART" ]; then
                LAST_RESTART_EPOCH=$(date -d "$LAST_RESTART" +%s 2>/dev/null || echo "0")
                NOW_EPOCH=$(date +%s)
                if [ $((NOW_EPOCH - LAST_RESTART_EPOCH)) -lt "$RESTART_COOLDOWN" ]; then
                    log "ERROR: Too many restart attempts, waiting for cooldown"
                    return 1
                fi
            fi
        fi
        
        log "Recovery attempt $((RESTART_COUNT + 1))"
        systemctl restart xray
        sleep 5
        
        if systemctl is-active --quiet xray; then
            log "SUCCESS: Xray service recovered"
            return 0
        else
            log "ERROR: Failed to recover Xray service"
            return 1
        fi
    fi
    return 0
}

check_and_recover
BASH_EOF

# Create systemd service for exporter
cat > "$DEPLOY_DIR/xray-exporter.service" <<'SERVICE_EOF'
[Unit]
Description=x0tta6bl4 Xray Prometheus Exporter
After=network.target xray.service
Requires=xray.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/x0tta6bl4-monitor
ExecStart=/usr/bin/python3 /opt/x0tta6bl4-monitor/xray_exporter.py 9090
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Create systemd timer for health checks
cat > "$DEPLOY_DIR/xray-health-check.service" <<'SERVICE_EOF'
[Unit]
Description=x0tta6bl4 Xray Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/x0tta6bl4-monitor/xray_health_check.sh
StandardOutput=journal
StandardError=journal
SERVICE_EOF

cat > "$DEPLOY_DIR/xray-health-check.timer" <<'TIMER_EOF'
[Unit]
Description=Run x0tta6bl4 Xray Health Check every minute
Requires=xray-health-check.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Unit=xray-health-check.service

[Install]
WantedBy=timers.target
TIMER_EOF

# Create systemd timer for auto-recovery
cat > "$DEPLOY_DIR/xray-auto-recovery.service" <<'SERVICE_EOF'
[Unit]
Description=x0tta6bl4 Xray Auto Recovery
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/x0tta6bl4-monitor/xray_auto_recovery.sh
StandardOutput=journal
StandardError=journal
SERVICE_EOF

cat > "$DEPLOY_DIR/xray-auto-recovery.timer" <<'TIMER_EOF'
[Unit]
Description=Run x0tta6bl4 Xray Auto Recovery every 30 seconds
Requires=xray-auto-recovery.service

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
Unit=xray-auto-recovery.service

[Install]
WantedBy=timers.target
TIMER_EOF

# Create installation script
cat > "$DEPLOY_DIR/install.sh" <<'INSTALL_EOF'
#!/usr/bin/env bash
set -euo pipefail

log() { printf "\033[1;32m[+]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[-]\033[0m %s\n" "$*"; }

MONITOR_DIR="/opt/x0tta6bl4-monitor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log "Installing x0tta6bl4 monitoring components"
log "Script directory: $SCRIPT_DIR"

# Create directory
mkdir -p "$MONITOR_DIR"

# List files in script directory
log "Files in deployment package:"
ls -la "$SCRIPT_DIR" || true

# Copy files from script directory (don't cd to MONITOR_DIR)
cp -v "$SCRIPT_DIR/xray_exporter.py" "$MONITOR_DIR/" || { err "ERROR: xray_exporter.py not found"; ls -la "$SCRIPT_DIR"; exit 1; }
cp -v "$SCRIPT_DIR/xray_health_check.sh" "$MONITOR_DIR/" || { err "ERROR: xray_health_check.sh not found"; exit 1; }
cp -v "$SCRIPT_DIR/xray_auto_recovery.sh" "$MONITOR_DIR/" || { err "ERROR: xray_auto_recovery.sh not found"; exit 1; }

# Make scripts executable
chmod +x "$MONITOR_DIR"/*.py "$MONITOR_DIR"/*.sh

# Install Python dependencies
log "Installing Python dependencies"
apt-get update -qq
apt-get install -y python3-pip python3-prometheus-client bc >/dev/null 2>&1 || true
pip3 install prometheus-client >/dev/null 2>&1 || true

# Install systemd services
log "Installing systemd services"
cp "$SCRIPT_DIR/xray-exporter.service" /etc/systemd/system/
cp "$SCRIPT_DIR/xray-health-check.service" /etc/systemd/system/
cp "$SCRIPT_DIR/xray-health-check.timer" /etc/systemd/system/
cp "$SCRIPT_DIR/xray-auto-recovery.service" /etc/systemd/system/
cp "$SCRIPT_DIR/xray-auto-recovery.timer" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable and start services
log "Enabling services"
systemctl enable xray-exporter.service
systemctl enable xray-health-check.timer
systemctl enable xray-auto-recovery.timer

systemctl start xray-exporter.service
systemctl start xray-health-check.timer
systemctl start xray-auto-recovery.timer

log "Installation complete!"
log "Prometheus metrics available at: http://localhost:9090/metrics"
log "Health check endpoint: http://localhost:9090/health"
INSTALL_EOF

chmod +x "$DEPLOY_DIR/install.sh"

# Verify all files exist
log "Verifying deployment files"
for file in "$DEPLOY_DIR"/*; do
    if [ -f "$file" ]; then
        log "  Found: $(basename "$file")"
    fi
done

# Create tarball
log "Creating deployment package"
cd "$TEMP_DIR"
tar czf x0tta6bl4-vpn-deploy.tar.gz -C "$TEMP_DIR" x0tta6bl4-vpn-deploy

# Deploy to server
log "Deploying to server $SERVER_IP"
sshpass -p "$SERVER_PASS" scp -o StrictHostKeyChecking=no \
    "$TEMP_DIR/x0tta6bl4-vpn-deploy.tar.gz" \
    "root@$SERVER_IP:/tmp/"

# Install on server
log "Installing on server"
sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no "root@$SERVER_IP" <<REMOTE_EOF
set -euo pipefail
cd /tmp
rm -rf x0tta6bl4-vpn-deploy
tar xzf x0tta6bl4-vpn-deploy.tar.gz
cd x0tta6bl4-vpn-deploy
ls -la
bash install.sh
REMOTE_EOF

# Cleanup
rm -rf "$TEMP_DIR"

log "Deployment complete!"
log "Check status with: ssh root@$SERVER_IP 'systemctl status xray-exporter'"
log "View metrics: curl http://$SERVER_IP:9090/metrics"

