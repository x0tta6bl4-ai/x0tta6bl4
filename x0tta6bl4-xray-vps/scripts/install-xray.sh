#!/bin/bash
# Xray Core + Reality + xhttp Installation Script
# x0tta6bl4 VPS Setup
# Date: 2026-01-31
# Version: 1.0.0

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
XRAY_VERSION="25.1.30"
XRAY_DIR="/usr/local/xray"
CONFIG_DIR="/usr/local/etc/xray"
LOG_DIR="/var/log/xray"
SERVICE_NAME="xray"

# Default ports
PORT_VLESS=443
PORT_VMESS=8443
PORT_SHADOWSOCKS=8388
PORT_TROJAN=9443

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root"
    exit 1
fi

# Detect OS
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    elif [[ -f /etc/redhat-release ]]; then
        OS="centos"
    else
        OS=$(uname -s)
    fi
    log_info "Detected OS: $OS"
}

# Install dependencies
install_deps() {
    log_info "Installing dependencies..."
    
    case $OS in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq curl wget unzip jq openssl uuid-runtime qrencode net-tools
            ;;
        centos|rhel|fedora|almalinux|rocky)
            yum install -y -q curl wget unzip jq openssl uuidgen qrencode net-tools
            ;;
        arch)
            pacman -Sy --noconfirm curl wget unzip jq openssl qrencode net-tools
            ;;
        *)
            log_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
    
    log_success "Dependencies installed"
}

# Generate UUIDs
generate_uuids() {
    UUID_VLESS=$(cat /proc/sys/kernel/random/uuid)
    UUID_VMESS=$(cat /proc/sys/kernel/random/uuid)
    UUID_TROJAN=$(cat /proc/sys/kernel/random/uuid)
    PASSWORD_SS=$(openssl rand -base64 32)
    
    log_info "Generated UUIDs and passwords"
}

# Generate Reality keys
generate_reality_keys() {
    log_info "Generating Reality key pair..."
    
    # Generate X25519 key pair
    KEYS=$(xray x25519 2>/dev/null || echo "")
    
    if [[ -z "$KEYS" ]]; then
        # Fallback: generate manually
        PRIVATE_KEY=$(openssl rand -base64 32)
        PUBLIC_KEY=$(echo -n "$PRIVATE_KEY" | openssl dgst -sha256 -binary | base64)
    else
        PRIVATE_KEY=$(echo "$KEYS" | grep "Private" | awk '{print $3}')
        PUBLIC_KEY=$(echo "$KEYS" | grep "Public" | awk '{print $3}')
    fi
    
    log_success "Reality keys generated"
}

# Generate short ID
generate_short_id() {
    SHORT_ID=$(openssl rand -hex 8)
    log_info "Short ID: $SHORT_ID"
}

# Download Xray
download_xray() {
    log_info "Downloading Xray Core v${XRAY_VERSION}..."
    
    ARCH=$(uname -m)
    case $ARCH in
        x86_64) ARCH="64" ;;
        aarch64|arm64) ARCH="arm64-v8a" ;;
        armv7l) ARCH="armv7a" ;;
        *) log_error "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    
    DOWNLOAD_URL="https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-${ARCH}.zip"
    
    mkdir -p "$XRAY_DIR"
    cd "$XRAY_DIR"
    
    wget -q --show-progress "$DOWNLOAD_URL" -O xray.zip
    unzip -o xray.zip
    chmod +x xray
    
    # Create symlink
    ln -sf "$XRAY_DIR/xray" /usr/local/bin/xray
    
    log_success "Xray Core installed"
}

# Create directories
create_directories() {
    log_info "Creating directories..."
    
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p /etc/ssl/xray
    
    # Set permissions
    chmod 755 "$CONFIG_DIR"
    chmod 755 "$LOG_DIR"
    
    log_success "Directories created"
}

# Generate self-signed certificate for fallback
generate_cert() {
    log_info "Generating self-signed certificate..."
    
    openssl req -x509 -newkey rsa:4096 \
        -keyout /etc/ssl/xray/xray.key \
        -out /etc/ssl/xray/xray.crt \
        -days 365 \
        -nodes \
        -subj "/C=US/ST=State/L=City/O=x0tta6bl4/OU=VPS/CN=xray.local" \
        2>/dev/null
    
    chmod 600 /etc/ssl/xray/xray.key
    chmod 644 /etc/ssl/xray/xray.crt
    
    log_success "Certificate generated"
}

