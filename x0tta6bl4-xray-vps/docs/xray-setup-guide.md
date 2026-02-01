# Xray Core Setup Guide for x0tta6bl4 VPS

## Overview

This guide provides production-ready configuration for Xray Core on VPS 89.125.1.107 with Reality + xhttp fallback, optimized for FlClashX client compatibility.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         x0tta6bl4 VPS (89.125.1.107)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Xray Core (v25.1.1)                             │   │
│  │                                                                     │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │   │
│  │  │  VLESS-      │    │  VLESS-      │    │  Trojan-     │          │   │
│  │  │  XTLS-       │    │  XTLS-       │    │  gRPC        │          │   │
│  │  │  Reality     │    │  xhttp       │    │  (fallback)  │          │   │
│  │  │  :443        │    │  :8443       │    │  :2083       │          │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘          │   │
│  │         │                   │                   │                   │   │
│  │         └───────────────────┴───────────────────┘                   │   │
│  │                         │                                          │   │
│  │              ┌──────────┴──────────┐                              │   │
│  │              │   Routing Engine    │                              │   │
│  │              │  (geosite/geoip)    │                              │   │
│  │              └──────────┬──────────┘                              │   │
│  │                         │                                          │   │
│  │         ┌───────────────┼───────────────┐                         │   │
│  │         ▼               ▼               ▼                         │   │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                    │   │
│  │  │ Freedom  │    │  Block   │    │  DNS     │                    │   │
│  │  │ (direct) │    │ (reject) │    │ (resolve)│                    │   │
│  │  └──────────┘    └──────────┘    └──────────┘                    │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Monitoring & Management                         │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │   │
│  │  │Prometheus│  │  Xray-   │  │  Health  │  │  MAPE-K  │           │   │
│  │  │Exporter  │  │  API     │  │  Check   │  │  Loop    │           │   │
│  │  │:9100     │  │:8080     │  │  Script  │  │          │           │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

```bash
# System requirements
- Ubuntu 22.04 LTS or Debian 12
- 1+ vCPU, 1GB+ RAM
- Dedicated IPv4 address
- Domain name (for TLS certificates)
- Firewall ports: 22, 443, 8443, 2083, 8080, 9100

# Domain setup
DOMAIN="x0tta6bl4.example.com"
REALITY_DEST="www.microsoft.com"  # Or other high-traffic site
```

## Installation

### Step 1: System Preparation

```bash
#!/bin/bash
# prepare-system.sh

set -euo pipefail

# Update system
apt-get update && apt-get upgrade -y

# Install dependencies
apt-get install -y \
    curl wget git jq \
    socat iptables-persistent \
    net-tools dnsutils \
    uuid-runtime openssl

# Enable BBR congestion control
cat >> /etc/sysctl.conf << 'EOF'
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF
sysctl -p

# Configure firewall
iptables -F
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow established
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow Xray ports
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT
iptables -A INPUT -p tcp --dport 2083 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
iptables -A INPUT -p tcp --dport 9100 -j ACCEPT

# Save rules
netfilter-persistent save

echo "System preparation complete"
```

### Step 2: Install Xray Core

```bash
#!/bin/bash
# install-xray.sh

set -euo pipefail

XRAY_VERSION="v25.1.1"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/usr/local/etc/xray"

# Download Xray
ARCH=$(uname -m)
case $ARCH in
    x86_64) ARCH_SUFFIX="64" ;;
    aarch64) ARCH_SUFFIX="arm64-v8a" ;;
    *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

DOWNLOAD_URL="https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-${ARCH_SUFFIX}.zip"

cd /tmp
wget -q "$DOWNLOAD_URL" -O xray.zip
unzip -o xray.zip -d xray-install
mv xray-install/xray "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/xray"

# Create directories
mkdir -p "${CONFIG_DIR}"
mkdir -p /var/log/xray
mkdir -p /usr/share/xray

# Download geo files
wget -q https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat -O /usr/share/xray/geosite.dat
wget -q https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat -O /usr/share/xray/geoip.dat

# Create user
useradd -r -s /bin/false xray || true

# Set permissions
chown -R xray:xray /var/log/xray
chown -R xray:xray /usr/share/xray

echo "Xray Core ${XRAY_VERSION} installed successfully"
```

