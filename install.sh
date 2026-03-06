#!/bin/bash
# x0tta6bl4 Production Installer (v3.3)
# Installs dependencies, sets up virtualenv, and configures systemd service.

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="/opt/x0tta6bl4"
USER="x0tta6bl4"
SERVICE_NAME="x0tta6bl4-node"

echo -e "${CYAN}
      ___       ___       ___       ___       ___       ___   
     /\  \     /\  \     /\  \     /\  \     /\  \     /\  \  
    /::\  \   /::\  \   /::\  \   /::\  \   /::\  \   /::\  \ 
   /:/\:\__\ /:/\:\__\ /:/\:\__\ /:/\:\__\ /:/\:\__\ /::\:\__\
   \:\/:/  / \:\/:/  / \:\/:/  / \:\/:/  / \:\/:/  / \/\::/  /
    \::/  /   \::/  /   \::/  /   \::/  /   \::/  /    /:/  / 
     \/__/     \/__/     \/__/     \/__/     \/__/     \/__/  
${NC}"
echo -e "${GREEN}Deploying 'The Living Network' (v3.3.0-rc1)...${NC}\n"

# 0. Argument Parsing
while [[ $# -gt 0 ]]; do
  case $1 in
    --node-id)
      NODE_ID="$2"
      shift 2
      ;;
    --token)
      JOIN_TOKEN="$2"
      shift 2
      ;;
    --mesh)
      MESH_ID="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# 1. Root Check
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run as root (sudo).${NC}"
  exit 1
fi

# 2. Dependencies
echo -e "${YELLOW}[1/5] Checking dependencies...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-dev build-essential libssl-dev git curl
echo -e "${GREEN}Dependencies installed.${NC}"

# 3. User Creation
echo -e "${YELLOW}[2/5] Creating service user...${NC}"
if id "$USER" &>/dev/null; then
    echo "User $USER already exists."
else
    useradd -r -s /bin/false "$USER"
    echo "User $USER created."
fi

# 4. Installation
echo -e "${YELLOW}[3/5] Installing application to $INSTALL_DIR...${NC}"
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR"

# Create production .env from template
if [ -f "$INSTALL_DIR/.env.example" ]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
else
  touch "$INSTALL_DIR/.env"
fi

# Apply MaaS provisioning if provided
if [ ! -z "$NODE_ID" ]; then
  echo "X0T_NODE_ID=$NODE_ID" >> "$INSTALL_DIR/.env"
  echo "X0T_MESH_ID=$MESH_ID" >> "$INSTALL_DIR/.env"
  echo "X0T_JOIN_TOKEN=$JOIN_TOKEN" >> "$INSTALL_DIR/.env"
fi

chown -R "$USER:$USER" "$INSTALL_DIR"

cd "$INSTALL_DIR"
# Setup venv as the service user to avoid permission issues
sudo -u "$USER" python3 -m venv .venv
sudo -u "$USER" .venv/bin/pip install --no-cache-dir --upgrade pip
sudo -u "$USER" .venv/bin/pip install --no-cache-dir -r requirements.lock
echo -e "${GREEN}Application installed.${NC}"

# 5. Systemd Service
echo -e "${YELLOW}[4/5] Configuring systemd...${NC}"
cat <<EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=x0tta6bl4 Mesh Node
After=network.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn src.core.app:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5
Environment=ENV=production
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
echo -e "${GREEN}Service configured.${NC}"

# 6. Start
echo -e "${YELLOW}[5/5] Starting node...${NC}"
# systemctl start $SERVICE_NAME 
# Commented out start to allow config before launch
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "\nTo start the node:\n  systemctl start $SERVICE_NAME"
echo -e "Check status:\n  systemctl status $SERVICE_NAME"
echo -e "View logs:\n  journalctl -u $SERVICE_NAME -f"
