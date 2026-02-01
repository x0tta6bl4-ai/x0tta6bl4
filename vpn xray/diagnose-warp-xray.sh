#!/bin/bash
###############################################################################
# x0tta6bl4: Diagnostic & Troubleshooting Script
# Проверяет WARP + Xray интеграцию и выявляет проблемы
# Дата: 2025-01-31
###############################################################################

set -e

SSH_USER="root"
SSH_HOST="89.125.1.107"
SSH_PASS="lH7SEcWM812blV50sz"
SSH_CMD="sshpass -p '$SSH_PASS' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_ok() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_section() { echo -e "\n${CYAN}╔══════════════════════════════════════════════════╗${NC}"; echo -e "${CYAN}║  $1${NC}"; echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}\n"; }

remote_exec() {
    $SSH_CMD $SSH_USER@$SSH_HOST "$1" 2>/dev/null || echo "ERROR"
}

# ============================================================================
# DIAGNOSTICS
# ============================================================================

check_warp() {
    log_section "WARP Status"
    
    STATUS=$(remote_exec "warp-cli --accept-tos status 2>&1" | head -10)
    echo "$STATUS"
    
    if echo "$STATUS" | grep -qi "Connected"; then
        log_ok "WARP is connected"
    else
        log_warn "WARP may not be connected"
    fi
    
    # Check WARP version
    VERSION=$(remote_exec "warp-cli --version 2>&1")
    log_info "WARP version: $VERSION"
    
    # Check WARP listening on 40000
    LISTENING=$(remote_exec "ss -tulnp 2>/dev/null | grep -c ':40000' || echo 0")
    if [ "$LISTENING" -gt 0 ]; then
        log_ok "WARP proxy listening on port 40000"
    else
        log_warn "WARP proxy NOT listening on port 40000 (UDP, might be normal)"
    fi
}

check_xray() {
    log_section "Xray Status"
    
    # Container running?
    RUNNING=$(remote_exec "docker ps | grep -c x0t-node || echo 0")
    if [ "$RUNNING" -gt 0 ]; then
        log_ok "Xray container (x0t-node) is running"
    else
        log_error "Xray container NOT running!"
        return 1
    fi
    
    # Port listening?
    XRAY_PORT=$(remote_exec "docker exec x0t-node ss -tulnp 2>/dev/null | grep 10809 || echo 'NOT_LISTENING'")
    if echo "$XRAY_PORT" | grep -q "10809"; then
        log_ok "Xray listening on port 10809"
    else
        log_error "Xray NOT listening on port 10809"
    fi
    
    # Config valid?
    CONFIG_VALID=$(remote_exec "docker exec x0t-node xray test -c /etc/xray/config.json 2>&1" | grep -i "valid\|ok\|success\|error" || echo "UNKNOWN")
    log_info "Config validation: $CONFIG_VALID"
    
    # Recent logs
    log_info "Recent Xray logs (last 10 lines):"
    remote_exec "docker logs x0t-node --tail 10" | head -20
}

check_iptables() {
    log_section "iptables Rules"
    
    # Check GID
    GID=$(remote_exec "getent group xray_warp | cut -d: -f3 || echo 'NOT_FOUND'")
    log_info "xray_warp GID: $GID"
    
    # Check XRAY_WARP chain
    CHAIN=$(remote_exec "iptables -t mangle -L XRAY_WARP -v 2>/dev/null | head -5 || echo 'CHAIN_NOT_FOUND'")
    if echo "$CHAIN" | grep -q "XRAY_WARP"; then
        log_ok "iptables XRAY_WARP chain exists"
        echo "$CHAIN"
    else
        log_warn "iptables XRAY_WARP chain NOT found"
    fi
    
    # Check rules
    log_info "Checking GID bypass rule..."
    BYPASS=$(remote_exec "iptables -t mangle -L XRAY_WARP -v 2>/dev/null | grep 'gid-owner' || echo 'NOT_FOUND'")
    if [ "$BYPASS" != "NOT_FOUND" ]; then
        log_ok "GID bypass rule exists"
    else
        log_warn "GID bypass rule NOT found (needed to prevent loops)"
    fi
    
    # Check mark rules
    log_info "Checking mark rules for WARP (40000)..."
    MARK=$(remote_exec "iptables -t mangle -L XRAY_WARP -v 2>/dev/null | grep -E '40000|MARK' || echo 'NOT_FOUND'")
    if [ "$MARK" != "NOT_FOUND" ]; then
        log_ok "Port 40000 mark rule exists"
    else
        log_warn "Port 40000 mark rule NOT found"
    fi
}

