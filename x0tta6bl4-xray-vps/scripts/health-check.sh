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
CONFIG_DIR="${CONFIG_DIR:-/usr/local/etc/xray}"
LOG_DIR="${LOG_DIR:-/var/log/xray}"
CLIENT_DIR="${CLIENT_DIR:-/root/xray-clients}"
ALERT_THRESHOLD_ERRORS=50
ALERT_THRESHOLD_LOAD=80
XRAY_SERVICE="${XRAY_SERVICE:-}"
XRAY_CONFIG="${XRAY_CONFIG:-}"
XRAY_BIN="${XRAY_BIN:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISTRIBUTION_GATE_SCRIPT="${DISTRIBUTION_GATE_SCRIPT:-${SCRIPT_DIR}/check-client-distribution-gate.sh}"

if [[ -z "$XRAY_SERVICE" ]]; then
    if systemctl list-unit-files x-ui.service &>/dev/null; then
        XRAY_SERVICE="x-ui"
    else
        XRAY_SERVICE="xray"
    fi
fi

if [[ -z "$XRAY_CONFIG" ]]; then
    if [[ -f /usr/local/x-ui/bin/config.json ]]; then
        XRAY_CONFIG="/usr/local/x-ui/bin/config.json"
    else
        XRAY_CONFIG="${CONFIG_DIR}/config.json"
    fi
fi

if [[ -z "$XRAY_BIN" ]]; then
    if [[ -x /usr/local/x-ui/bin/xray-linux-amd64.real ]]; then
        XRAY_BIN="/usr/local/x-ui/bin/xray-linux-amd64.real"
    else
        XRAY_BIN="$(command -v xray || true)"
    fi
fi

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((++CHECKS_PASSED)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((++CHECKS_FAILED)); HEALTH_STATUS="UNHEALTHY"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((++CHECKS_WARNINGS)); }
log_section() { echo -e "\n${CYAN}=== $1 ===${NC}"; }
xray_version() {
    if [[ -n "$XRAY_BIN" && -x "$XRAY_BIN" ]]; then
        local output
        output="$("$XRAY_BIN" version 2>/dev/null || true)"
        output="${output%%$'\n'*}"
        echo "${output:-unknown}"
    else
        echo "unknown"
    fi
}

xray_config_test() {
    [[ -n "$XRAY_BIN" && -x "$XRAY_BIN" ]] && "$XRAY_BIN" run -test -config "$XRAY_CONFIG" &>/dev/null
}

is_ipv4() {
    local value="${1:-}"
    [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    local IFS=.
    read -r o1 o2 o3 o4 <<< "$value"
    for octet in "$o1" "$o2" "$o3" "$o4"; do
        [[ "$octet" =~ ^[0-9]+$ ]] || return 1
        ((octet >= 0 && octet <= 255)) || return 1
    done
}

detect_public_ipv4() {
    local endpoint value
    for endpoint in \
        "https://api.ipify.org" \
        "https://ifconfig.co/ip" \
        "https://ifconfig.me/ip"; do
        value="$(curl -fsS -4 --max-time 8 "$endpoint" 2>/dev/null | tr -d '[:space:]' || true)"
        if is_ipv4 "$value"; then
            printf '%s\n' "$value"
            return 0
        fi
    done
    return 1
}

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
    
    if systemctl is-active --quiet "$XRAY_SERVICE"; then
        local uptime=$(systemctl show "$XRAY_SERVICE" --property=ActiveEnterTimestamp --value 2>/dev/null | cut -d' ' -f2-)
        log_pass "$XRAY_SERVICE service is running (since: $uptime)"
        
        # Check for restarts
        local restarts=$(systemctl show "$XRAY_SERVICE" --property=NRestarts --value 2>/dev/null || echo "0")
        if [[ "$restarts" -gt 0 ]]; then
            log_warn "Service has been restarted $restarts times"
        fi
    else
        log_fail "$XRAY_SERVICE service is not running"
        return 1
    fi
    
    if systemctl is-enabled --quiet "$XRAY_SERVICE" 2>/dev/null; then
        log_pass "Service is enabled on boot"
    else
        log_warn "Service is not enabled on boot"
    fi
}

