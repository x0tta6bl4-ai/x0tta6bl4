#!/bin/bash
# x0tta6bl4 Mesh Agent Installer (Go Data Plane Edition)
# Usage: curl -sL maas.x0tta6bl4.io/install | sudo bash -s -- --token <KEY>
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="/opt/x0tta6bl4-agent"
CONFIG_DIR="/etc/x0t"
DATA_DIR="/var/lib/x0t"
SERVICE_NAME="x0t-agent"

log() { echo -e "${GREEN}[x0t]${NC} $1"; }
err() { echo -e "${RED}[x0t] ERROR:${NC} $1" >&2; exit 1; }

# Parse args
TOKEN=""
API_URL="https://maas.x0tta6bl4.io"
while [[ $# -gt 0 ]]; do
    case $1 in
        --token) TOKEN="$2"; shift 2;;
        --api-url) API_URL="$2"; shift 2;;
        --help) echo "Usage: $0 --token <TOKEN> [--api-url <URL>]"; exit 0;;
        *) shift;;
    esac
done

[ -z "$TOKEN" ] && err "Join token required. Use: --token <TOKEN>"

log "x0tta6bl4 Mesh Agent Installer"

# Check root
[ "$EUID" -ne 0 ] && err "Run as root: sudo bash -s -- --token $TOKEN"

# Dependencies
log "Installing system dependencies..."
if command -v apt-get >/dev/null; then
    apt-get update -qq && apt-get install -y -qq python3-venv python3-pip curl jq xxd
elif command -v dnf >/dev/null; then
    dnf install -y -q python3-virtualenv python3-pip curl jq vim-common
else
    log "Warning: Please ensure python3-venv and curl are installed."
fi

# Create dirs
mkdir -p "$CONFIG_DIR" "$DATA_DIR" "/usr/local/bin"

log "Installing Agent Binary..."
# In a real environment, we'd curl this from a release URL.
# For this workspace, we copy from the local build path.
cp "agent/bin/x0t-agent" "/usr/local/bin/x0t-agent"
chmod +x "/usr/local/bin/x0t-agent"

# Generate config
NODE_ID="x0t-$(head -c 4 /dev/urandom | xxd -p)"
cat > "$CONFIG_DIR/agent.yaml" <<EOF
# x0tta6bl4 Mesh Agent Configuration
node_id: "$NODE_ID"
api_endpoint: "$API_URL"
join_token: "$TOKEN"
data_dir: "$DATA_DIR"
listen_port: 8080
pqc_enabled: true
EOF

log "Config written to $CONFIG_DIR/agent.yaml"

# Install systemd service
cat > /etc/systemd/system/$SERVICE_NAME.service <<UNIT
[Unit]
Description=x0tta6bl4 Mesh Agent (Go Data Plane)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/x0t-agent --config $CONFIG_DIR/agent.yaml
Restart=always
RestartSec=5
LimitNOFILE=65535

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA_DIR $CONFIG_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "  ${CYAN}x0tta6bl4 Agent Installed!${NC}"
log "  Node ID: $NODE_ID"
log "  Status:  systemctl status $SERVICE_NAME"
log "  Logs:    journalctl -u $SERVICE_NAME -f"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