check_dns() {
    log_section "DNS Configuration"
    
    # Check resolv.conf
    log_info "Current /etc/resolv.conf:"
    remote_exec "cat /etc/resolv.conf | head -6"
    
    # Test DNS resolution
    log_info "\nTesting DNS resolution:"
    
    # Cloudflare
    CF_TEST=$(remote_exec "dig @1.1.1.1 +short google.com 2>/dev/null | head -1")
    if [ -n "$CF_TEST" ] && [ "$CF_TEST" != "ERROR" ]; then
        log_ok "Cloudflare DNS (1.1.1.1) working: $CF_TEST"
    else
        log_error "Cloudflare DNS NOT working"
    fi
    
    # Google
    GOOGLE_DNS=$(remote_exec "dig @8.8.8.8 +short google.com 2>/dev/null | head -1")
    if [ -n "$GOOGLE_DNS" ] && [ "$GOOGLE_DNS" != "ERROR" ]; then
        log_ok "Google DNS (8.8.8.8) working: $GOOGLE_DNS"
    else
        log_error "Google DNS NOT working"
    fi
    
    # Test through WARP SOCKS5
    log_info "\nTesting DNS through WARP SOCKS5 proxy..."
    WARP_DNS=$(remote_exec "timeout 5 curl -s --socks5 127.0.0.1:40000 https://ifconfig.me 2>/dev/null || echo 'TIMEOUT/ERROR'")
    if [ "$WARP_DNS" != "TIMEOUT/ERROR" ] && [ -n "$WARP_DNS" ]; then
        log_ok "WARP SOCKS5 DNS working: $WARP_DNS"
    else
        log_warn "WARP SOCKS5 proxy may not be responding"
    fi
}

check_connectivity() {
    log_section "Connectivity Tests"
    
    # Test local WARP proxy
    log_info "Testing WARP SOCKS5 proxy (127.0.0.1:40000)..."
    WARP_TEST=$(remote_exec "timeout 10 curl -s --socks5 127.0.0.1:40000 https://api.ipify.org 2>/dev/null || echo 'FAILED'")
    if [ "$WARP_TEST" != "FAILED" ] && [ -n "$WARP_TEST" ]; then
        log_ok "WARP proxy accessible, IP: $WARP_TEST"
    else
        log_warn "WARP proxy test failed"
    fi
    
    # Test direct connectivity
    log_info "Testing direct connectivity to Google..."
    DIRECT_TEST=$(remote_exec "timeout 5 curl -s -I https://google.com 2>/dev/null | head -1")
    if echo "$DIRECT_TEST" | grep -q "200\|301\|302\|403"; then
        log_ok "Direct Google connectivity: $DIRECT_TEST"
    else
        log_warn "Direct Google connectivity: $DIRECT_TEST (may be expected)"
    fi
    
    # Test Xray inbound
    log_info "Checking Xray inbound connectivity..."
    XRAY_INBOUND=$(remote_exec "ss -tulnp 2>/dev/null | grep 10809")
    if [ -n "$XRAY_INBOUND" ]; then
        log_ok "Xray inbound listening"
        echo "$XRAY_INBOUND"
    else
        log_error "Xray inbound NOT listening"
    fi
}

