#!/bin/bash
#
# x0tta6bl4 Network Kill Switch
# Blocks all outgoing traffic except through VPN tunnel
# Prevents IP leaks on VPN disconnect
#

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="/var/log/x0tta6bl4-killswitch.log"
readonly LOCK_FILE="/var/run/x0tta6bl4-killswitch.lock"

# Configuration
VPN_INTERFACE="${VPN_INTERFACE:-wg0}"
VPN_GATEWAY="${VPN_GATEWAY:-}"
ALLOWED_SUBNETS="${ALLOWED_SUBNETS:-}"
NAMESERVERS="${NAMESERVERS:-1.1.1.1 1.0.0.1}"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
    log "ERROR: $1"
}

success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
    log "SUCCESS: $1"
}

warn() {
    echo -e "${YELLOW}WARNING: $1${NC}"
    log "WARNING: $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
}

detect_firewall() {
    if command -v nft &> /dev/null && [[ -f /etc/nftables.conf ]]; then
        echo "nftables"
    elif command -v iptables &> /dev/null; then
        echo "iptables"
    else
        error "Neither nftables nor iptables found"
        exit 1
    fi
}

get_default_interface() {
    ip route | grep default | awk '{print $5}' | head -n1
}

get_vpn_gateway() {
    local vpn_iface="$1"
    ip route | grep "dev $vpn_iface" | grep "src" | awk '{print $9}' | head -n1
}

enable_iptables_killswitch() {
    local default_iface="$1"
    
    log "Enabling iptables kill switch..."
    
    # Save existing rules
    iptables-save > /tmp/iptables-backup-$(date +%s).rules 2>/dev/null || true
    
    # Flush existing rules
    iptables -F OUTPUT 2>/dev/null || true
    iptables -F INPUT 2>/dev/null || true
    iptables -F FORWARD 2>/dev/null || true
    
    # Default deny
    iptables -P OUTPUT DROP
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    
    # Allow loopback
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Allow established connections
    iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    
    # Allow DNS queries to trusted servers
    for ns in $NAMESERVERS; do
        iptables -A OUTPUT -p udp --dport 53 -d "$ns" -j ACCEPT
        iptables -A OUTPUT -p tcp --dport 53 -d "$ns" -j ACCEPT
    done
    
    # Allow VPN tunnel traffic (WireGuard default port)
    iptables -A OUTPUT -p udp --dport 51820 -j ACCEPT
    iptables -A OUTPUT -p udp --dport 2408 -j ACCEPT  # WARP
    
    # Allow OpenVPN ports
    iptables -A OUTPUT -p udp --dport 1194 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 1194 -j ACCEPT
    
    # Allow traffic through VPN interface
    iptables -A OUTPUT -o "$VPN_INTERFACE" -j ACCEPT
    iptables -A INPUT -i "$VPN_INTERFACE" -j ACCEPT
    
    # Allow DHCP
    iptables -A OUTPUT -p udp --sport 68 --dport 67 -j ACCEPT
    iptables -A INPUT -p udp --sport 67 --dport 68 -j ACCEPT
    
    # Allow allowed subnets
    if [[ -n "$ALLOWED_SUBNETS" ]]; then
        for subnet in $ALLOWED_SUBNETS; do
            iptables -A OUTPUT -d "$subnet" -j ACCEPT
        done
    fi
    
    # Log dropped packets (rate limited)
    iptables -A OUTPUT -m limit --limit 10/min -j LOG --log-prefix "KS-DROP: " --log-level 4
    
    touch "$LOCK_FILE"
    success "Kill switch enabled with iptables"
}

enable_nftables_killswitch() {
    local default_iface="$1"
    
    log "Enabling nftables kill switch..."
    
    # Save existing rules
    nft list ruleset > /tmp/nftables-backup-$(date +%s).rules 2>/dev/null || true
    
    # Create new ruleset
    cat > /tmp/x0tta6bl4-killswitch.nft << 'EOF'
#!/usr/sbin/nft -f

flush ruleset

table inet killswitch {
    set trusted_dns {
        type ipv4_addr
        flags interval
        elements = { 1.1.1.1, 1.0.0.1, 8.8.8.8, 8.8.4.4 }
    }
    
    set vpn_ports {
        type inet_proto . inet_service
        flags interval
        elements = { udp . 51820, udp . 2408, udp . 1194, tcp . 1194 }
    }
    
    chain input {
        type filter hook input priority 0; policy drop;
        
        # Allow loopback
        iif "lo" accept
        
        # Allow established/related
        ct state established,related accept
        
        # Allow VPN interface
        iifname "wg*" accept
        iifname "tun*" accept
        
        # Allow DHCP
        udp sport 67 udp dport 68 accept
        
        # ICMP (limited)
        ip protocol icmp icmp type { echo-request, echo-reply } limit rate 5/second accept
        ip6 nexthdr icmpv6 icmpv6 type { echo-request, echo-reply } limit rate 5/second accept
        
        # Log and drop
        log prefix "KS-IN-DROP: " limit rate 5/minute
    }
    
    chain output {
        type filter hook output priority 0; policy drop;
        
        # Allow loopback
        oif "lo" accept
        
        # Allow established/related
        ct state established,related accept
        
        # Allow DNS to trusted servers
        ip daddr @trusted_dns udp dport 53 accept
        ip daddr @trusted_dns tcp dport 53 accept
        
        # Allow VPN establishment traffic
        meta l4proto . th dport @vpn_ports accept
        
        # Allow VPN interface traffic
        oifname "wg*" accept
        oifname "tun*" accept
        
        # Allow DHCP
        udp sport 68 udp dport 67 accept
        
        # ICMP
        ip protocol icmp icmp type { echo-request, echo-reply } limit rate 5/second accept
        ip6 nexthdr icmpv6 icmpv6 type { echo-request, echo-reply } limit rate 5/second accept
        
        # Log and drop
        log prefix "KS-OUT-DROP: " limit rate 10/minute
    }
    
    chain forward {
        type filter hook forward priority 0; policy drop;
    }
}
EOF
    
    # Apply rules
    nft -f /tmp/x0tta6bl4-killswitch.nft
    
    touch "$LOCK_FILE"
    success "Kill switch enabled with nftables"
}

