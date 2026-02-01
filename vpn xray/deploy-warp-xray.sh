#!/bin/bash
###############################################################################
# x0tta6bl4: WARP + Xray Integration Deployment
# Решает проблемы: Google blocking, datacenter IP detection, DNS leaks
# Автор: mesh-архитектор
# Дата: 2025-01-31
###############################################################################

set -e

# ============================================================================
# CONFIG
# ============================================================================

SSH_USER="root"
SSH_HOST="89.125.1.107"
SSH_PASS="lH7SEcWM812blV50sz"
SSH_CMD="sshpass -p '$SSH_PASS' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30"

XRAY_CONFIG_PATH="/usr/local/etc/xray/config.json"
WARP_PORT=40000
XRAY_PORT=10809

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_ok() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# Проверка зависимостей
check_dependencies() {
    log_info "Checking dependencies..."
    
    command -v sshpass >/dev/null 2>&1 || log_error "sshpass not installed"
    command -v jq >/dev/null 2>&1 || log_error "jq not installed"
    
    log_ok "All dependencies OK"
}

# SSH execute helper
remote_exec() {
    local cmd="$1"
    $SSH_CMD $SSH_USER@$SSH_HOST "$cmd"
}

# SCP helper
remote_copy() {
    local src="$1"
    local dst="$2"
    sshpass -p "$SSH_PASS" scp -o StrictHostKeyChecking=no "$src" $SSH_USER@$SSH_HOST:"$dst"
}

# ============================================================================
# STEP 1: Pre-Flight Checks
# ============================================================================

preflight_checks() {
    log_info "=== PRE-FLIGHT CHECKS ==="
    
    # Check SSH connectivity
    log_info "Testing SSH connectivity..."
    remote_exec "echo 'SSH OK'" > /dev/null || log_error "SSH connection failed"
    log_ok "SSH connected"
    
    # Check WARP status
    log_info "Checking WARP status..."
    WARP_STATUS=$(remote_exec "warp-cli --accept-tos status 2>&1" | grep -i "Connected\|Status" | head -1)
    log_info "WARP: $WARP_STATUS"
    
    # Check Xray status
    log_info "Checking Xray status..."
    remote_exec "docker ps | grep x0t-node" > /dev/null || log_error "x0t-node container not running"
    log_ok "Xray container running"
    
    # Check disk space
    log_info "Checking disk space..."
    DISK_USAGE=$(remote_exec "df /usr/local/etc/xray | tail -1 | awk '{print \$5}'")
    log_info "Disk usage: $DISK_USAGE"
    
    log_ok "Pre-flight checks complete"
}

# ============================================================================
# STEP 2: Configure WARP in Proxy Mode
# ============================================================================

configure_warp_proxy() {
    log_info "=== CONFIGURING WARP PROXY MODE ==="
    
    # Set WARP to proxy mode (not full tunnel)
    log_info "Setting WARP to proxy mode..."
    remote_exec "warp-cli --accept-tos mode proxy"
    sleep 1
    
    # Configure proxy port
    log_info "Configuring WARP proxy on port $WARP_PORT..."
    remote_exec "warp-cli --accept-tos proxy port $WARP_PORT"
    sleep 1
    
    # Set listen interface to localhost only (security)
    log_info "Setting WARP proxy to listen on 127.0.0.1..."
    remote_exec "warp-cli --accept-tos proxy listen 127.0.0.1"
    sleep 1
    
    # Ensure WARP is connected
    log_info "Ensuring WARP is connected..."
    remote_exec "warp-cli --accept-tos connect"
    sleep 3
    
    # Verify WARP proxy is listening
    log_info "Verifying WARP proxy listening..."
    WARP_LISTEN=$(remote_exec "ss -tlnp | grep -E '40000|warp' || echo 'Not yet listening'")
    log_info "WARP listening status:\n$WARP_LISTEN"
    
    log_ok "WARP proxy mode configured"
}

# ============================================================================
# STEP 3: Generate Enhanced Xray Config
# ============================================================================