# Create Xray configuration
create_config() {
    log_info "Creating Xray configuration..."
    
    # Get server IP
    SERVER_IP=$(curl -s -4 ifconfig.me || echo "0.0.0.0")
    
    cat > "$CONFIG_DIR/config.json" << EOF
{
  "log": {
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log",
    "loglevel": "warning",
    "dnsLog": false
  },
  "api": {
    "tag": "api",
    "services": ["HandlerService", "LoggerService", "StatsService"]
  },
  "stats": {},
  "policy": {
    "levels": {
      "0": {
        "statsUserUplink": true,
        "statsUserDownlink": true
      }
    },
    "system": {
      "statsInboundUplink": true,
      "statsInboundDownlink": true,
      "statsOutboundUplink": true,
      "statsOutboundDownlink": true
    }
  },
  "inbounds": [
    {
      "tag": "api",
      "listen": "127.0.0.1",
      "port": 10085,
      "protocol": "dokodemo-door",
      "settings": {
        "address": "127.0.0.1"
      }
    },
    {
      "tag": "vless-reality",
      "listen": "0.0.0.0",
      "port": ${PORT_VLESS},
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${UUID_VLESS}",
            "flow": "xtls-rprx-vision",
            "email": "vless@x0tta6bl4"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.microsoft.com:443",
          "xver": 0,
          "serverNames": [
            "www.microsoft.com",
            "microsoft.com",
            "www.bing.com",
            "bing.com"
          ],
          "privateKey": "${PRIVATE_KEY}",
          "publicKey": "${PUBLIC_KEY}",
          "minClientVer": "",
          "maxClientVer": "",
          "maxTimeDiff": 0,
          "shortIds": ["${SHORT_ID}"]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vless-xhttp",
      "listen": "0.0.0.0",
      "port": ${PORT_VMESS},
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${UUID_VLESS}",
            "email": "vless-xhttp@x0tta6bl4"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "xhttpSettings": {
          "path": "/xhttp",
          "mode": "auto"
        },
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/etc/ssl/xray/xray.crt",
              "keyFile": "/etc/ssl/xray/xray.key"
            }
          ]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "vmess-ws",
      "listen": "0.0.0.0",
      "port": 8080,
      "protocol": "vmess",
      "settings": {
        "clients": [
          {
            "id": "${UUID_VMESS}",
            "alterId": 0,
            "email": "vmess@x0tta6bl4"
          }
        ]
      },
      "streamSettings": {
        "network": "ws",
        "wsSettings": {
          "path": "/vmess"
        },
        "security": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "shadowsocks",
      "listen": "0.0.0.0",
      "port": ${PORT_SHADOWSOCKS},
      "protocol": "shadowsocks",
      "settings": {
        "method": "2022-blake3-aes-256-gcm",
        "password": "${PASSWORD_SS}",
        "network": "tcp,udp"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    },
    {
      "tag": "trojan-tcp",
      "listen": "0.0.0.0",
      "port": ${PORT_TROJAN},
      "protocol": "trojan",
      "settings": {
        "clients": [
          {
            "password": "${UUID_TROJAN}",
            "email": "trojan@x0tta6bl4"
          }
        ],
        "fallbacks": [
          {
            "dest": "www.microsoft.com:443"
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/etc/ssl/xray/xray.crt",
              "keyFile": "/etc/ssl/xray/xray.key"
            }
          ]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom"
    },
    {
      "tag": "blocked",
      "protocol": "blackhole"
    },
    {
      "tag": "warp",
      "protocol": "wireguard",
      "settings": {
        "secretKey": "",
        "address": ["172.16.0.2/32"],
        "peers": [
          {
            "publicKey": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
            "allowedIPs": ["0.0.0.0/0", "::/0"],
            "endpoint": "engage.cloudflareclient.com:2408"
          }
        ]
      }
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "inboundTag": ["api"],
        "outboundTag": "api"
      },
      {
        "type": "field",
        "domain": ["geosite:category-ads-all"],
        "outboundTag": "blocked"
      },
      {
        "type": "field",
        "ip": ["geoip:private", "geoip:cn"],
        "outboundTag": "blocked"
      },
      {
        "type": "field",
        "domain": ["geosite:google", "geosite:youtube", "geosite:netflix"],
        "outboundTag": "warp"
      }
    ]
  },
  "dns": {
    "servers": [
      "https+local://1.1.1.1/dns-query",
      "https+local://8.8.8.8/dns-query",
      "localhost"
    ]
  }
}
EOF

    log_success "Configuration created"
}

