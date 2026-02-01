#!/bin/bash
# Xray Health Check Script
# Performs comprehensive health checks on Xray service
# Date: 2026-01-31
# Version: 1.0.0

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Status
HEALTH_STATUS="HEALTHY"
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNINGS=0

# Configuration
CONFIG_DIR="/usr/local/etc/xray"
LOG_DIR="/var/log/xray"
ALERT_THRESHOLD_ERRORS=50
ALERT_THRESHOLD_LOAD=80

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((CHECKS_PASSED++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((CHECKS_FAILED++)); HEALTH_STATUS="UNHEALTHY"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((CHECKS_WARNINGS++)); }
log_section() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "This script must be run as root"
        exit 1
    fi
}

# Check 1: Service Status
check_service() {
    log_section "SERVICE STATUS"
    
    if systemctl is-active --quiet xray; then
        local uptime=$(systemctl show xray --property=ActiveEnterTimestamp --value 2>/dev/null | cut -d' ' -f2-)
        log_pass "Xray service is running (since: $uptime)"
        
        # Check for restarts
        local restarts=$(systemctl show xray --property=NRestarts --value 2>/dev/null || echo "0")
        if [[ "$restarts" -gt 0 ]]; then
            log_warn "Service has been restarted $restarts times"
        fi
    else
        log_fail "Xray service is not running"
        return 1
    fi
    
    if systemctl is-enabled --quiet xray 2>/dev/null; then
        log_pass "Service is enabled on boot"
    else
        log_warn "Service is not enabled on boot"
    fi
}

# Check 2: Configuration Validity
check_config() {
    log_section "CONFIGURATION"
    
    if [[ ! -f "${CONFIG_DIR}/config.json" ]]; then
        log_fail "Configuration file not found"
        return 1
    fi
    
    log_pass "Configuration file exists"
    
    # Check JSON validity
    if jq empty "${CONFIG_DIR}/config.json" 2>/dev/null; then
        log_pass "Configuration is valid JSON"
    else
        log_fail "Configuration is invalid JSON"
        return 1
    fi
    
    # Test with Xray
    if xray -test -config "${CONFIG_DIR}/config.json" &>/dev/null; then
        log_pass "Xray configuration test passed"
    else
        log_fail "Xray configuration test failed"
        return 1
    fi
    
    # Count inbounds
    local inbounds=$(jq '.inbounds | length' "${CONFIG_DIR}/config.json" 2>/dev/null || echo "0")
    log_info "Number of inbounds: $inbounds"
}

# Check 3: Port Listening
check_ports() {
    log_section "PORT STATUS"
    
    declare -A PORTS
    PORTS[443]="VLESS-Reality"
    PORTS[8443]="VLESS-xHTTP"
    PORTS[8388]="Shadowsocks"
    PORTS[9443]="Trojan"
    PORTS[8080]="ShadowTLS"
    
    local any_listening=false
    
    for port in "${!PORTS[@]}"; do
        local service="${PORTS[$port]}"
        if ss -tlnp 2>/dev/null | grep -q ":$port " || \
           netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            log_pass "Port $port ($service) is listening"
            any_listening=true
        else
            log_warn "Port $port ($service) is not listening"
        fi
    done
    
    if [[ "$any_listening" == "false" ]]; then
        log_fail "No Xray ports are listening"
        return 1
    fi
}

# Check 4: Resource Usage
check_resources() {
    log_section "RESOURCE USAGE"
    
    # Memory usage
    local mem_usage=$(free | awk '/^Mem:/{printf "%.0f", $3/$2 * 100}')
    if [[ $mem_usage -gt 90 ]]; then
        log_fail "Critical memory usage: ${mem_usage}%"
    elif [[ $mem_usage -gt 75 ]]; then
        log_warn "High memory usage: ${mem_usage}%"
    else
        log_pass "Memory usage: ${mem_usage}%"
    fi
    
    # Disk usage
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 90 ]]; then
        log_fail "Critical disk usage: ${disk_usage}%"
    elif [[ $disk_usage -gt 80 ]]; then
        log_warn "High disk usage: ${disk_usage}%"
    else
        log_pass "Disk usage: ${disk_usage}%"
    fi
    
    # Load average
    local load=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cores=$(nproc)
    local load_pct=$(awk "BEGIN {printf \"%.0f\", ($load / $cores) * 100}")
    
    if [[ $load_pct -gt $ALERT_THRESHOLD_LOAD ]]; then
        log_warn "High load average: $load ($load_pct% of $cores cores)"
    else
        log_pass "Load average: $load ($load_pct% of $cores cores)"
    fi
}

# Check 5: Error Logs
check_logs() {
    log_section "ERROR LOGS"
    
    if [[ ! -f "${LOG_DIR}/error.log" ]]; then
        log_warn "Error log file not found"
        return
    fi
    
    # Check recent errors (last 100 lines)
    local recent_errors=$(tail -100 "${LOG_DIR}/error.log" 2>/dev/null | grep -ci "error\|failed\|fatal" || echo "0")
    
    if [[ $recent_errors -eq 0 ]]; then
        log_pass "No errors in recent logs"
    elif [[ $recent_errors -lt 10 ]]; then
        log_warn "$recent_errors errors in recent logs"
    else
        log_fail "$recent_errors errors in recent logs"
    fi
    
    # Check total error count
    local total_errors=$(wc -l < "${LOG_DIR}/error.log" 2>/dev/null || echo "0")
    log_info "Total error log entries: $total_errors"
}