check_routing() {
    log_section "Routing Configuration"
    
    # Check Xray config exists
    CONFIG=$(remote_exec "cat /usr/local/etc/xray/config.json 2>/dev/null | jq . 2>&1" | head -3)
    if echo "$CONFIG" | grep -q "inbounds\|outbounds"; then
        log_ok "Xray config is valid JSON"
    else
        log_error "Xray config JSON parsing failed"
        return 1
    fi
    
    # Check outbounds
    log_info "Checking outbounds in config..."
    OUTBOUNDS=$(remote_exec "docker exec x0t-node xray test -c /etc/xray/config.json 2>&1 | grep -i 'outbound' | head -5" || echo "CHECK_FAILED")
    log_info "$OUTBOUNDS"
    
    # Check for WARP outbound
    WARP_OUTBOUND=$(remote_exec "cat /usr/local/etc/xray/config.json 2>/dev/null | jq '.outbounds[] | select(.tag | contains(\"warp\")) | .tag' 2>/dev/null | head -5")
    if [ -n "$WARP_OUTBOUND" ]; then
        log_ok "WARP outbounds configured:"
        echo "$WARP_OUTBOUND"
    else
        log_warn "No WARP outbounds found in config"
    fi
    
    # Check routing rules
    log_info "Checking routing rules..."
    RULES=$(remote_exec "cat /usr/local/etc/xray/config.json 2>/dev/null | jq '.routing.rules | length' 2>/dev/null")
    log_info "Number of routing rules: $RULES"
    
    # Check for Google domains
    GOOGLE_RULES=$(remote_exec "cat /usr/local/etc/xray/config.json 2>/dev/null | jq '.routing.rules[] | select(.domain | strings | select(test(\"goog|youtube|google\"))) | .domain | .[0]' 2>/dev/null | head -3")
    if [ -n "$GOOGLE_RULES" ]; then
        log_ok "Google domain rules found:"
        echo "$GOOGLE_RULES"
    else
        log_warn "No Google domain rules found"
    fi
}

check_system() {
    log_section "System Information"
    
    # OS & Kernel
    OS_INFO=$(remote_exec "uname -a")
    log_info "OS: $OS_INFO"
    
    # Resources
    MEM=$(remote_exec "free -h | grep Mem | awk '{print \"Used: \"$3\" / \"$2}'")
    DISK=$(remote_exec "df -h / | tail -1 | awk '{print \"Used: \"$3\" / \"$2\" (\"$5\")\"}'")
    log_info "Memory: $MEM"
    log_info "Disk: $DISK"
    
    # Network interfaces
    log_info "Network interfaces:"
    remote_exec "ip -br addr | head -10"
    
    # Uptime
    UPTIME=$(remote_exec "uptime")
    log_info "Uptime: $UPTIME"
}

check_ports() {
    log_section "Open Ports"
    
    log_info "Listening ports on server:"
    remote_exec "ss -tlnp | grep LISTEN | awk '{print \$4, \$7}' | head -20"
    
    # Specific ports
    echo ""
    for port in 10809 40000 8081 3000 9091 80 443; do
        LISTENING=$(remote_exec "ss -tlnp | grep -c :$port || echo 0")
        if [ "$LISTENING" -gt 0 ]; then
            log_ok "Port $port: listening"
        else
            log_warn "Port $port: not listening"
        fi
    done
}

# ============================================================================
# PROBLEMS & SOLUTIONS
# ============================================================================