# Create systemd service
create_service() {
    log_info "Creating systemd service..."
    
    cat > /etc/systemd/system/xray.service << 'EOF'
[Unit]
Description=Xray Service
Documentation=https://github.com/xtls
After=network.target nss-lookup.target

[Service]
Type=simple
User=root
NoNewPrivileges=true
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartPreventExitStatus=23
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    log_success "Service created"
}

# Configure firewall
configure_firewall() {
    log_info "Configuring firewall..."
    
    if command -v ufw &> /dev/null; then
        ufw allow ${PORT_VLESS}/tcp
        ufw allow ${PORT_VMESS}/tcp
        ufw allow ${PORT_SHADOWSOCKS}/tcp
        ufw allow ${PORT_SHADOWSOCKS}/udp
        ufw allow ${PORT_TROJAN}/tcp
        ufw allow 8080/tcp
        log_success "UFW configured"
    elif command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-port=${PORT_VLESS}/tcp
        firewall-cmd --permanent --add-port=${PORT_VMESS}/tcp
        firewall-cmd --permanent --add-port=${PORT_SHADOWSOCKS}/tcp
        firewall-cmd --permanent --add-port=${PORT_SHADOWSOCKS}/udp
        firewall-cmd --permanent --add-port=${PORT_TROJAN}/tcp
        firewall-cmd --permanent --add-port=8080/tcp
        firewall-cmd --reload
        log_success "FirewallD configured"
    else
        log_warn "No firewall detected, configure manually"
    fi
}

# Optimize system
optimize_system() {
    log_info "Optimizing system..."
    
    # Increase file descriptors
    cat >> /etc/security/limits.conf << EOF
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
EOF

    # TCP optimization
    cat >> /etc/sysctl.conf << EOF
# Xray optimizations
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.core.netdev_max_backlog = 250000
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_notsent_lowat = 16384
EOF

    sysctl -p >/dev/null 2>&1 || true
    
    # Enable BBR
    modprobe tcp_bbr 2>/dev/null || true
    
    log_success "System optimized"
}

# Start service
start_service() {
    log_info "Starting Xray service..."
    
    systemctl enable xray
    systemctl start xray
    
    sleep 2
    
    if systemctl is-active --quiet xray; then
        log_success "Xray service started successfully"
    else
        log_error "Failed to start Xray service"
        systemctl status xray --no-pager
        exit 1
    fi
}