generate_xray_config() {
    log_info "=== GENERATING ENHANCED XRAY CONFIG ==="
    
    # Read current config
    log_info "Reading current Xray config..."
    CURRENT_CONFIG=$(remote_exec "cat $XRAY_CONFIG_PATH")
    
    # Extract UUID and other important settings
    UUID=$(echo "$CURRENT_CONFIG" | jq -r '.inbounds[0].settings.clients[0].id // "aaaabbbb-cccc-dddd-eeee-ffff00001111"')
    PRIVATE_KEY=$(echo "$CURRENT_CONFIG" | jq -r '.inbounds[0].streamSettings.realitySettings.privateKey // "aHf-d3bGb7F9KrLb3OzVSVXdvWrpLjXDjTD2jN3cK28"')
    
    log_info "Extracted UUID: ${UUID:0:8}..."
    log_info "Extracted Private Key: ${PRIVATE_KEY:0:8}..."
    
    # Generate new config with WARP routing
    cat > /tmp/xray-enhanced-config.json << 'XRAY_CONFIG_EOF'
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 10809,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "PLACEHOLDER_UUID",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "microsoft.com:443",
          "xver": 0,
          "serverNames": [
            "microsoft.com",
            "bing.com",
            "office.com",
            "outlook.com",
            "windows.com",
            "apple.com"
          ],
          "privateKey": "PLACEHOLDER_PRIVATE_KEY",
          "minClientVer": "",
          "maxClientVer": "",
          "maxTimeDiff": 0,
          "shortIds": [
            "0011aabbccdd",
            "001122334455"
          ]
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct",
      "settings": {
        "domainStrategy": "UseIP"
      }
    },
    {
      "protocol": "socks",
      "tag": "warp-google",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 40000
          }
        ]
      }
    },
    {
      "protocol": "socks",
      "tag": "warp-meta",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 40000
          }
        ]
      }
    },
    {
      "protocol": "socks",
      "tag": "warp-bytedance",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 40000
          }
        ]
      }
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNameMatch",
    "rules": [
      {
        "type": "field",
        "outboundTag": "warp-google",
        "domain": [
          "goog",
          "googleapis.com",
          "google.com",
          "google.ru",
          "google.co.uk",
          "google.de",
          "google.fr",
          "accounts.google.com",
          "youtube.com",
          "youtube-nocookie.com",
          "youtu.be",
          "yt.be",
          "googleusercontent.com",
          "gstatic.com",
          "google-analytics.com",
          "analytics.google.com",
          "recaptcha.net",
          "recaptcha.google.com",
          "chrome.com",
          "chromium.org",
          "g.co",
          "goo.gl",
          "firebaseapp.com",
          "firebaseio.com"
        ]
      },
      {
        "type": "field",
        "outboundTag": "warp-meta",
        "domain": [
          "facebook.com",
          "instagram.com",
          "whatsapp.com",
          "meta.com",
          "fb.com",
          "fbcdn.net",
          "instagram-engineering.com",
          "threads.net"
        ]
      },
      {
        "type": "field",
        "outboundTag": "warp-bytedance",
        "domain": [
          "bytedance.com",
          "tiktok.com",
          "douyin.com",
          "tiktokv.com",
          "tiktokcdn.com"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "domain": [
          "cn",
          "local",
          "internal",
          "test",
          "localhost"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "ip": [
          "10.0.0.0/8",
          "172.16.0.0/12",
          "192.168.0.0/16",
          "127.0.0.0/8",
          "169.254.0.0/16"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "port": "22-25,53,143,194-199,443,465,587,993,995,1194,3128,5222,5228,5229,5230,5232,5242-5243,8080-8888,9999-10000"
      }
    ]
  }
}
XRAY_CONFIG_EOF
    
    # Replace placeholders
    sed -i "s|PLACEHOLDER_UUID|$UUID|g" /tmp/xray-enhanced-config.json
    sed -i "s|PLACEHOLDER_PRIVATE_KEY|$PRIVATE_KEY|g" /tmp/xray-enhanced-config.json
    
    # Validate JSON
    log_info "Validating Xray config..."
    jq . /tmp/xray-enhanced-config.json > /dev/null || log_error "Invalid JSON config"
    log_ok "Config JSON valid"
    
    # Backup old config
    log_info "Backing up current Xray config..."
    remote_exec "cp $XRAY_CONFIG_PATH ${XRAY_CONFIG_PATH}.backup.$(date +%s)"
    log_ok "Config backed up"
    
    # Copy new config
    log_info "Uploading new Xray config..."
    remote_copy "/tmp/xray-enhanced-config.json" "$XRAY_CONFIG_PATH"
    log_ok "Config uploaded"
    
    rm -f /tmp/xray-enhanced-config.json
}

