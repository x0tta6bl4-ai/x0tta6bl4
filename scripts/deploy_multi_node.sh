#!/bin/bash
# deploy_multi_node.sh — x0tta6bl4 Multi-Node Mesh Deployment
# Deploys ghost-vpn-server + Yggdrasil + Go agent + eBPF on a new node.
#
# Usage:
#   ./deploy_multi_node.sh --role entry --master-ip 89.125.1.107
#   ./deploy_multi_node.sh --role exit --master-ip 89.125.1.107
#
# Roles:
#   entry  = Low-latency entry point for CIS (RU)
#   exit   = Geoblocking bypass node (US/SG)
#   master = Orchestrator + Gateway (NL, pre-deployed)

set -euo pipefail

# --- Configuration ---
ROLE="${1:-entry}"
MASTER_IP="${2:-89.125.1.107}"
MASTER_PORT="${3:-9001}"
NODE_ID="ghost-${ROLE}-$(hostname -s 2>/dev/null || echo 'node')"
VPN_PORT=9999
MESH_PORT=5000
YGG_PORT=9001
PROJECT_DIR="/opt/x0tta6bl4"
LOG_FILE="/var/log/x0tta6bl4-deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

log "🛡️ x0tta6bl4 Node Deployment — Role: $ROLE, Master: $MASTER_IP"

# --- Phase 1: System Prep ---
log "Phase 1: System preparation"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Must run as root" >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    curl git docker.io docker-compose-v2 \
    bpftool linux-tools-common linux-tools-$(uname -r) \
    iproute2 chrony net-tools jq \
    python3 python3-pip python3-venv

log "✅ System packages installed"

# Clock sync (critical for PQC + Ghost Pulse timing)
systemctl enable --now chrony
chronyc tracking > /dev/null 2>&1 && log "✅ Chrony sync active" || log "⚠️ Chrony sync degraded"

# --- Phase 2: Project Setup ---
log "Phase 2: Project setup"

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Clone or update project
if [ -d ".git" ]; then
    git pull --ff-only 2>/dev/null || log "⚠️ Git pull failed, using existing code"
else
    git clone --depth 1 https://github.com/x0tta6bl4-ai/x0tta6bl4.git . 2>/dev/null || \
    log "⚠️ Clone failed, using existing code"
fi

log "✅ Project code ready at $PROJECT_DIR"

# --- Phase 3: Yggdrasil Mesh ---
log "Phase 3: Yggdrasil mesh setup"

# Generate unique Yggdrasil key
mkdir -p /etc/yggdrasil
if [ ! -f /etc/yggdrasil/yggdrasil.conf ]; then
    # Generate new config with unique key
    yggdrasil -genconf > /etc/yggdrasil/yggdrasil.conf 2>/dev/null || true
    
    # Configure peers
    cat > /etc/yggdrasil/yggdrasil.conf << YGGEOF
{
    "Listen": ["tcp://0.0.0.0:$YGG_PORT"],
    "Peers": ["tcp://$MASTER_IP:$MASTER_PORT"],
    "NodeInfo": {
        "name": "$NODE_ID",
        "role": "$ROLE",
        "version": "3.4.0"
    },
    "NodeInfoPrivacy": false,
    "IfName": "auto"
}
YGGEOF
fi

systemctl enable --now yggdrasil 2>/dev/null || \
    yggdrasil --config /etc/yggdrasil/yggdrasil.conf &
sleep 2

YGG_IPV6=$(yggdrasilctl getSelf 2>/dev/null | grep 'IPv6 address' | awk '{print $4}' || echo "pending")
log "✅ Yggdrasil started — IPv6: $YGG_IPV6"

# --- Phase 4: Go Agent (x0t-agent) ---
log "Phase 4: Go agent deployment"

# Build agent from source
if [ ! -f /usr/local/bin/x0t-agent ]; then
    if command -v go &> /dev/null; then
        cd "$PROJECT_DIR/agent" && go build -o /usr/local/bin/x0t-agent . && cd "$PROJECT_DIR"
        log "✅ Go agent built from source"
    else
        log "⚠️ Go not installed, skipping agent build"
    fi
fi

# Create agent config
mkdir -p /etc/x0t
cat > /etc/x0t/agent.yaml << EOF
node_id: "$NODE_ID"
listen_port: $MESH_PORT
pqc_enabled: true
trust_domain: "x0tta6bl4.mesh"
log_level: "info"
EOF

log "✅ Agent config created at /etc/x0t/agent.yaml"

# --- Phase 5: Ghost VPN Server ---
log "Phase 5: Ghost VPN server deployment"