# Check 6: Certificate Validity
check_certificates() {
    log_section "CERTIFICATES"
    
    if [[ ! -f /etc/ssl/xray/xray.crt ]]; then
        log_warn "TLS certificate not found"
        return
    fi
    
    # Check certificate expiry
    if openssl x509 -in /etc/ssl/xray/xray.crt -noout -checkend 86400 &>/dev/null; then
        log_pass "Certificate valid for at least 24 hours"
    else
        log_fail "Certificate expires within 24 hours or is invalid"
    fi
    
    # Get expiry date
    local expiry=$(openssl x509 -in /etc/ssl/xray/xray.crt -noout -enddate 2>/dev/null | cut -d'=' -f2)
    log_info "Certificate expires: $expiry"
    
    # Check key permissions
    local key_perms=$(stat -c %a /etc/ssl/xray/xray.key 2>/dev/null || stat -f %Lp /etc/ssl/xray/xray.key 2>/dev/null)
    if [[ "$key_perms" == "600" ]]; then
        log_pass "Key file has correct permissions (600)"
    else
        log_warn "Key file permissions: $key_perms (should be 600)"
    fi
}

# Check 7: Network Connectivity
check_network() {
    log_section "NETWORK"
    
    # Check internet connectivity
    if ping -c 1 -W 3 1.1.1.1 &>/dev/null; then
        log_pass "Internet connectivity available"
    else
        log_warn "No internet connectivity"
    fi
    
    # Get public IP
    local public_ip=$(curl -s -4 --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    log_info "Public IP: $public_ip"
    
    # Check DNS resolution
    if nslookup google.com &>/dev/null; then
        log_pass "DNS resolution working"
    else
        log_warn "DNS resolution may have issues"
    fi
}

# Check 8: Process Health
check_process() {
    log_section "PROCESS HEALTH"
    
    local xray_pid=$(pgrep -x xray || echo "")
    if [[ -z "$xray_pid" ]]; then
        log_fail "Xray process not found"
        return 1
    fi
    
    log_pass "Xray process running (PID: $xray_pid)"
    
    # Check file descriptors
    local fd_count=$(ls /proc/$xray_pid/fd 2>/dev/null | wc -l || echo "0")
    log_info "Open file descriptors: $fd_count"
    
    # Check memory usage of process
    local proc_mem=$(ps -p $xray_pid -o %mem --no-headers 2>/dev/null | tr -d ' ' || echo "0")
    log_info "Process memory usage: ${proc_mem}%"
}

# Check 9: Connection Stats
check_connections() {
    log_section "CONNECTION STATS"
    
    # Count established connections
    local established=$(ss -tunap 2>/dev/null | grep xray | grep ESTAB | wc -l || echo "0")
    log_info "Established connections: $established"
    
    # Count connections by port
    for port in 443 8443 8388 9443 8080; do
        local count=$(ss -tunap 2>/dev/null | grep ":$port " | wc -l || echo "0")
        if [[ $count -gt 0 ]]; then
            log_info "Port $port connections: $count"
        fi
    done
}

# Generate health report
generate_report() {
    log_section "HEALTH REPORT"
    
    echo ""
    echo -e "${CYAN}Overall Status: ${HEALTH_STATUS}${NC}"
    echo ""
    echo -e "Checks Passed:   ${GREEN}$CHECKS_PASSED${NC}"
    echo -e "Checks Failed:   ${RED}$CHECKS_FAILED${NC}"
    echo -e "Warnings:        ${YELLOW}$CHECKS_WARNINGS${NC}"
    echo ""
    
    # Timestamp
    echo "Report generated: $(date -Iseconds)"
    echo "Hostname: $(hostname)"
    echo "Xray version: $(xray -version 2>/dev/null | head -1 || echo 'unknown')"
}

# Save report to file
save_report() {
    local report_file="${LOG_DIR}/health-report-$(date +%Y%m%d-%H%M%S).log"
    
    cat > "$report_file" << EOF
Xray Health Report
==================
Date: $(date -Iseconds)
Hostname: $(hostname)
Status: $HEALTH_STATUS

Checks:
  Passed: $CHECKS_PASSED
  Failed: $CHECKS_FAILED
  Warnings: $CHECKS_WARNINGS

Service Status: $(systemctl is-active xray 2>/dev/null || echo 'unknown')
Xray Version: $(xray -version 2>/dev/null | head -1 || echo 'unknown')

System Resources:
  Memory Usage: $(free | awk '/^Mem:/{printf "%.1f%%", $3/$2 * 100}')
  Disk Usage: $(df / | awk 'NR==2 {print $5}')
  Load Average: $(uptime | awk -F'load average:' '{print $2}')
EOF

    log_info "Report saved to: $report_file"
}

# Main function
main() {
    echo -e "${CYAN}"
    echo "  __  __          __        __   _           __  ____  ____"
    echo "  \\ \\/ /__  _____/ /_____ _/ /  (_)__  ___  /  |/  / |/ / /"
    echo "   \\  / _ \\/ ___/ __/ __ \\ / /  / / _ \\/ _ \\/ /|_/ /    /_/"
    echo "   / /  __/ /__/ /_/ /_/ // /__/ / __/  __/ /  / / /| / /"
    echo "  /_/\\___/\\___/\\__/\\____/____/_/_/  \\___/_/  /_/_/ |_/_/"
    echo ""
    echo -e "${NC}"
    echo -e "  ${BLUE}Xray Health Check${NC}"
    echo ""
    
    check_root
    check_service
    check_config
    check_ports
    check_resources
    check_logs
    check_certificates
    check_network
    check_process
    check_connections
    generate_report
    save_report
    
    # Exit with appropriate code
    if [[ "$HEALTH_STATUS" == "HEALTHY" ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main
main "$@"