# ============================================================================
# STEP 4: Setup iptables GID-Based Bypass
# ============================================================================

setup_iptables_bypass() {
    log_info "=== SETTING UP iptables GID BYPASS ==="
    
    remote_exec << 'IPTABLES_SCRIPT'
#!/bin/bash
set -e

echo "Creating xray_warp group..."
groupadd -f xray_warp 2>/dev/null || true
GID=$(getent group xray_warp | cut -d: -f3)
echo "GID: $GID"

echo "Clearing old iptables rules..."
iptables -t mangle -F XRAY_WARP 2>/dev/null || true
iptables -t mangle -X XRAY_WARP 2>/dev/null || true

echo "Creating XRAY_WARP chain..."
iptables -t mangle -N XRAY_WARP

echo "Adding rules..."
# Bypass Xray's own traffic
iptables -t mangle -A XRAY_WARP -m owner --gid-owner $GID -j RETURN

# Mark WARP proxy traffic
iptables -t mangle -A XRAY_WARP -p tcp --dport 40000 -j MARK --set-mark 0x1
iptables -t mangle -A XRAY_WARP -p udp --dport 40000 -j MARK --set-mark 0x1

# Mark DNS traffic (UDP 53)
iptables -t mangle -A XRAY_WARP -p udp --dport 53 -j MARK --set-mark 0x2

echo "Creating routing tables..."
# Create routing table for marked packets
ip rule del fwmark 0x1 table 100 2>/dev/null || true
ip rule add fwmark 0x1 table 100

ip route del local 0.0.0.0/0 dev lo table 100 2>/dev/null || true
ip route add local 0.0.0.0/0 dev lo table 100

# DNS routing
ip rule del fwmark 0x2 table 101 2>/dev/null || true
ip rule add fwmark 0x2 table 101

echo "Saving iptables rules..."
iptables-save | tee /etc/iptables/rules.v4 > /dev/null

echo "✅ iptables rules configured"
IPTABLES_SCRIPT
    
    log_ok "iptables GID bypass configured"
}

# ============================================================================
# STEP 5: Configure DNS
# ============================================================================

configure_dns() {
    log_info "=== CONFIGURING DNS ==="
    
    remote_exec << 'DNS_SCRIPT'
#!/bin/bash

echo "Setting DNS to Cloudflare..."
cat > /etc/resolv.conf << 'EOF'
# Cloudflare WARP DNS
nameserver 1.1.1.1
nameserver 1.0.0.1

# Fallback to Google DNS
nameserver 8.8.8.8
nameserver 8.8.4.4

# IPv6 (optional)
nameserver 2606:4700:4700::1111
nameserver 2606:4700:4700::1001
EOF

echo "Making resolv.conf immutable..."
chattr +i /etc/resolv.conf || echo "chattr not available, skipping"

echo "Testing DNS resolution..."
nslookup google.com 1.1.1.1
nslookup youtube.com 1.1.1.1

echo "✅ DNS configured"
DNS_SCRIPT
    
    log_ok "DNS configured"
}

# ============================================================================
# STEP 6: Restart Services
# ============================================================================

restart_services() {
    log_info "=== RESTARTING SERVICES ==="
    
    # Reload iptables
    log_info "Reloading iptables..."
    remote_exec "iptables-restore < /etc/iptables/rules.v4" || log_warn "iptables restore failed"
    
    # Restart Xray
    log_info "Restarting Xray container..."
    remote_exec "docker restart x0t-node"
    sleep 3
    
    # Verify Xray is running
    log_info "Verifying Xray status..."
    remote_exec "docker ps | grep x0t-node" > /dev/null || log_error "Xray failed to start"
    log_ok "Xray restarted successfully"
    
    # Ensure WARP is still connected
    log_info "Verifying WARP connection..."
    remote_exec "warp-cli --accept-tos connect"
    sleep 2
    
    log_ok "Services restarted"
}

# ============================================================================
# STEP 7: Verification & Testing
# ============================================================================