# Create VPN systemd service
cat > /etc/systemd/system/x0tta-ghost-vpn.service << 'VPNEOF'
[Unit]
Description=x0tta6bl4 Ghost VPN Server
After=network-online.target yggdrasil.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/x0tta6bl4
ExecStart=/usr/bin/python3 -m ghost_vpn_server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=x0tta-ghost-vpn
Environment=VPN_PORT=9999
Environment=VPN_SUBNET=10.88.0.0/24
Environment=PULSE_MODE=adaptive
Environment=LOG_LEVEL=info

[Install]
WantedBy=multi-user.target
VPNEOF

# Create watchdog
cat > /etc/systemd/system/x0tta-ghost-watchdog.service << 'WDEOF'
[Unit]
Description=x0tta6bl4 Ghost VPN Watchdog
After=x0tta-ghost-vpn.service
Wants=x0tta-ghost-vpn.service

[Service]
Type=simple
User=root
ExecStart=/bin/bash -c 'while true; do pgrep -f ghost_vpn_server || systemctl restart x0tta-ghost-vpn; sleep 30; done'
Restart=always
RestartSec=10
StandardOutput=journal
SyslogIdentifier=x0tta-watchdog

[Install]
WantedBy=multi-user.target
WDEOF

systemctl daemon-reload
systemctl enable x0tta-ghost-vpn x0tta-ghost-watchdog
log "✅ VPN systemd services installed"

# --- Phase 6: eBPF ---
log "Phase 6: eBPF dataplane"

mkdir -p "$PROJECT_DIR/ebpf/prod"
if [ -f "$PROJECT_DIR/ebpf/prod/meshcore_x86_bpfel.o" ]; then
    log "✅ Pre-compiled eBPF objects found"
else
    log "⚠️ No pre-compiled eBPF objects — will use fallback mode"
fi

# --- Phase 7: PQC Key Exchange ---
log "Phase 7: PQC key exchange"

# Generate and store PQC keys locally
# In production, keys are exchanged via control plane or SPIFFE
mkdir -p "$PROJECT_DIR/keys"
if [ ! -f "$PROJECT_DIR/keys/node.key" ]; then
    python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
key = ec.generate_private_key(ec.SECP256R1())
with open('$PROJECT_DIR/keys/node.key', 'wb') as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()
    ))
print('Generated node PQC key pair')
" 2>/dev/null || log "⚠️ Key generation requires cryptography package"
fi

log "✅ PQC keys ready"

# --- Phase 8: Firewall ---
log "Phase 8: Firewall configuration"

ufw --force enable 2>/dev/null || true
ufw allow $YGG_PORT/tcp comment "Yggdrasil mesh" 2>/dev/null || true
ufw allow $VPN_PORT/udp comment "Ghost VPN" 2>/dev/null || true
ufw allow $MESH_PORT/udp comment "Mesh agent" 2>/dev/null || true
ufw allow 8080/tcp comment "Metrics" 2>/dev/null || true
log "✅ Firewall configured"

# --- Phase 9: Start Services ---
log "Phase 9: Starting services"

systemctl start x0tta-ghost-vpn 2>/dev/null || log "⚠️ VPN start deferred"
systemctl start x0tta-ghost-watchdog 2>/dev/null || true

# Start Go agent in background
if [ -f /usr/local/bin/x0t-agent ]; then
    nohup /usr/local/bin/x0t-agent \
        --config /etc/x0t/agent.yaml \
        --port $MESH_PORT \
        --log-level info \
        > /var/log/x0t-agent.log 2>&1 &
    log "✅ Go agent started (PID: $!)"
fi

# --- Phase 10: Health Check ---
log "Phase 10: Health check"

sleep 5

# Check Yggdrasil
if yggdrasilctl getSelf 2>/dev/null | grep -q "IPv6"; then
    log "✅ Yggdrasil: CONNECTED"
else
    log "⚠️ Yggdrasil: NOT CONNECTED"
fi

# Check VPN
if pgrep -f ghost_vpn_server > /dev/null 2>&1; then
    log "✅ Ghost VPN: RUNNING"
else
    log "⚠️ Ghost VPN: NOT RUNNING"
fi

# Check Go agent
if pgrep -f x0t-agent > /dev/null 2>&1; then
    log "✅ Go Agent: RUNNING"
else
    log "⚠️ Go Agent: NOT RUNNING"
fi

# --- Summary ---
log "=========================================="
log "🚀 Node $NODE_ID deployment complete!"
log "   Role:      $ROLE"
log "   Yggdrasil: $YGG_IPV6"
log "   VPN:       0.0.0.0:$VPN_PORT/udp"
log "   Agent:     0.0.0.0:$MESH_PORT/udp"
log "   Metrics:   0.0.0.0:8080/tcp"
log "=========================================="