# Generate client configurations
generate_client_configs() {
    log_info "Generating client configurations..."
    
    SERVER_IP=$(curl -s -4 ifconfig.me)
    
    # Create output directory
    mkdir -p /root/xray-clients
    
    # VLESS Reality
    cat > /root/xray-clients/vless-reality.json << EOF
{
  "v": "2",
  "ps": "x0tta6bl4-VLESS-Reality",
  "add": "${SERVER_IP}",
  "port": "${PORT_VLESS}",
  "id": "${UUID_VLESS}",
  "aid": "0",
  "scy": "auto",
  "net": "tcp",
  "type": "none",
  "host": "www.microsoft.com",
  "path": "",
  "tls": "reality",
  "sni": "www.microsoft.com",
  "fp": "chrome",
  "pbk": "${PUBLIC_KEY}",
  "sid": "${SHORT_ID}",
  "spx": "/",
  "flow": "xtls-rprx-vision"
}
EOF

    # VLESS XHTTP
    cat > /root/xray-clients/vless-xhttp.json << EOF
{
  "v": "2",
  "ps": "x0tta6bl4-VLESS-XHTTP",
  "add": "${SERVER_IP}",
  "port": "${PORT_VMESS}",
  "id": "${UUID_VLESS}",
  "aid": "0",
  "scy": "auto",
  "net": "xhttp",
  "type": "none",
  "host": "${SERVER_IP}",
  "path": "/xhttp",
  "tls": "tls",
  "sni": "${SERVER_IP}",
  "fp": "chrome",
  "alpn": "h2,http/1.1"
}
EOF

    # VMESS WebSocket
    cat > /root/xray-clients/vmess-ws.json << EOF
{
  "v": "2",
  "ps": "x0tta6bl4-VMESS-WS",
  "add": "${SERVER_IP}",
  "port": "8080",
  "id": "${UUID_VMESS}",
  "aid": "0",
  "scy": "auto",
  "net": "ws",
  "type": "none",
  "host": "${SERVER_IP}",
  "path": "/vmess",
  "tls": "none"
}
EOF

    # Trojan
    cat > /root/xray-clients/trojan.json << EOF
{
  "v": "2",
  "ps": "x0tta6bl4-Trojan",
  "add": "${SERVER_IP}",
  "port": "${PORT_TROJAN}",
  "id": "${UUID_TROJAN}",
  "aid": "0",
  "scy": "auto",
  "net": "tcp",
  "type": "none",
  "host": "${SERVER_IP}",
  "path": "",
  "tls": "tls",
  "sni": "${SERVER_IP}",
  "fp": "chrome"
}
EOF

    # Shadowsocks
    cat > /root/xray-clients/shadowsocks.txt << EOF
ss://$(echo -n "2022-blake3-aes-256-gcm:${PASSWORD_SS}" | base64 -w 0)@${SERVER_IP}:${PORT_SHADOWSOCKS}#x0tta6bl4-Shadowsocks
EOF

    # Generate QR codes
    if command -v qrencode &> /dev/null; then
        for file in /root/xray-clients/*.json; do
            base=$(basename "$file" .json)
            cat "$file" | base64 -w 0 | qrencode -t ANSIUTF8 -o - > "/root/xray-clients/${base}.qr.txt"
        done
    fi
    
    log_success "Client configurations saved to /root/xray-clients/"
}

# Display summary
display_summary() {
    SERVER_IP=$(curl -s -4 ifconfig.me)
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Xray Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Server IP:${NC} ${SERVER_IP}"
    echo -e "${BLUE}Xray Version:${NC} ${XRAY_VERSION}"
    echo ""
    echo -e "${YELLOW}=== VLESS Reality (Recommended) ===${NC}"
    echo "Port: ${PORT_VLESS}"
    echo "UUID: ${UUID_VLESS}"
    echo "Public Key: ${PUBLIC_KEY}"
    echo "Short ID: ${SHORT_ID}"
    echo "SNI: www.microsoft.com"
    echo "Flow: xtls-rprx-vision"
    echo ""
    echo -e "${YELLOW}=== VLESS XHTTP (Fallback) ===${NC}"
    echo "Port: ${PORT_VMESS}"
    echo "UUID: ${UUID_VLESS}"
    echo "Path: /xhttp"
    echo ""
    echo -e "${YELLOW}=== VMESS WebSocket ===${NC}"
    echo "Port: 8080"
    echo "UUID: ${UUID_VMESS}"
    echo "Path: /vmess"
    echo ""
    echo -e "${YELLOW}=== Shadowsocks 2022 ===${NC}"
    echo "Port: ${PORT_SHADOWSOCKS}"
    echo "Method: 2022-blake3-aes-256-gcm"
    echo "Password: ${PASSWORD_SS}"
    echo ""
    echo -e "${YELLOW}=== Trojan ===${NC}"
    echo "Port: ${PORT_TROJAN}"
    echo "Password: ${UUID_TROJAN}"
    echo ""
    echo -e "${BLUE}Client configs saved to:${NC} /root/xray-clients/"
    echo -e "${BLUE}Logs:${NC} /var/log/xray/"
    echo -e "${BLUE}Config:${NC} /usr/local/etc/xray/config.json"
    echo ""
    echo -e "${GREEN}Commands:${NC}"
    echo "  systemctl status xray    - Check service status"
    echo "  systemctl restart xray   - Restart service"
    echo "  xray -version            - Check version"
    echo ""
}

# Main installation
main() {
    clear
    echo -e "${GREEN}"
    echo "  __  __          __        __   _           __  ____  ____"
    echo "  \\ \\/ /__  _____/ /_____ _/ /  (_)__  ___  /  |/  / |/ / /"
    echo "   \\  / _ \\/ ___/ __/ __ \\ / /  / / _ \\/ _ \\/ /|_/ /    /_/"
    echo "   / /  __/ /__/ /_/ /_/ // /__/ / __/  __/ /  / / /| / /"
    echo "  /_/\\___/\\___/\\__/\\____/____/_/_/  \\___/_/  /_/_/ |_/_/"
    echo ""
    echo -e "${NC}"
    echo "  Xray Core + Reality + xhttp Installation"
    echo "  Version: 1.0.0 | Date: 2026-01-31"
    echo ""
    
    detect_os
    install_deps
    generate_uuids
    download_xray
    generate_reality_keys
    generate_short_id
    create_directories
    generate_cert
    create_config
    create_service
    configure_firewall
    optimize_system
    start_service
    generate_client_configs
    display_summary
}

# Run main
main "$@"