### Step 3: Generate Reality Keys

```bash
#!/bin/bash
# generate-reality-keys.sh

set -euo pipefail

# Generate X25519 key pair
KEY_PAIR=$(/usr/local/bin/xray x25519)
PRIVATE_KEY=$(echo "$KEY_PAIR" | grep "Private key:" | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEY_PAIR" | grep "Public key:" | awk '{print $3}')

# Generate UUIDs
UUID_VLESS=$(cat /proc/sys/kernel/random/uuid)
UUID_TROJAN=$(cat /proc/sys/kernel/random/uuid)

# Generate short ID (8 hex chars)
SHORT_ID=$(openssl rand -hex 4)

# Save to file
cat > /usr/local/etc/xray/reality-keys.json << EOF
{
  "private_key": "${PRIVATE_KEY}",
  "public_key": "${PUBLIC_KEY}",
  "short_id": "${SHORT_ID}",
  "uuid_vless": "${UUID_VLESS}",
  "uuid_trojan": "${UUID_TROJAN}",
  "generated_at": "$(date -Iseconds)"
}
EOF

echo "Reality keys generated:"
echo "  Public Key: ${PUBLIC_KEY}"
echo "  Short ID: ${SHORT_ID}"
echo "  UUID VLESS: ${UUID_VLESS}"
```

## Configuration

### Main Xray Config (config.json)

```json
{
  "log": {
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log",
    "loglevel": "warning",
    "dnsLog": false
  },
  "api": {
    "tag": "api",
    "services": [
      "HandlerService",
      "LoggerService",
      "StatsService"
    ]
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
      "port": 8080,
      "protocol": "dokodemo-door",
      "settings": {
        "address": "127.0.0.1"
      }
    },
    {
      "tag": "vless-reality",
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "UUID_VLESS",
            "flow": "xtls-rprx-vision",
            "level": 0
          }
        ],
        "decryption": "none",
        "fallbacks": [
          {
            "dest": "8443",
            "xver": 1
          }
        ]
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
            "x0tta6bl4.example.com"
          ],
          "privateKey": "PRIVATE_KEY",
          "shortIds": [
            "SHORT_ID"
          ]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls",
          "quic"
        ]
      }
    },
    {
      "tag": "vless-xhttp",
      "listen": "0.0.0.0",
      "port": 8443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "UUID_VLESS",
            "level": 0
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "xhttp",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/usr/local/etc/xray/cert.pem",
              "keyFile": "/usr/local/etc/xray/key.pem"
            }
          ]
        },
        "xhttpSettings": {
          "path": "/xhttp",
          "mode": "auto"
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls"
        ]
      }
    },
    {
      "tag": "trojan-grpc",
      "listen": "0.0.0.0",
      "port": 2083,
      "protocol": "trojan",
      "settings": {
        "clients": [
          {
            "password": "UUID_TROJAN",
            "level": 0
          }
        ],
        "fallbacks": []
      },
      "streamSettings": {
        "network": "grpc",
        "security": "tls",
        "tlsSettings": {
          "certificates": [
            {
              "certificateFile": "/usr/local/etc/xray/cert.pem",
              "keyFile": "/usr/local/etc/xray/key.pem"
            }
          ]
        },
        "grpcSettings": {
          "serviceName": "trojan-service"
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls"
        ]
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
      "protocol": "blackhole",
      "settings": {
        "response": {
          "type": "http"
        }
      }
    },
    {
      "tag": "dns-out",
      "protocol": "dns"
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "inboundTag": [
          "api"
        ],
        "outboundTag": "api"
      },
      {
        "type": "field",
        "port": "53",
        "network": "udp",
        "outboundTag": "dns-out"
      },
      {
        "type": "field",
        "ip": [
          "geoip:private"
        ],
        "outboundTag": "blocked"
      },
      {
        "type": "field",
        "domain": [
          "geosite:category-ads-all",
          "geosite:category-ads-ru"
        ],
        "outboundTag": "blocked"
      },
      {
        "type": "field",
        "domain": [
          "geosite:google",
          "geosite:google-cn",
          "geosite:netflix",
          "geosite:spotify",
          "geosite:telegram"
        ],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "ip": [
          "geoip:cn"
        ],
        "outboundTag": "blocked"
      }
    ]
  },
  "dns": {
    "servers": [
      "https+local://1.1.1.1/dns-query",
      "https+local://8.8.8.8/dns-query",
      {
        "address": "https://1.1.1.1/dns-query",
        "domains": [
          "geosite:geolocation-!cn"
        ]
      }
    ],
    "queryStrategy": "UseIP"
  }
}
```