diagnose_problems() {
    log_section "Problem Diagnosis"
    
    # Problem 1: Google still blocks
    log_info "Checking for Google blocking..."
    GOOGLE_TEST=$(remote_exec "timeout 5 curl -s -I https://google.com 2>/dev/null | head -1")
    if echo "$GOOGLE_TEST" | grep -q "403\|400"; then
        log_error "Google appears to be blocking (HTTP 403/400)"
        log_info "Solution: Ensure WARP outbound is correctly configured in routing rules"
        log_info "         Check that google.com domain routes to warp-google outbound"
    fi
    
    # Problem 2: DNS leaks
    log_info "Checking for DNS configuration..."
    DNS_CONFIG=$(remote_exec "cat /etc/resolv.conf | grep -v '^#' | grep nameserver | wc -l")
    if [ "$DNS_CONFIG" -lt 2 ]; then
        log_error "DNS servers not properly configured"
        log_info "Solution: Run 'cat > /etc/resolv.conf' and add Cloudflare DNS (1.1.1.1)"
    else
        log_ok "DNS servers configured ($DNS_CONFIG nameservers)"
    fi
    
    # Problem 3: WARP not connected
    WARP_STATUS=$(remote_exec "warp-cli --accept-tos status 2>&1 | grep -i connected | wc -l")
    if [ "$WARP_STATUS" -eq 0 ]; then
        log_error "WARP not connected"
        log_info "Solution: Run 'warp-cli --accept-tos connect'"
    else
        log_ok "WARP appears connected"
    fi
    
    # Problem 4: Xray config invalid
    XRAY_CONFIG_TEST=$(remote_exec "docker exec x0t-node xray test -c /etc/xray/config.json 2>&1" | grep -i "error\|invalid" | wc -l)
    if [ "$XRAY_CONFIG_TEST" -gt 0 ]; then
        log_error "Xray config validation failed"
        log_info "Solution: Check /usr/local/etc/xray/config.json JSON syntax"
    else
        log_ok "Xray config appears valid"
    fi
    
    # Problem 5: iptables rules missing
    IPTABLES_TEST=$(remote_exec "iptables -t mangle -L XRAY_WARP 2>/dev/null | wc -l")
    if [ "$IPTABLES_TEST" -lt 3 ]; then
        log_error "iptables rules not properly configured"
        log_info "Solution: Run iptables setup script to configure GID bypass"
    else
        log_ok "iptables rules appear configured"
    fi
}

# ============================================================================
# RECOMMENDATIONS
# ============================================================================

show_recommendations() {
    log_section "Recommendations"
    
    cat << 'EOF'
Based on the diagnostic results:

1. WARP Configuration:
   - Ensure WARP is in "proxy" mode (not full tunnel)
   - Port 40000 should be listening for SOCKS5 traffic
   - Run: warp-cli --accept-tos mode proxy
   - Run: warp-cli --accept-tos connect

2. Xray Configuration:
   - Check that routing rules include Google domains
   - Verify WARP outbounds are configured with SOCKS5 (port 40000)
   - Test with: docker exec x0t-node xray test -c /etc/xray/config.json

3. iptables Rules:
   - GID bypass must be configured to prevent routing loops
   - Run: groupadd -f xray_warp
   - Run: iptables -t mangle -A XRAY_WARP -m owner --gid-owner GID -j RETURN

4. DNS Configuration:
   - Ensure /etc/resolv.conf points to Cloudflare (1.1.1.1)
   - Run: echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
   - Make immutable: sudo chattr +i /etc/resolv.conf

5. Testing:
   - From your client: curl -v -x socks5://user@host:10809 https://google.com
   - Should return 200 OK (not 403)
   - Check IP: curl --socks5 socks5://user@host:10809 https://ifconfig.me
   - Should NOT show 89.125.1.107

6. Monitoring:
   - Watch logs: docker logs x0t-node -f
   - Check traffic: ss -tnp | grep 40000
   - Monitor connections: netstat -an | grep ESTABLISHED
EOF
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  x0tta6bl4: WARP + Xray Diagnostic Report          ║${NC}"
    echo -e "${CYAN}║  Server: $SSH_HOST                           ║${NC}"
    echo -e "${CYAN}║  Date: $(date +'%Y-%m-%d %H:%M:%S')                           ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════╝${NC}"
    
    # Run all checks
    check_system
    check_warp
    check_xray
    check_iptables
    check_dns
    check_ports
    check_routing
    check_connectivity
    diagnose_problems
    show_recommendations
    
    log_section "Diagnostic Report Complete"
    echo "Report saved to: $0"
}

trap 'log_error "Diagnostic failed at line $LINENO"' ERR
main "$@"
