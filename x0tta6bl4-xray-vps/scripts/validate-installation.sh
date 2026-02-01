#!/bin/bash
# Xray Installation Validation Script
# Validates Xray deployment and tests all protocols
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

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNINGS=0

# Configuration paths
CONFIG_DIR="/usr/local/etc/xray"
LOG_DIR="/var/log/xray"
CLIENT_DIR="/root/xray-clients"
BACKUP_DIR="/root/xray-backups"

# Protocol test results
declare -A PROTOCOL_STATUS

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; ((TESTS_PASSED++)); }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; ((TESTS_FAILED++)); }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((TESTS_WARNINGS++)); }
log_section() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# Check if running as root
check_root() {
    log_section "PRIVILEGE CHECK"
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
    log_success "Running as root"
}

# Check Xray binary
check_xray_binary() {
    log_section "XRAY BINARY"
    
    if [[ -f /usr/local/bin/xray ]]; then
        log_success "Xray binary exists at /usr/local/bin/xray"
        
        VERSION=$(xray -version 2>/dev/null | head -1 || echo "unknown")
        log_info "Xray version: $VERSION"
        
        if xray -version &>/dev/null; then
            log_success "Xray binary is executable"
        else
            log_error "Xray binary is not executable"
        fi
        
        # Check if binary is from official source
        if [[ -f /usr/local/bin/xray ]]; then
            BINARY_SIZE=$(stat -c%s /usr/local/bin/xray 2>/dev/null || stat -f%z /usr/local/bin/xray 2>/dev/null)
            log_info "Binary size: $BINARY_SIZE bytes"
        fi
    else
        log_error "Xray binary not found at /usr/local/bin/xray"
    fi
}

# Check Xray service
check_service() {
    log_section "SYSTEMD SERVICE"
    
    if systemctl is-active --quiet xray; then
        log_success "Xray service is running"
        
        # Get service uptime
        UPTIME=$(systemctl show xray --property=ActiveEnterTimestamp --value 2>/dev/null || echo "unknown")
        log_info "Service active since: $UPTIME"
        
        # Check for restarts
        RESTART_COUNT=$(systemctl show xray --property=NRestarts --value 2>/dev/null || echo "0")
        if [[ "$RESTART_COUNT" -gt 0 ]]; then
            log_warn "Service has been restarted $RESTART_COUNT times"
        fi
    else
        log_error "Xray service is not running"
        systemctl status xray --no-pager || true
    fi
    
    if systemctl is-enabled --quiet xray 2>/dev/null; then
        log_success "Xray service is enabled on boot"
    else
        log_warn "Xray service is not enabled on boot"
    fi
    
    # Check service file
    if [[ -f /etc/systemd/system/xray.service ]]; then
        log_success "Systemd service file exists"
    else
        log_error "Systemd service file not found"
    fi
}

# Check configuration file
check_config() {
    log_section "CONFIGURATION VALIDATION"
    
    if [[ -f ${CONFIG_DIR}/config.json ]]; then
        log_success "Configuration file exists"
        
        # Check JSON validity
        if jq empty ${CONFIG_DIR}/config.json 2>/dev/null; then
            log_success "Configuration is valid JSON"
        else
            log_error "Configuration is invalid JSON"
            return
        fi
        
        # Test with Xray
        if xray -test -config ${CONFIG_DIR}/config.json &>/dev/null; then
            log_success "Xray configuration test passed"
        else
            log_error "Xray configuration test failed"
            xray -test -config ${CONFIG_DIR}/config.json || true
        fi
        
        # Check for required sections
        local required_sections=("log" "inbounds" "outbounds" "routing")
        for section in "${required_sections[@]}"; do
            if jq -e ".$section" ${CONFIG_DIR}/config.json &>/dev/null; then
                log_success "Configuration section '$section' exists"
            else
                log_error "Configuration section '$section' missing"
            fi
        done
        
        # Count inbounds
        INBOUND_COUNT=$(jq '.inbounds | length' ${CONFIG_DIR}/config.json 2>/dev/null || echo "0")
        log_info "Number of inbounds configured: $INBOUND_COUNT"
        
    else
        log_error "Configuration file not found at ${CONFIG_DIR}/config.json"
    fi
}

