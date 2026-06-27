#!/bin/bash
# Emergency Identity Severance Protocol
# Execute this script immediately upon suspected identity compromise

set -euo pipefail

LOG_FILE="/var/log/emergency-severance.log"
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${BOLD}$1${NC}" | tee -a "$LOG_FILE"
}

# ============================================================================
# PHASE 1: IMMEDIATE NETWORK ISOLATION
# ============================================================================

phase1_network_isolation() {
    header "PHASE 1: IMMEDIATE NETWORK ISOLATION"
    
    log "Initiating emergency network disconnect..."
    
    # Disable all network interfaces
    for iface in $(ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -v "lo"); do
        if [[ -d "/sys/class/net/$iface" ]]; then
            log "Bringing down interface: $iface"
            ip link set "$iface" down 2>/dev/null || warning "Failed to bring down $iface"
        fi
    done
    
    # Stop NetworkManager
    systemctl stop NetworkManager 2>/dev/null || true
    systemctl disable NetworkManager 2>/dev/null || true
    
    # Stop networking service
    systemctl stop networking 2>/dev/null || true
    
    # Disable WiFi via rfkill
    rfkill block wifi 2>/dev/null || true
    rfkill block bluetooth 2>/dev/null || true
    
    success "Network interfaces disabled"
}

# ============================================================================
# PHASE 2: VPN TERMINATION
# ============================================================================

phase2_vpn_termination() {
    header "PHASE 2: VPN TERMINATION"
    
    log "Terminating all VPN connections..."
    
    # Kill OpenVPN
    pkill -9 -f openvpn 2>/dev/null || true
    
    # Kill WireGuard
    for iface in $(ip link show | grep -oE "wg[0-9]+|tun-[^:]" 2>/dev/null || true); do
        log "Shutting down WireGuard interface: $iface"
        wg-quick down "$iface" 2>/dev/null || true
    done
    
    # Stop VPN services
    systemctl stop vpn-chain 2>/dev/null || true
    systemctl stop wg-quick@* 2>/dev/null || true
    
    # Kill Tor
    pkill -9 -f tor 2>/dev/null || true
    systemctl stop tor 2>/dev/null || true
    
    success "All VPN connections terminated"
}

# ============================================================================
# PHASE 3: BROWSER TERMINATION
# ============================================================================

phase3_browser_termination() {
    header "PHASE 3: BROWSER TERMINATION"
    
    log "Killing all browser processes..."
    
    # Firefox
    pkill -9 -f firefox 2>/dev/null || true
    pkill -9 -f firefox-esr 2>/dev/null || true
    
    # Chrome/Chromium
    pkill -9 -f chrome 2>/dev/null || true
    pkill -9 -f chromium 2>/dev/null || true
    pkill -9 -f chromium-browser 2>/dev/null || true
    pkill -9 -f google-chrome 2>/dev/null || true
    
    # Tor Browser
    pkill -9 -f "tor-browser" 2>/dev/null || true
    
    # Kill all WebContent processes (macOS)
    pkill -9 -f "WebContent" 2>/dev/null || true
    
    success "All browser processes terminated"
}

# ============================================================================
# PHASE 4: ACTIVATE KILLSWITCH
# ============================================================================

phase4_killswitch() {
    header "PHASE 4: ACTIVATE NETWORK KILLSWITCH"
    
    log "Activating emergency killswitch..."
    
    # Flush all iptables rules
    iptables -F 2>/dev/null || true
    iptables -X 2>/dev/null || true
    iptables -t nat -F 2>/dev/null || true
    iptables -t nat -X 2>/dev/null || true
    iptables -t mangle -F 2>/dev/null || true
    iptables -t mangle -X 2>/dev/null || true
    
    # IPv6
    ip6tables -F 2>/dev/null || true
    ip6tables -X 2>/dev/null || true
    
    # Set default policies to DROP
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT DROP
    
    ip6tables -P INPUT DROP 2>/dev/null || true
    ip6tables -P FORWARD DROP 2>/dev/null || true
    ip6tables -P OUTPUT DROP 2>/dev/null || true
    
    # Allow loopback only
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Log dropped packets (rate limited)
    iptables -A INPUT -m limit --limit 5/min -j LOG --log-prefix "[EMERGENCY DROP] " --log-level 4
    iptables -A OUTPUT -m limit --limit 5/min -j LOG --log-prefix "[EMERGENCY DROP] " --log-level 4
    
    success "Emergency killswitch activated - ONLY LOOPBACK TRAFFIC ALLOWED"
    warning "System is now completely isolated from network"
}

