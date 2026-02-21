#!/bin/bash
# x0tta6bl4 System-wide Proxy Automation
# Configures GNOME/Linux proxy settings to route all traffic through the mesh.

set -e

PROXY_PORT=1080
PROXY_HOST="127.0.0.1"

GREEN='\033[0;32m'
NC='\033[0m'

enable_proxy() {
    echo -e "${GREEN}🔧 Configuring System Proxy (SOCKS5: $PROXY_HOST:$PROXY_PORT)...${NC}"
    gsettings set org.gnome.system.proxy mode 'manual'
    gsettings set org.gnome.system.proxy.socks host "$PROXY_HOST"
    gsettings set org.gnome.system.proxy.socks port "$PROXY_PORT"
    gsettings set org.gnome.system.proxy ignore-hosts "['localhost', '127.0.0.0/8', '::1']"
    echo -e "${GREEN}✅ System Proxy ENABLED.${NC}"
}

disable_proxy() {
    echo -e "${GREEN}🔧 Disabling System Proxy...${NC}"
    gsettings set org.gnome.system.proxy mode 'none'
    echo -e "${GREEN}✅ System Proxy DISABLED.${NC}"
}

status_proxy() {
    MODE=$(gsettings get org.gnome.system.proxy mode)
    echo -e "System Proxy Mode: ${GREEN}$MODE${NC}"
    if [[ "$MODE" == "'manual'" ]]; then
        HOST=$(gsettings get org.gnome.system.proxy.socks host)
        PORT=$(gsettings get org.gnome.system.proxy.socks port)
        echo -e "SOCKS5: $HOST:$PORT"
    fi
}

case "$1" in
    on) enable_proxy ;;
    off) disable_proxy ;;
    status) status_proxy ;;
    *) echo "Usage: $0 {on|off|status}" ;;
esac
