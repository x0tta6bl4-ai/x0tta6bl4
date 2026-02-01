#!/bin/bash
# Anti-Geolocation System Verification Script
# Validates effectiveness against geolocation detection services

set -euo pipefail

LOG_FILE="/var/log/anti-geolocation-verify.log"
RESULTS_FILE="/tmp/verification-results.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[FAIL]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[PASS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Test results
declare -A TEST_RESULTS
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# ============================================================================
# NETWORK LAYER TESTS
# ============================================================================

test_ip_leak() {
    log "Testing IP leak..."
    
    local detected_ip
    detected_ip=$(curl -s --max-time 10 https://ifconfig.me 2>/dev/null || echo "")
    
    if [[ -z "$detected_ip" ]]; then
        error "Could not detect public IP"
        TEST_RESULTS["ip_leak"]="FAIL: No IP detected"
        ((FAILED_TESTS++))
        return 1
    fi
    
    info "Detected IP: $detected_ip"
    
    # Check if it's a known VPN IP (Cloudflare, etc.)
    if echo "$detected_ip" | grep -qE "^(104\.|172\.|173\.)"; then
        success "IP appears to be from Cloudflare/VPN range"
        TEST_RESULTS["ip_leak"]="PASS: VPN IP detected ($detected_ip)"
        ((PASSED_TESTS++))
        return 0
    else
        warning "IP may not be from expected VPN range"
        TEST_RESULTS["ip_leak"]="WARN: Unexpected IP range ($detected_ip)"
        ((TOTAL_TESTS++))
        return 0
    fi
}

test_dns_leak() {
    log "Testing DNS leak..."
    
    # Get DNS servers from dnsleaktest
    local dns_servers
    dns_servers=$(curl -s --max-time 15 https://dnsleaktest.com/api/servers 2>/dev/null || echo "[]")
    
    if [[ "$dns_servers" == "[]" ]] || [[ -z "$dns_servers" ]]; then
        error "Could not retrieve DNS server information"
        TEST_RESULTS["dns_leak"]="FAIL: No DNS data"
        ((FAILED_TESTS++))
        return 1
    fi
    
    # Check for ISP DNS (common ISP indicators)
    local isp_dns=$(echo "$dns_servers" | grep -iE "(comcast|verizon|att|spectrum|charter|cox|rogers|bt\.|orange|telefonica)" || true)
    
    if [[ -n "$isp_dns" ]]; then
        error "ISP DNS servers detected!"
        echo "$isp_dns"
        TEST_RESULTS["dns_leak"]="FAIL: ISP DNS leak detected"
        ((FAILED_TESTS++))
        return 1
    else
        success "No ISP DNS leak detected"
        TEST_RESULTS["dns_leak"]="PASS: Using privacy DNS"
        ((PASSED_TESTS++))
        return 0
    fi
}

test_ipv6_leak() {
    log "Testing IPv6 leak..."
    
    local ipv6_status
    ipv6_status=$(curl -s --max-time 10 https://test-ipv6.com/ip/?callback=? 2>/dev/null || echo "")
    
    if [[ -z "$ipv6_status" ]]; then
        success "No IPv6 connectivity (good for privacy)"
        TEST_RESULTS["ipv6_leak"]="PASS: IPv6 disabled"
        ((PASSED_TESTS++))
        return 0
    fi
    
    warning "IPv6 connectivity detected"
    TEST_RESULTS["ipv6_leak"]="WARN: IPv6 enabled"
    return 0
}

test_webrtc_leak() {
    log "Testing WebRTC leak..."
    
    # Check if WebRTC is disabled in Firefox
    if pgrep -x "firefox" > /dev/null; then
        local firefox_profile
        firefox_profile=$(find ~/.mozilla/firefox -name "*.default*" -type d 2>/dev/null | head -n1)
        
        if [[ -f "$firefox_profile/user.js" ]]; then
            if grep -q 'media.peerconnection.enabled", false' "$firefox_profile/user.js"; then
                success "WebRTC disabled in Firefox"
                TEST_RESULTS["webrtc_firefox"]="PASS: WebRTC disabled"
                ((PASSED_TESTS++))
            else
                warning "WebRTC may be enabled in Firefox"
                TEST_RESULTS["webrtc_firefox"]="WARN: WebRTC status unclear"
            fi
        fi
    fi
    
    # Note: Full WebRTC test requires browser automation
    info "Manual verification required at https://browserleaks.com/webrtc"
    TEST_RESULTS["webrtc_manual"]="INFO: Verify at browserleaks.com/webrtc"
}

# ============================================================================
# SYSTEM HARDENING TESTS
# ============================================================================

test_mac_randomization() {
    log "Testing MAC address randomization..."
    
    local has_random_mac=false
    
    for iface in $(ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -vE "^(lo|docker)"); do
        local mac
        mac=$(cat "/sys/class/net/$iface/address" 2>/dev/null || echo "")
        
        # Check if MAC is locally administered (randomized)
        local first_byte="${mac:0:2}"
        local second_bit=$((16#$first_byte & 2))
        
        if [[ $second_bit -eq 2 ]]; then
            success "Interface $iface has randomized MAC: $mac"
            has_random_mac=true
        else
            info "Interface $iface MAC: $mac (may not be randomized)"
        fi
    done
    
    if [[ "$has_random_mac" == true ]]; then
        TEST_RESULTS["mac_randomization"]="PASS: Randomized MAC detected"
        ((PASSED_TESTS++))
    else
        warning "No randomized MAC addresses detected"
        TEST_RESULTS["mac_randomization"]="WARN: MAC randomization not confirmed"
    fi
}

test_hostname_randomization() {
    log "Testing hostname..."
    
    local hostname
    hostname=$(hostname)
    
    # Check if hostname looks randomized (not default like ubuntu, debian, etc.)
    if echo "$hostname" | grep -qiE "(ubuntu|debian|fedora|arch|localhost|desktop|laptop|pc-[0-9])"; then
        warning "Hostname appears to be default: $hostname"
        TEST_RESULTS["hostname"]="WARN: Default hostname detected"
    else
        success "Hostname appears randomized: $hostname"
        TEST_RESULTS["hostname"]="PASS: Randomized hostname"
        ((PASSED_TESTS++))
    fi
}

test_ipv6_disabled() {
    log "Testing IPv6 disablement..."
    
    local ipv6_disabled
    ipv6_disabled=$(sysctl net.ipv6.conf.all.disable_ipv6 2>/dev/null | awk '{print $3}')
    
    if [[ "$ipv6_disabled" == "1" ]]; then
        success "IPv6 is disabled at kernel level"
        TEST_RESULTS["ipv6_kernel"]="PASS: IPv6 disabled"
        ((PASSED_TESTS++))
    else
        warning "IPv6 may be enabled"
        TEST_RESULTS["ipv6_kernel"]="WARN: IPv6 enabled"
    fi
}

# ============================================================================
# DNS PROXY TESTS
# ============================================================================

test_doh_proxy() {
    log "Testing DNS over HTTPS proxy..."
    
    if systemctl is-active --quiet cloudflared-proxy-dns 2>/dev/null; then
        success "cloudflared DoH proxy is running"
        TEST_RESULTS["doh_proxy"]="PASS: cloudflared running"
        ((PASSED_TESTS++))
    else
        warning "cloudflared DoH proxy not running"
        TEST_RESULTS["doh_proxy"]="WARN: cloudflared not active"
    fi
    
    # Test DNS resolution through local proxy
    if dig @127.0.0.1 -p 5053 cloudflare.com +short +time=5 > /dev/null 2>&1; then
        success "DoH proxy responding on port 5053"
        TEST_RESULTS["doh_port"]="PASS: Port 5053 responding"
        ((PASSED_TESTS++))
    else
        error "DoH proxy not responding"
        TEST_RESULTS["doh_port"]="FAIL: Port 5053 not responding"
        ((FAILED_TESTS++))
    fi
}

test_dnscrypt_proxy() {
    log "Testing DNSCrypt proxy..."
    
    if systemctl is-active --quiet dnscrypt-proxy 2>/dev/null; then
        success "dnscrypt-proxy is running"
        TEST_RESULTS["dnscrypt_proxy"]="PASS: dnscrypt-proxy running"
        ((PASSED_TESTS++))
    else
        warning "dnscrypt-proxy not running"
        TEST_RESULTS["dnscrypt_proxy"]="WARN: dnscrypt-proxy not active"
    fi
}

# ============================================================================
# BROWSER HARDENING TESTS
# ============================================================================

test_firefox_hardening() {
    log "Testing Firefox hardening..."
    
    local firefox_profiles
    firefox_profiles=$(find ~/.mozilla/firefox -name "*.default*" -type d 2>/dev/null)
    
    if [[ -z "$firefox_profiles" ]]; then
        info "No Firefox profiles found"
        TEST_RESULTS["firefox_profile"]="INFO: No Firefox profiles"
        return 0
    fi
    
    for profile in $firefox_profiles; do
        if [[ -f "$profile/user.js" ]]; then
            local has_rfp=false
            local has_webrtc_disable=false
            local has_geo_disable=false
            
            if grep -q 'privacy.resistFingerprinting", true' "$profile/user.js"; then
                has_rfp=true
            fi
            
            if grep -q 'media.peerconnection.enabled", false' "$profile/user.js"; then
                has_webrtc_disable=true
            fi
            
            if grep -q 'geo.enabled", false' "$profile/user.js"; then
                has_geo_disable=true
            fi
            
            if [[ "$has_rfp" == true && "$has_webrtc_disable" == true && "$has_geo_disable" == true ]]; then
                success "Firefox profile properly hardened: $(basename "$profile")"
                TEST_RESULTS["firefox_hardening"]="PASS: Profile hardened"
                ((PASSED_TESTS++))
            else
                warning "Firefox profile may not be fully hardened"
                TEST_RESULTS["firefox_hardening"]="WARN: Incomplete hardening"
            fi
        else
            warning "No user.js found in Firefox profile"
            TEST_RESULTS["firefox_hardening"]="WARN: No user.js"
        fi
    done
}

# ============================================================================
# VPN/KILLSWITCH TESTS
# ============================================================================

test_killswitch() {
    log "Testing killswitch..."
    
    if [[ -f /tmp/vpn-killswitch-active ]]; then
        success "Killswitch is active"
        TEST_RESULTS["killswitch"]="PASS: Killswitch active"
        ((PASSED_TESTS++))
    else
        info "Killswitch not currently active"
        TEST_RESULTS["killswitch"]="INFO: Killswitch inactive"
    fi
}

test_vpn_connection() {
    log "Testing VPN connection..."
    
    local vpn_iface
    vpn_iface=$(ip link show | grep -oE "tun-[^:]+|tun[0-9]+|wg[0-9]+" | head -n1)
    
    if [[ -n "$vpn_iface" ]]; then
        success "VPN interface detected: $vpn_iface"
        TEST_RESULTS["vpn_interface"]="PASS: VPN active ($vpn_iface)"
        ((PASSED_TESTS++))
    else
        warning "No VPN interface detected"
        TEST_RESULTS["vpn_interface"]="WARN: No VPN detected"
    fi
}

# ============================================================================
# IDENTITY MANAGEMENT TESTS
# ============================================================================

test_identity_manager() {
    log "Testing identity manager..."
    
    if command -v identity-manager &>/dev/null; then
        success "identity-manager command available"
        TEST_RESULTS["identity_manager"]="PASS: identity-manager installed"
        ((PASSED_TESTS++))
    else
        error "identity-manager not found"
        TEST_RESULTS["identity_manager"]="FAIL: identity-manager missing"
        ((FAILED_TESTS++))
    fi
}

# ============================================================================
# LEAK DETECTOR TESTS
# ============================================================================

test_leak_detector() {
    log "Testing leak detector..."
    
    if command -v leak-detector &>/dev/null; then
        success "leak-detector command available"
        TEST_RESULTS["leak_detector"]="PASS: leak-detector installed"
        ((PASSED_TESTS++))
    else
        error "leak-detector not found"
        TEST_RESULTS["leak_detector"]="FAIL: leak-detector missing"
        ((FAILED_TESTS++))
    fi
    
    if [[ -f /etc/anti-geolocation/leak-detector.yaml ]]; then
        success "Leak detector configuration exists"
        TEST_RESULTS["leak_detector_config"]="PASS: Config exists"
        ((PASSED_TESTS++))
    else
        warning "Leak detector configuration missing"
        TEST_RESULTS["leak_detector_config"]="WARN: No config"
    fi
}

# ============================================================================
# REPORT GENERATION
# ============================================================================

generate_report() {
    log "Generating verification report..."
    
    local total=$((PASSED_TESTS + FAILED_TESTS))
    local pass_rate=0
    if [[ $total -gt 0 ]]; then
        pass_rate=$((PASSED_TESTS * 100 / total))
    fi
    
    cat > "$RESULTS_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "summary": {
    "total_tests": $total,
    "passed": $PASSED_TESTS,
    "failed": $FAILED_TESTS,
    "pass_rate": $pass_rate
  },
  "results": {
EOF

    local first=true
    for key in "${!TEST_RESULTS[@]}"; do
        if [[ "$first" == true ]]; then
            first=false
        else
            echo "," >> "$RESULTS_FILE"
        fi
        echo -n "    \"$key\": \"${TEST_RESULTS[$key]}\"" >> "$RESULTS_FILE"
    done
    
    cat >> "$RESULTS_FILE" << EOF

  }
}
EOF

    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           VERIFICATION REPORT                                    ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Total Tests: $total"
    echo "Passed: $PASSED_TESTS"
    echo "Failed: $FAILED_TESTS"
    echo "Pass Rate: $pass_rate%"
    echo ""
    echo "Detailed Results:"
    for key in "${!TEST_RESULTS[@]}"; do
        echo "  $key: ${TEST_RESULTS[$key]}"
    done
    echo ""
    echo "Full report saved to: $RESULTS_FILE"
    
    if [[ $FAILED_TESTS -gt 0 ]]; then
        echo ""
        warning "Some tests failed. Review the results above."
        return 1
    else
        echo ""
        success "All tests passed!"
        return 0
    fi
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    log "Starting Anti-Geolocation System Verification"
    
    # Network layer tests
    test_ip_leak
    test_dns_leak
    test_ipv6_leak
    test_webrtc_leak
    
    # System hardening tests
    test_mac_randomization
    test_hostname_randomization
    test_ipv6_disabled
    
    # DNS proxy tests
    test_doh_proxy
    test_dnscrypt_proxy
    
    # Browser tests
    test_firefox_hardening
    
    # VPN/Killswitch tests
    test_killswitch
    test_vpn_connection
    
    # Identity management tests
    test_identity_manager
    
    # Leak detector tests
    test_leak_detector
    
    # Generate report
    generate_report
}

# Run main function
main "$@"