# ============================================================================
# PHASE 5: CLEAR SENSITIVE DATA
# ============================================================================

phase5_clear_data() {
    header "PHASE 5: CLEAR SENSITIVE DATA"
    
    log "Clearing sensitive data..."
    
    # Clear shell history
    if [[ -f ~/.bash_history ]]; then
        shred -vfz -n 3 ~/.bash_history 2>/dev/null || rm -f ~/.bash_history
        log "Cleared bash history"
    fi
    
    if [[ -f ~/.zsh_history ]]; then
        shred -vfz -n 3 ~/.zsh_history 2>/dev/null || rm -f ~/.zsh_history
        log "Cleared zsh history"
    fi
    
    # Clear current session history
    history -c 2>/dev/null || true
    
    # Clear clipboard
    echo -n | xclip -selection clipboard 2>/dev/null || true
    echo -n | xclip -selection primary 2>/dev/null || true
    echo -n | xclip -selection secondary 2>/dev/null || true
    
    # Clear recent files (GNOME)
    rm -f ~/.local/share/recently-used.xbel 2>/dev/null || true
    
    # Clear thumbnails
    rm -rf ~/.cache/thumbnails/* 2>/dev/null || true
    
    # Clear temporary files
    rm -rf /tmp/.X11-unix/* 2>/dev/null || true
    rm -rf /tmp/ssh-* 2>/dev/null || true
    
    success "Sensitive data cleared"
}

# ============================================================================
# PHASE 6: SECURE MEMORY
# ============================================================================

phase6_secure_memory() {
    header "PHASE 6: SECURE MEMORY"
    
    log "Attempting to secure memory..."
    
    # Drop caches
    echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || warning "Could not drop caches"
    
    # Sync filesystems
    sync
    
    # Note: Full memory wipe requires kernel module or reboot to cold boot state
    warning "Note: Full memory wipe requires reboot or specialized tools"
    
    success "Memory secured (best effort)"
}

# ============================================================================
# PHASE 7: ACCOUNT SECURITY
# ============================================================================

phase7_account_security() {
    header "PHASE 7: ACCOUNT SECURITY ACTIONS"
    
    warning "Manual actions required:"
    echo ""
    echo "1. FROM ANOTHER DEVICE, immediately:"
    echo "   - Change passwords for all compromised accounts"
    echo "   - Force logout all sessions"
    echo "   - Revoke OAuth tokens"
    echo "   - Check for unauthorized access"
    echo ""
    echo "2. Notify contacts via out-of-band channel"
    echo "   - Assume this device is compromised"
    echo "   - Do NOT use normal communication channels"
    echo ""
    echo "3. Document the incident"
    echo "   - What was accessed?"
    echo "   - When did compromise occur?"
    echo "   - What data may be exposed?"
    echo ""
    
    # Create incident report template
    cat > "/tmp/incident-report-$TIMESTAMP.txt" << EOF
EMERGENCY INCIDENT REPORT
=========================

Timestamp: $(date -Iseconds)
Action: Emergency Identity Severance Executed

IMMEDIATE ACTIONS TAKEN:
- Network interfaces disabled
- VPN connections terminated
- Browser processes killed
- Killswitch activated
- Sensitive data cleared
- Memory secured

MANUAL ACTIONS REQUIRED:
[ ] Change all account passwords
[ ] Force logout all sessions
[ ] Revoke OAuth tokens
[ ] Check account access logs
[ ] Notify contacts (out-of-band)
[ ] Document incident details

SYSTEM STATE:
- Network: COMPLETELY ISOLATED
- VPN: TERMINATED
- Browsers: TERMINATED
- Killswitch: ACTIVE

NEXT STEPS:
1. Do NOT reconnect this device to network
2. Use separate clean device for account recovery
3. Assess compromise scope
4. Plan new identity establishment
5. Review and improve OPSEC

EOF

    success "Incident report template created: /tmp/incident-report-$TIMESTAMP.txt"
}

# ============================================================================
# PHASE 8: FINALIZE
# ============================================================================

phase8_finalize() {
    header "PHASE 8: FINALIZATION"
    
    # Log completion
    log "Emergency severance protocol completed"
    
    # Create status file
    cat > "/tmp/emergency-severance-$TIMESTAMP.status" << EOF
EMERGENCY SEVERANCE COMPLETED
=============================
Timestamp: $(date -Iseconds)
Status: SYSTEM ISOLATED

Network: DISABLED
VPN: TERMINATED
Browsers: TERMINATED
Killswitch: ACTIVE
Data: CLEARED

DO NOT RECONNECT TO NETWORK WITHOUT PROPER ANALYSIS
EOF

    success "Emergency severance protocol COMPLETE"
    echo ""
    header "╔════════════════════════════════════════════════════════════╗"
    header "║  EMERGENCY SEVERANCE COMPLETE                              ║"
    header "║                                                            ║"
    header "║  System is now COMPLETELY ISOLATED                         ║"
    header "║  Only loopback traffic is allowed                          ║"
    header "║                                                            ║"
    header "║  DO NOT reconnect to network without:                      ║"
    header "║  1. Full system analysis                                   ║"
    header "║  2. Understanding compromise vector                        ║"
    header "║  3. Establishing new identity infrastructure               ║"
    header "║                                                            ║"
    header "║  See: /tmp/incident-report-$TIMESTAMP.txt         ║"
    header "╚════════════════════════════════════════════════════════════╝"
    echo ""
}

# ============================================================================
# RESTORE FUNCTIONS (for recovery)
# ============================================================================

restore_network() {
    header "RESTORING NETWORK CONNECTIVITY"
    
    warning "Only run this after thorough analysis!"
    read -p "Are you sure you want to restore network? (type YES): " confirm
    
    if [[ "$confirm" != "YES" ]]; then
        log "Network restore cancelled"
        return 1
    fi
    
    # Reset iptables
    iptables -P INPUT ACCEPT
    iptables -P FORWARD ACCEPT
    iptables -P OUTPUT ACCEPT
    iptables -F
    iptables -X
    
    ip6tables -P INPUT ACCEPT 2>/dev/null || true
    ip6tables -P FORWARD ACCEPT 2>/dev/null || true
    ip6tables -P OUTPUT ACCEPT 2>/dev/null || true
    ip6tables -F 2>/dev/null || true
    ip6tables -X 2>/dev/null || true
    
    # Enable interfaces
    for iface in $(ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -v "lo"); do
        if [[ -d "/sys/class/net/$iface" ]]; then
            ip link set "$iface" up 2>/dev/null || true
        fi
    done
    
    # Start NetworkManager
    systemctl start NetworkManager 2>/dev/null || true
    
    # Unblock WiFi
    rfkill unblock wifi 2>/dev/null || true
    rfkill unblock bluetooth 2>/dev/null || true
    
    success "Network connectivity restored"
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
    
    echo ""
    header "╔════════════════════════════════════════════════════════════╗"
    header "║  EMERGENCY IDENTITY SEVERANCE PROTOCOL                     ║"
    header "║                                                            ║"
    header "║  This will IMMEDIATELY isolate the system                  ║"
    header "║  All network connections will be TERMINATED                ║"
    header "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    case "${1:-execute}" in
        execute|start|run)
            read -p "Execute emergency severance? (type EMERGENCY to confirm): " confirm
            
            if [[ "$confirm" != "EMERGENCY" ]]; then
                log "Emergency severance cancelled"
                exit 0
            fi
            
            log "EMERGENCY SEVERANCE INITIATED"
            
            phase1_network_isolation
            phase2_vpn_termination
            phase3_browser_termination
            phase4_killswitch
            phase5_clear_data
            phase6_secure_memory
            phase7_account_security
            phase8_finalize
            
            # Log completion
            log "Emergency severance protocol completed at $(date)"
            ;;
            
        restore|recover)
            restore_network
            ;;
            
        status)
            header "EMERGENCY SEVERANCE STATUS"
            
            # Check network status
            echo ""
            echo "Network Interfaces:"
            ip link show | grep -E "^[0-9]+:" | grep -v "lo:" || echo "  No active interfaces"
            
            # Check iptables
            echo ""
            echo "iptables Policy:"
            iptables -L -n | grep -E "^Chain" | grep "policy" || echo "  No rules found"
            
            # Check for status files
            echo ""
            echo "Recent Severance Events:"
            ls -lt /tmp/emergency-severance-*.status 2>/dev/null | head -5 || echo "  No recent events"
            ;;
            
        *)
            echo "Emergency Identity Severance Protocol"
            echo ""
            echo "Usage: $0 {execute|restore|status}"
            echo ""
            echo "Commands:"
            echo "  execute  - Execute emergency severance (DESTRUCTIVE)"
            echo "  restore  - Restore network connectivity (DANGEROUS)"
            echo "  status   - Check severance status"
            echo ""
            echo "WARNING: execute will immediately isolate the system!"
            exit 1
            ;;
    esac
}

main "$@"