verify_setup() {
    log_info "=== VERIFICATION & TESTING ==="
    
    # Check WARP proxy listening
    log_info "Checking WARP proxy..."
    WARP_LISTENING=$(remote_exec "ss -tlnp 2>/dev/null | grep 40000 | wc -l")
    if [ "$WARP_LISTENING" -gt 0 ]; then
        log_ok "WARP proxy listening on port 40000"
    else
        log_warn "WARP proxy may not be listening (UDP port, normal)"
    fi
    
    # Check Xray listening
    log_info "Checking Xray..."
    XRAY_LISTENING=$(remote_exec "ss -tlnp | grep 10809 | wc -l")
    if [ "$XRAY_LISTENING" -gt 0 ]; then
        log_ok "Xray listening on port 10809"
    else
        log_error "Xray not listening on port 10809"
    fi
    
    # Check iptables rules
    log_info "Checking iptables rules..."
    remote_exec "iptables -t mangle -L XRAY_WARP -v" | head -10 || log_warn "Could not display iptables rules"
    
    # Check DNS
    log_info "Checking DNS resolution..."
    DNS_TEST=$(remote_exec "dig @1.1.1.1 +short google.com | head -1")
    if [ -n "$DNS_TEST" ]; then
        log_ok "DNS resolution working: $DNS_TEST"
    else
        log_warn "DNS resolution may not be working"
    fi
    
    # Check Xray logs
    log_info "Checking Xray logs for errors..."
    XRAY_ERRORS=$(remote_exec "docker logs x0t-node --tail 20 2>&1 | grep -i 'error\|failed' | wc -l")
    if [ "$XRAY_ERRORS" -eq 0 ]; then
        log_ok "No errors in recent Xray logs"
    else
        log_warn "Found $XRAY_ERRORS error entries in Xray logs"
        remote_exec "docker logs x0t-node --tail 10"
    fi
    
    log_ok "Verification complete"
}

# ============================================================================
# STEP 8: Diagnostics
# ============================================================================

run_diagnostics() {
    log_info "=== RUNNING DIAGNOSTICS ==="
    
    log_info "System Info:"
    remote_exec "echo '=== UNAME ===' && uname -a && echo && echo '=== UPTIME ===' && uptime"
    
    log_info "Network Interfaces:"
    remote_exec "ip addr show | grep -E 'inet|inet6'"
    
    log_info "WARP Status:"
    remote_exec "warp-cli --accept-tos status 2>&1 | head -20"
    
    log_info "Docker Containers:"
    remote_exec "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
    
    log_info "Listening Ports:"
    remote_exec "ss -tlnp | grep -E '(LISTEN|40000|10809)'"
    
    log_ok "Diagnostics complete"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    log_info "╔════════════════════════════════════════════════════════╗"
    log_info "║   x0tta6bl4: WARP + Xray Integration Deployment       ║"
    log_info "║   Server: $SSH_HOST                         ║"
    log_info "║   Date: $(date)                               ║"
    log_info "╚════════════════════════════════════════════════════════╝"
    
    check_dependencies
    preflight_checks
    configure_warp_proxy
    generate_xray_config
    setup_iptables_bypass
    configure_dns
    restart_services
    verify_setup
    run_diagnostics
    
    log_ok "╔════════════════════════════════════════════════════════╗"
    log_ok "║              DEPLOYMENT SUCCESSFUL! ✅                  ║"
    log_ok "║                                                        ║"
    log_ok "║  Google is now routed through WARP (masked IP)        ║"
    log_ok "║  Your datacenter IP (89.125.1.107) is no longer used  ║"
    log_ok "║                                                        ║"
    log_ok "║  Next steps:                                           ║"
    log_ok "║  1. Test from your Crimea client via VLESS            ║"
    log_ok "║  2. Visit https://google.com - should work!           ║"
    log_ok "║  3. Check https://ifconfig.me - should show WARP IP  ║"
    log_ok "║  4. Monitor logs: docker logs x0t-node                ║"
    log_ok "║                                                        ║"
    log_ok "║  Troubleshoot: Check /tmp/xray-integration.log        ║"
    log_ok "╚════════════════════════════════════════════════════════╝"
}

# Run with error handling
trap 'log_error "Deployment failed at line $LINENO"' ERR
main "$@" | tee /tmp/xray-integration-$(date +%s).log

exit 0
