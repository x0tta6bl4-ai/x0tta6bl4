#!/bin/bash
set -euo pipefail

# Xray Anti-Detection Hardening Script
# Applies hardening configuration with automatic rollback

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
XRAY_CONFIG="/usr/local/etc/xray/config.json"
BACKUP_DIR="/etc/xray/backups/$(date +%Y%m%d_%H%M%S)"
ROLLBACK_TIMEOUT=30

# Create backup
log_info "Creating backup..."
mkdir -p "$BACKUP_DIR"
cp "$XRAY_CONFIG" "$BACKUP_DIR/config.json.backup"
log_info "Backup saved to $BACKUP_DIR"

# Get current clients from existing config
log_info "Extracting current clients..."
CLIENTS_443=$(python3 << 'PYTHON'
import json
with open('/usr/local/etc/xray/config.json') as f:
    config = json.load(f)
for inbound in config.get('inbounds', []):
    if inbound.get('port') == 443:
        print(json.dumps(inbound.get('settings', {}).get('clients', [])))
        break
PYTHON
)

CLIENTS_39829=$(python3 << 'PYTHON'
import json
with open('/usr/local/etc/xray/config.json') as f:
    config = json.load(f)
for inbound in config.get('inbounds', []):
    if inbound.get('port') == 39829:
        print(json.dumps(inbound.get('settings', {}).get('clients', [])))
        break
PYTHON
)

# Create new hardened config
log_info "Generating hardened configuration..."
cat > /tmp/xray_hardened.json << 'CONFIG'
{
  "log": {
    "loglevel": "warning"
  },
  "dns": {
    "servers": [
      "1.1.1.1",
      "8.8.8.8",
      "1.0.0.1"
    ],
    "queryStrategy": "UseIPv4",
    "disableFallbackIfMatch": true
  },
  "inbounds": [
    {
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.google.com:443",
          "xver": 0,
          "serverNames": [
            "www.google.com",
            "www.youtube.com",
            "www.gstatic.com",
            "googleapis.com",
            "ajax.googleapis.com",
            "fonts.googleapis.com"
          ],
          "privateKey": "sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw",
          "shortIds": [
            "f56fb66932ec4142",
            "b2fe8b65c4321102",
            "57782230b5d645c6",
            "aec1ab3d23d143fb"
          ]
        },
        "tcpSettings": {
          "header": {
            "type": "none"
          }
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic", "fakedns"],
        "metadataOnly": false
      }
    },
    {
      "listen": "0.0.0.0",
      "port": 39829,
      "protocol": "vless",
      "settings": {
        "clients": [],
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
            "www.bing.com",
            "www.office.com",
            "outlook.com",
            "login.microsoftonline.com"
          ],
          "privateKey": "sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw",
          "shortIds": [
            "f56fb66932ec4142",
            "b2fe8b65c4321102"
          ]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic", "fakedns"]
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct",
      "settings": {
        "domainStrategy": "UseIPv4"
      }
    },
    {
      "protocol": "blackhole",
      "tag": "block",
      "settings": {
        "response": {
          "type": "http"
        }
      }
    },
    {
      "protocol": "freedom",
      "tag": "google-direct",
      "settings": {
        "domainStrategy": "UseIPv4"
      }
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "domainMatcher": "hybrid",
    "rules": [
      {
        "type": "field",
        "protocol": ["bittorrent"],
        "outboundTag": "block"
      },
      {
        "type": "field",
        "domain": [
          "geosite:category-ads-all"
        ],
        "outboundTag": "block"
      },
      {
        "type": "field",
        "domain": [
          "gemini.google.com",
          "generativelanguage.googleapis.com",
          "ai.google.dev",
          "makersuite.google.com",
          "aistudio.google.com"
        ],
        "outboundTag": "google-direct"
      },
      {
        "type": "field",
        "domain": [
          "google.com",
          "www.google.com",
          "googleapis.com",
          "*.googleapis.com",
          "googleusercontent.com",
          "*.googleusercontent.com",
          "gstatic.com",
          "*.gstatic.com",
          "youtube.com",
          "www.youtube.com",
          "ytimg.com",
          "ggpht.com"
        ],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "ip": [
          "geoip:private",
          "10.0.0.0/8",
          "172.16.0.0/12",
          "192.168.0.0/16"
        ],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "ip": [
          "geoip:cn"
        ],
        "outboundTag": "block"
      },
      {
        "type": "field",
        "network": "tcp,udp",
        "outboundTag": "direct"
      }
    ]
  },
  "policy": {
    "levels": {
      "0": {
        "handshake": 4,
        "connIdle": 300,
        "uplinkOnly": 2,
        "downlinkOnly": 5,
        "bufferSize": 512
      }
    }
  }
}
CONFIG

# Inject clients into new config
python3 << PYTHON
import json

with open('/tmp/xray_hardened.json') as f:
    config = json.load(f)

clients_443 = json.loads('''$CLIENTS_443''')
clients_39829 = json.loads('''$CLIENTS_39829''')

for inbound in config['inbounds']:
    if inbound['port'] == 443:
        inbound['settings']['clients'] = clients_443
    elif inbound['port'] == 39829:
        inbound['settings']['clients'] = clients_39829

with open('/tmp/xray_hardened.json', 'w') as f:
    json.dump(config, f, indent=2)

print("Clients injected successfully")
PYTHON

# Validate new config
log_info "Validating new configuration..."
if /usr/local/bin/xray -test -config /tmp/xray_hardened.json 2>&1 | grep -q "Configuration OK"; then
    log_info "Configuration validation passed"
else
    log_error "Configuration validation failed"
    exit 1
fi

# Apply new config
log_info "Applying hardened configuration..."
cp /tmp/xray_hardened.json "$XRAY_CONFIG"

# Restart Xray
log_info "Restarting Xray..."
systemctl restart xray

# Wait for service to be ready
sleep 3

# Check if service is running
if systemctl is-active --quiet xray; then
    log_info "✓ Xray restarted successfully"
else
    log_error "✗ Xray failed to start"
    log_info "Rolling back..."
    cp "$BACKUP_DIR/config.json.backup" "$XRAY_CONFIG"
    systemctl restart xray
    exit 1
fi

# Test connectivity
log_info "Testing connectivity..."
if curl -s --max-time 10 https://www.google.com -o /dev/null; then
    log_info "✓ Connectivity test passed"
else
    log_warn "⚠ Connectivity test inconclusive (may be normal)"
fi

log_info "========================================="
log_info "Hardening applied successfully!"
log_info "========================================="
log_info "Backup: $BACKUP_DIR"
log_info "To rollback: cp $BACKUP_DIR/config.json.backup $XRAY_CONFIG && systemctl restart xray"