# Check ports
check_ports() {
    log_section "PORT LISTENING STATUS"
    
    declare -A PORTS
    PORTS[443]="VLESS-Reality"
    PORTS[8443]="VLESS-XHTTP"
    PORTS[8388]="Shadowsocks"
    PORTS[9443]="Trojan"
    PORTS[8080]="VMESS-WS"
    PORTS[10085]="Xray-API"
    
    for port in "${!PORTS[@]}"; do
        local protocol="${PORTS[$port]}"
        if netstat -tlnp 2>/dev/null | grep -q ":$port " || \
           ss -tlnp 2>/dev/null | grep -q ":$port " || \
           lsof -i :$port 2>/dev/null | grep -q LISTEN; then
            log_success "Port $port ($protocol) is listening"
            PROTOCOL_STATUS[$port]="UP"
        else
            log_warn "Port $port ($protocol) is not listening"
            PROTOCOL_STATUS[$port]="DOWN"
        fi
    done
}

# Check certificates
check_certificates() {
    log_section "TLS CERTIFICATES"
    
    if [[ -f /etc/ssl/xray/xray.crt && -f /etc/ssl/xray/xray.key ]]; then
        log_success "TLS certificates exist"
        
        # Check certificate validity
        if openssl x509 -in /etc/ssl/xray/xray.crt -noout -checkend 86400 &>/dev/null; then
            log_success "Certificate is valid for at least 24 hours"
        else
            log_warn "Certificate expires soon or is invalid"
        fi
        
        # Get certificate details
        CERT_SUBJECT=$(openssl x509 -in /etc/ssl/xray/xray.crt -noout -subject 2>/dev/null | cut -d'=' -f2-)
        CERT_ISSUER=$(openssl x509 -in /etc/ssl/xray/xray.crt -noout -issuer 2>/dev/null | cut -d'=' -f2-)
        CERT_EXPIRY=$(openssl x509 -in /etc/ssl/xray/xray.crt -noout -enddate 2>/dev/null | cut -d'=' -f2)
        log_info "Certificate Subject: $CERT_SUBJECT"
        log_info "Certificate Issuer: $CERT_ISSUER"
        log_info "Certificate Expiry: $CERT_EXPIRY"
        
        # Check key permissions
        KEY_PERMS=$(stat -c %a /etc/ssl/xray/xray.key 2>/dev/null || stat -f %Lp /etc/ssl/xray/xray.key 2>/dev/null)
        if [[ "$KEY_PERMS" == "600" ]]; then
            log_success "Key file has correct permissions (600)"
        else
            log_warn "Key file permissions: $KEY_PERMS (should be 600)"
        fi
        
        # Check certificate permissions
        CERT_PERMS=$(stat -c %a /etc/ssl/xray/xray.crt 2>/dev/null || stat -f %Lp /etc/ssl/xray/xray.crt 2>/dev/null)
        if [[ "$CERT_PERMS" == "644" ]]; then
            log_success "Certificate file has correct permissions (644)"
        else
            log_warn "Certificate file permissions: $CERT_PERMS (should be 644)"
        fi
    else
        log_error "TLS certificates not found in /etc/ssl/xray/"
    fi
}