## FlClashX Client Configuration

### VLESS Reality

```yaml
proxies:
  - name: "x0tta6bl4-reality"
    type: vless
    server: 89.125.1.107
    port: 443
    uuid: UUID_VLESS
    flow: xtls-rprx-vision
    tls: true
    skip-cert-verify: false
    servername: www.microsoft.com
    reality-opts:
      public-key: PUBLIC_KEY
      short-id: SHORT_ID
    network: tcp
    udp: true
```

### VLESS xhttp

```yaml
proxies:
  - name: "x0tta6bl4-xhttp"
    type: vless
    server: 89.125.1.107
    port: 8443
    uuid: UUID_VLESS
    tls: true
    skip-cert-verify: false
    servername: x0tta6bl4.example.com
    network: xhttp
    xhttp-opts:
      path: /xhttp
      mode: auto
```

### Trojan gRPC

```yaml
proxies:
  - name: "x0tta6bl4-trojan"
    type: trojan
    server: 89.125.1.107
    port: 2083
    password: UUID_TROJAN
    tls: true
    skip-cert-verify: false
    network: grpc
    grpc-opts:
      service-name: trojan-service
```

## Systemd Service

```ini
# /etc/systemd/system/xray.service
[Unit]
Description=Xray Core Service
Documentation=https://github.com/XTLS/Xray-core
After=network.target nss-lookup.target

[Service]
Type=simple
User=xray
Group=xray
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=3s
LimitNOFILE=655350
LimitNPROC=655350

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/xray
ReadOnlyPaths=/usr/share/xray /usr/local/etc/xray

[Install]
WantedBy=multi-user.target
```

## Health Check Script

```bash
#!/bin/bash
# health-check.sh

XRAY_API="127.0.0.1:8080"
LOG_FILE="/var/log/xray/health-check.log"

# Check if Xray is running
if ! pgrep -x "xray" > /dev/null; then
    echo "$(date): ERROR - Xray process not running" >> "$LOG_FILE"
    systemctl restart xray
    exit 1
fi

# Check API availability
if ! curl -s "http://${XRAY_API}/stats/query" > /dev/null 2>&1; then
    echo "$(date): WARNING - Xray API not responding" >> "$LOG_FILE"
fi

# Check port bindings
for port in 443 8443 2083; do
    if ! ss -tlnp | grep -q ":${port}"; then
        echo "$(date): ERROR - Port ${port} not listening" >> "$LOG_FILE"
        systemctl restart xray
        exit 1
    fi
done

# Check certificate validity
if [[ -f /usr/local/etc/xray/cert.pem ]]; then
    CERT_EXPIRY=$(openssl x509 -in /usr/local/etc/xray/cert.pem -noout -dates | grep notAfter | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$CERT_EXPIRY" +%s)
    CURRENT_EPOCH=$(date +%s)
    DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
    
    if [[ $DAYS_UNTIL_EXPIRY -lt 7 ]]; then
        echo "$(date): WARNING - Certificate expires in ${DAYS_UNTIL_EXPIRY} days" >> "$LOG_FILE"
    fi
fi

echo "$(date): Health check passed" >> "$LOG_FILE"
exit 0
```

## Next Steps

1. Run deployment scripts
2. Configure FlClashX clients
3. Set up monitoring
4. Test all protocols
5. Document client configurations