disable_killswitch() {
    log "Disabling kill switch..."
    
    local firewall
    firewall=$(detect_firewall)
    
    if [[ "$firewall" == "nftables" ]]; then
        nft flush ruleset
        # Restore original if exists
        if [[ -f /etc/nftables.conf ]]; then
            nft -f /etc/nftables.conf
        fi
    else
        iptables -P OUTPUT ACCEPT
        iptables -P INPUT ACCEPT
        iptables -P FORWARD ACCEPT
        iptables -F
    fi
    
    rm -f "$LOCK_FILE"
    success "Kill switch disabled"
}

status() {
    if [[ -f "$LOCK_FILE" ]]; then
        echo -e "${GREEN}Kill switch: ENABLED${NC}"
        
        local firewall
        firewall=$(detect_firewall)
        
        if [[ "$firewall" == "nftables" ]]; then
            echo "Firewall: nftables"
            nft list ruleset | grep -A5 "killswitch" || echo "  (rules not loaded)"
        else
            echo "Firewall: iptables"
            iptables -L OUTPUT -n | head -10
        fi
        
        # Show active VPN interface
        echo ""
        echo "VPN Interfaces:"
        ip link show | grep -E "(wg|tun)" || echo "  (none detected)"
        
        # Show current IP
        echo ""
        echo "Current External IP:"
        curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "  (unable to determine)"
    else
        echo -e "${YELLOW}Kill switch: DISABLED${NC}"
    fi
}

test_leak() {
    log "Testing for IP leaks..."
    
    echo "Testing through different methods..."
    
    # Test via different services
    echo "1. ifconfig.me: $(curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo 'FAILED')"
    echo "2. icanhazip.com: $(curl -s --max-time 5 https://icanhazip.com 2>/dev/null || echo 'FAILED')"
    echo "3. ipinfo.io: $(curl -s --max-time 5 https://ipinfo.io/ip 2>/dev/null || echo 'FAILED')"
    
    # DNS leak test
    echo ""
    echo "DNS Leak Test:"
    for ns in $NAMESERVERS; do
        if dig +short @$ns ch txt version.server 2>/dev/null | head -1; then
            echo "  $ns: REACHABLE"
        else
            echo "  $ns: UNREACHABLE"
        fi
    done
}

watchdog_start() {
    log "Starting VPN watchdog..."
    
    cat > /tmp/x0tta6bl4-watchdog.sh << 'EOF'
#!/bin/bash
VPN_IFACE="${VPN_INTERFACE:-wg0}"
LOG_FILE="/var/log/x0tta6bl4-watchdog.log"

while true; do
    if ! ip link show "$VPN_IFACE" &>/dev/null; then
        echo "$(date): VPN interface $VPN_IFACE down! Kill switch active." >> "$LOG_FILE"
        # Could trigger emergency actions here
        # ./emergency-severance.sh
    fi
    sleep 5
done
EOF
    chmod +x /tmp/x0tta6bl4-watchdog.sh
    
    # Start in background
    nohup /tmp/x0tta6bl4-watchdog.sh > /dev/null 2>&1 &
    echo $! > /var/run/x0tta6bl4-watchdog.pid
    
    success "Watchdog started (PID: $(cat /var/run/x0tta6bl4-watchdog.pid))"
}

watchdog_stop() {
    if [[ -f /var/run/x0tta6bl4-watchdog.pid ]]; then
        kill "$(cat /var/run/x0tta6bl4-watchdog.pid)" 2>/dev/null || true
        rm -f /var/run/x0tta6bl4-watchdog.pid
        success "Watchdog stopped"
    else
        warn "Watchdog not running"
    fi
}

usage() {
    cat << EOF
Usage: $0 [command] [options]

Commands:
    enable          Enable kill switch (blocks non-VPN traffic)
    disable         Disable kill switch (restore normal connectivity)
    status          Show current kill switch status
    test            Test for IP/DNS leaks
    watchdog-start  Start VPN monitoring watchdog
    watchdog-stop   Stop VPN monitoring watchdog

Environment Variables:
    VPN_INTERFACE   VPN interface name (default: wg0)
    VPN_GATEWAY     VPN gateway IP (auto-detected if not set)
    ALLOWED_SUBNETS Space-separated list of allowed subnets
    NAMESERVERS     Space-separated DNS servers (default: 1.1.1.1 1.0.0.1)

Examples:
    sudo $0 enable
    sudo VPN_INTERFACE=tun0 $0 enable
    sudo ALLOWED_SUBNETS="192.168.1.0/24" $0 enable
    $0 status
    $0 test
EOF
}

main() {
    case "${1:-}" in
        enable)
            check_root
            local default_iface
            default_iface=$(get_default_interface)
            local firewall
            firewall=$(detect_firewall)
            
            if [[ "$firewall" == "nftables" ]]; then
                enable_nftables_killswitch "$default_iface"
            else
                enable_iptables_killswitch "$default_iface"
            fi
            ;;
        disable)
            check_root
            disable_killswitch
            ;;
        status)
            status
            ;;
        test)
            test_leak
            ;;
        watchdog-start)
            check_root
            watchdog_start
            ;;
        watchdog-stop)
            check_root
            watchdog_stop
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