# Check logs
check_logs() {
    log_section "LOG ANALYSIS"
    
    if [[ -d ${LOG_DIR} ]]; then
        log_success "Log directory exists"
        
        # Check access log
        if [[ -f ${LOG_DIR}/access.log ]]; then
            log_success "Access log exists"
            ACCESS_LOG_SIZE=$(stat -c%s ${LOG_DIR}/access.log 2>/dev/null || stat -f%z ${LOG_DIR}/access.log 2>/dev/null)
            log_info "Access log size: $ACCESS_LOG_SIZE bytes"
        else
            log_warn "Access log not found"
        fi
        
        # Check error log
        if [[ -f ${LOG_DIR}/error.log ]]; then
            log_success "Error log exists"
            ERROR_LOG_SIZE=$(stat -c%s ${LOG_DIR}/error.log 2>/dev/null || stat -f%z ${LOG_DIR}/error.log 2>/dev/null)
            log_info "Error log size: $ERROR_LOG_SIZE bytes"
            
            # Check for recent errors (last 50 lines)
            RECENT_ERRORS=$(tail -50 ${LOG_DIR}/error.log 2>/dev/null | grep -c "error\|Error\|ERROR" || echo "0")
            if [[ "$RECENT_ERRORS" -gt 0 ]]; then
                log_warn "Found $RECENT_ERRORS error entries in recent logs"
                log_info "Recent errors:"
                tail -20 ${LOG_DIR}/error.log | grep -i "error" | head -5 || true
            else
                log_success "No recent errors in error log"
            fi
        else
            log_warn "Error log not found"
        fi
    else
        log_error "Log directory not found at ${LOG_DIR}"
    fi
}