# Check 2: Configuration Validity
check_config() {
    log_section "CONFIGURATION"
    
    if [[ ! -f "$XRAY_CONFIG" ]]; then
        log_fail "Configuration file not found: $XRAY_CONFIG"
        return 1
    fi
    
    log_pass "Configuration file exists: $XRAY_CONFIG"
    
    # Check JSON validity
    if jq empty "$XRAY_CONFIG" 2>/dev/null; then
        log_pass "Configuration is valid JSON"
    else
        log_fail "Configuration is invalid JSON"
        return 1
    fi
    
    # Test with Xray
    if xray_config_test; then
        log_pass "Xray configuration test passed"
    else
        log_fail "Xray configuration test failed"
        return 1
    fi
    
    # Count inbounds
    local inbounds=$(jq '.inbounds | length' "$XRAY_CONFIG" 2>/dev/null || echo "0")
    log_info "Number of inbounds: $inbounds"
}

# Check 3: Port Listening
check_ports() {
    log_section "PORT STATUS"
    
    local any_listening=false
    local rows=""
    rows=$(jq -r '.inbounds[]? | select(.port != null) | [.port, (.protocol // "unknown"), (.tag // "")] | @tsv' "$XRAY_CONFIG" 2>/dev/null || true)
    
    if [[ -z "$rows" ]]; then
        rows=$'443\tVLESS-Reality\tdefault\n8443\tVLESS-xHTTP\tdefault\n8388\tShadowsocks\tdefault\n9443\tTrojan\tdefault\n8080\tShadowTLS\tdefault'
    fi

    while IFS=$'\t' read -r port protocol tag; do
        [[ -z "$port" ]] && continue
        if ss -tlnp 2>/dev/null | grep -q ":$port " || \
           netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            log_pass "Port $port ($protocol ${tag:-untagged}) is listening"
            any_listening=true
        else
            log_warn "Port $port ($protocol ${tag:-untagged}) is not listening"
        fi
    done <<< "$rows"
    
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
    local recent_errors
    recent_errors=$(tail -100 "${LOG_DIR}/error.log" 2>/dev/null | awk 'BEGIN{IGNORECASE=1; count=0} /error|failed|fatal/{count++} END{print count}')
    recent_errors=${recent_errors//[[:space:]]/}
    
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
    local public_ip
    public_ip=$(detect_public_ipv4 || echo "unknown")
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
    
    local xray_pid=""
    if [[ "$XRAY_SERVICE" == "x-ui" ]]; then
        xray_pid=$(pgrep -f "xray-linux-amd64.*bin/config.json" | head -1 || echo "")
    fi
    if [[ -z "$xray_pid" ]]; then
        xray_pid=$(pgrep -f "xray-linux-amd64.*$XRAY_CONFIG|/usr/local/bin/xray.*$XRAY_CONFIG|xray run" | head -1 || echo "")
    fi
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
    local established=$(ss -tunap 2>/dev/null | grep -E "xray|x-ui" | grep ESTAB | wc -l || echo "0")
    log_info "Established connections: $established"
    
    # Count connections by port
    local ports
    ports=$(jq -r '.inbounds[]? | select(.port != null) | .port' "$XRAY_CONFIG" 2>/dev/null | sort -n | uniq)
    for port in ${ports:-443 8443 8388 9443 8080}; do
        local count=$(ss -tunap 2>/dev/null | grep ":$port " | wc -l || echo "0")
        if [[ $count -gt 0 ]]; then
            log_info "Port $port connections: $count"
        fi
    done
}

# Check 10: Client distribution safety
check_client_distribution() {
    log_section "CLIENT DISTRIBUTION"

    if [[ ! -d "$CLIENT_DIR" ]]; then
        log_fail "Client directory missing: $CLIENT_DIR"
        return 1
    fi

    if [[ ! -x "$DISTRIBUTION_GATE_SCRIPT" ]]; then
        log_fail "Distribution gate script missing or not executable: $DISTRIBUTION_GATE_SCRIPT"
        return 1
    fi

    local gate_output
    if gate_output="$(CONFIG_FILE="$XRAY_CONFIG" CLIENT_DIR="$CLIENT_DIR" bash "$DISTRIBUTION_GATE_SCRIPT" 2>&1)"; then
        log_pass "Client distribution gate passed"
        echo "$gate_output" | grep -E "Distribution gate summary:|Passed:|Failed:|Warnings:|Client profiles are safe to distribute" || true
    else
        log_fail "Client distribution gate failed"
        echo "$gate_output"
        return 1
    fi
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
    echo "Xray service: $XRAY_SERVICE"
    echo "Xray config: $XRAY_CONFIG"
    echo "Xray version: $(xray_version)"
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

Service: $XRAY_SERVICE
Service Status: $(systemctl is-active "$XRAY_SERVICE" 2>/dev/null || echo 'unknown')
Xray Config: $XRAY_CONFIG
Xray Version: $(xray_version)

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
    check_client_distribution
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