# Check client configurations
check_client_configs() {
    log_section "CLIENT CONFIGURATIONS"
    
    if [[ -d ${CLIENT_DIR} ]]; then
        log_success "Client configuration directory exists"
        
        # List all config files
        CONFIG_COUNT=$(find ${CLIENT_DIR} -type f | wc -l)
        log_info "Found $CONFIG_COUNT configuration files"
        
        # Check each config file
        for file in ${CLIENT_DIR}/*; do
            if [[ -f "$file" ]]; then
                local basename=$(basename "$file")
                log_info "Found: $basename"
                
                # Validate JSON files
                if [[ "$file" == *.json ]]; then
                    if jq empty "$file" 2>/dev/null; then
                        log_success "$basename is valid JSON"
                    else
                        log_error "$basename is invalid JSON"
                    fi
                fi
            fi
        done
    else
        log_warn "Client configuration directory not found at ${CLIENT_DIR}"
    fi
}

# Check firewall status
check_firewall() {
    log_section "FIREWALL STATUS"
    
    # Check UFW
    if command -v ufw &> /dev/null; then
        if ufw status 2>/dev/null | grep -q "Status: active"; then
            log_success "UFW is active"
            log_info "UFW rules:"
            ufw status numbered | grep -E "443|8443|8388|9443|8080" || log_warn "No Xray ports found in UFW rules"
        else
            log_warn "UFW is not active"
        fi
    fi
    
    # Check FirewallD
    if command -v firewall-cmd &> /dev/null; then
        if firewall-cmd --state 2>/dev/null | grep -q "running"; then
            log_success "FirewallD is running"
            log_info "FirewallD zones:"
            firewall-cmd --list-ports | grep -E "443|8443|8388|9443|8080" || log_warn "No Xray ports found in FirewallD"
        else
            log_warn "FirewallD is not running"
        fi
    fi
    
    # Check iptables
    if command -v iptables &> /dev/null; then
        log_info "iptables rules for Xray ports:"
        iptables -L -n 2>/dev/null | grep -E "443|8443|8388|9443|8080" || log_info "No specific Xray rules in iptables"
    fi
}

# Check system resources
check_system_resources() {
    log_section "SYSTEM RESOURCES"
    
    # Check memory
    TOTAL_MEM=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo "0")
    FREE_MEM=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}' || echo "0")
    log_info "Total Memory: ${TOTAL_MEM}MB"
    log_info "Free Memory: ${FREE_MEM}MB"
    
    if [[ "$FREE_MEM" -lt 100 ]]; then
        log_warn "Low free memory: ${FREE_MEM}MB"
    else
        log_success "Sufficient free memory available"
    fi
    
    # Check disk space
    DISK_USAGE=$(df -h / 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//' || echo "0")
    log_info "Disk usage: ${DISK_USAGE}%"
    
    if [[ "$DISK_USAGE" -gt 90 ]]; then
        log_warn "High disk usage: ${DISK_USAGE}%"
    else
        log_success "Disk usage is acceptable"
    fi
    
    # Check load average
    LOAD_AVG=$(uptime 2>/dev/null | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//' || echo "0")
    log_info "Load average (1min): $LOAD_AVG"
    
    # Check file descriptors
    if [[ -f /proc/sys/fs/file-max ]]; then
        FILE_MAX=$(cat /proc/sys/fs/file-max)
        log_info "Max file descriptors: $FILE_MAX"
    fi
}

# Check network connectivity
check_network() {
    log_section "NETWORK CONNECTIVITY"
    
    # Check if we can reach the internet
    if ping -c 1 -W 3 1.1.1.1 &>/dev/null; then
        log_success "Internet connectivity available"
    else
        log_warn "No internet connectivity detected"
    fi
    
    # Get public IP
    PUBLIC_IP=$(curl -s -4 --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    log_info "Public IP: $PUBLIC_IP"
    
    # Check DNS resolution
    if nslookup google.com &>/dev/null; then
        log_success "DNS resolution working"
    else
        log_warn "DNS resolution may have issues"
    fi
}

# Check Reality configuration
check_reality() {
    log_section "REALITY PROTOCOL CHECK"
    
    if [[ -f ${CONFIG_DIR}/config.json ]]; then
        # Check if Reality is configured
        if jq -e '.inbounds[] | select(.streamSettings.security == "reality")' ${CONFIG_DIR}/config.json &>/dev/null; then
            log_success "Reality is configured"
            
            # Extract Reality settings
            REALITY_INBOUND=$(jq '.inbounds[] | select(.streamSettings.security == "reality")' ${CONFIG_DIR}/config.json)
            DEST=$(echo "$REALITY_INBOUND" | jq -r '.streamSettings.realitySettings.dest // empty')
            SERVER_NAMES=$(echo "$REALITY_INBOUND" | jq -r '.streamSettings.realitySettings.serverNames | join(", ") // empty')
            
            log_info "Reality dest: $DEST"
            log_info "Reality serverNames: $SERVER_NAMES"
            
            # Test if dest is reachable
            DEST_HOST=$(echo "$DEST" | cut -d':' -f1)
            if ping -c 1 -W 3 "$DEST_HOST" &>/dev/null; then
                log_success "Reality destination ($DEST_HOST) is reachable"
            else
                log_warn "Reality destination ($DEST_HOST) may not be reachable"
            fi
        else
            log_warn "Reality is not configured"
        fi
    fi
}

# Check BBR and TCP optimization
check_tcp_optimization() {
    log_section "TCP OPTIMIZATION"
    
    # Check if BBR is enabled
    CURRENT_CC=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo "unknown")
    log_info "Current congestion control: $CURRENT_CC"
    
    if [[ "$CURRENT_CC" == "bbr" ]]; then
        log_success "BBR is enabled"
    else
        log_warn "BBR is not enabled (current: $CURRENT_CC)"
    fi
    
    # Check available congestion control algorithms
    AVAILABLE_CC=$(sysctl -n net.ipv4.tcp_available_congestion_control 2>/dev/null || echo "unknown")
    log_info "Available congestion control: $AVAILABLE_CC"
    
    # Check TCP buffer sizes
    RMEM_MAX=$(sysctl -n net.core.rmem_max 2>/dev/null || echo "0")
    WMEM_MAX=$(sysctl -n net.core.wmem_max 2>/dev/null || echo "0")
    log_info "TCP read buffer max: $RMEM_MAX"
    log_info "TCP write buffer max: $WMEM_MAX"
}

# Perform health check
health_check() {
    log_section "HEALTH CHECK"
    
    local healthy=true
    
    # Check critical components
    if ! systemctl is-active --quiet xray; then
        log_error "Xray service is not running - CRITICAL"
        healthy=false
    fi
    
    if ! [[ -f ${CONFIG_DIR}/config.json ]]; then
        log_error "Configuration file missing - CRITICAL"
        healthy=false
    fi
    
    if ! xray -test -config ${CONFIG_DIR}/config.json &>/dev/null; then
        log_error "Configuration test failed - CRITICAL"
        healthy=false
    fi
    
    # Check if at least one inbound is listening
    local any_listening=false
    for port in 443 8443 8388 9443 8080; do
        if ss -tlnp 2>/dev/null | grep -q ":$port "; then
            any_listening=true
            break
        fi
    done
    
    if [[ "$any_listening" == "false" ]]; then
        log_error "No Xray ports are listening - CRITICAL"
        healthy=false
    fi
    
    if [[ "$healthy" == "true" ]]; then
        log_success "All health checks passed - System is HEALTHY"
        return 0
    else
        log_error "Health checks failed - System is UNHEALTHY"
        return 1
    fi
}

# Generate report
generate_report() {
    log_section "VALIDATION SUMMARY"
    
    echo -e "\n${CYAN}Test Results:${NC}"
    echo -e "  ${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "  ${RED}Failed: $TESTS_FAILED${NC}"
    echo -e "  ${YELLOW}Warnings: $TESTS_WARNINGS${NC}"
    
    echo -e "\n${CYAN}Protocol Status:${NC}"
    for port in "${!PROTOCOL_STATUS[@]}"; do
        local status="${PROTOCOL_STATUS[$port]}"
        if [[ "$status" == "UP" ]]; then
            echo -e "  Port $port: ${GREEN}UP${NC}"
        else
            echo -e "  Port $port: ${YELLOW}DOWN${NC}"
        fi
    done
    
    echo -e "\n${CYAN}Overall Status:${NC}"
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "  ${GREEN}✓ All critical checks passed${NC}"
        return 0
    else
        echo -e "  ${RED}✗ Some checks failed - review required${NC}"
        return 1
    fi
}

# Save report to file
save_report() {
    local report_file="${LOG_DIR}/validation-report-$(date +%Y%m%d-%H%M%S).log"
    
    cat > "$report_file" << EOF
Xray Validation Report
======================
Date: $(date)
Hostname: $(hostname)
Public IP: $(curl -s -4 ifconfig.me 2>/dev/null || echo "unknown")

Test Results:
  Passed: $TESTS_PASSED
  Failed: $TESTS_FAILED
  Warnings: $TESTS_WARNINGS

Xray Version: $(xray -version 2>/dev/null | head -1 || echo "unknown")
Service Status: $(systemctl is-active xray 2>/dev/null || echo "unknown")

Protocol Status:
$(for port in "${!PROTOCOL_STATUS[@]}"; do echo "  Port $port: ${PROTOCOL_STATUS[$port]}"; done)

Configuration:
  Config File: ${CONFIG_DIR}/config.json
  Inbounds: $(jq '.inbounds | length' ${CONFIG_DIR}/config.json 2>/dev/null || echo "0")
EOF

    log_info "Report saved to: $report_file"
}

# Main function
main() {
    clear
    echo -e "${CYAN}"
    echo "  __  __          __        __   _           __  ____  ____"
    echo "  \\ \\/ /__  _____/ /_____ _/ /  (_)__  ___  /  |/  / |/ / /"
    echo "   \\  / _ \\/ ___/ __/ __ \\ / /  / / _ \\/ _ \\/ /|_/ /    /_/"
    echo "   / /  __/ /__/ /_/ /_/ // /__/ / __/  __/ /  / / /| / /"
    echo "  /_/\\___/\\___/\\__/\\____/____/_/_/  \\___/_/  /_/_/ |_/_/"
    echo ""
    echo -e "${NC}"
    echo -e "  ${BLUE}Xray Installation Validation Script${NC}"
    echo -e "  ${BLUE}Version: 1.0.0 | Date: 2026-01-31${NC}"
    echo ""
    
    check_root
    check_xray_binary
    check_service
    check_config
    check_ports
    check_certificates
    check_logs
    check_client_configs
    check_firewall
    check_system_resources
    check_network
    check_reality
    check_tcp_optimization
    health_check
    generate_report
    save_report
    
    echo -e "\n${BLUE}Validation complete!${NC}\n"
    
    # Exit with appropriate code
    if [[ $TESTS_FAILED -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"
