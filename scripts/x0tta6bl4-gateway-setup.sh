#!/bin/bash
#
# x0tta6bl4 Mesh Gateway Setup Script
# Configures network stack for transparent traffic routing through mesh
#
# Usage:
#   sudo ./x0tta6bl4-gateway-setup.sh setup
#   sudo ./x0tta6bl4-gateway-setup.sh teardown
#   sudo ./x0tta6bl4-gateway-setup.sh status
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TUN_DEV="${TUN_DEV:-tun0}"
TUN_IP="${TUN_IP:-10.0.0.1}"
TUN_PEER="${TUN_PEER:-10.0.0.2}"
MESH_TABLE="${MESH_TABLE:-x0tta6bl4_mesh}"
MESH_TABLE_ID="${MESH_TABLE_ID:-200}"
MARK="${MARK:-0x1}"
SOCKS_PORT="${SOCKS_PORT:-1080}"
DNS_PORT="${DNS_PORT:-5353}"

# Functions

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    local missing=()
    
    for cmd in ip iptables curl; do
        if ! command -v $cmd &> /dev/null; then
            missing+=($cmd)
        fi
    done
    
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing[*]}"
        log_info "Install with: apt install -y iproute2 iptables curl"
        exit 1
    fi
}

# Setup Functions

setup_tun() {
    log_info "Setting up TUN interface..."
    
    # Load TUN module
    modprobe tun 2>/dev/null || true
    
    # Create TUN interface
    ip tuntap add dev $TUN_DEV mode tun 2>/dev/null || {
        log_warn "TUN interface $TUN_DEV already exists"
    }
    
    # Set MTU
    ip link set dev $TUN_DEV mtu 1500
    
    # Bring up interface
    ip link set dev $TUN_DEV up
    
    # Assign IP address
    ip addr add ${TUN_IP}/32 dev $TUN_DEV 2>/dev/null || {
        log_warn "Address ${TUN_IP}/32 already assigned"
    }
    
    # Alternative: point-to-point
    # ip addr add ${TUN_IP} peer ${TUN_PEER} dev $TUN_DEV
    
    log_info "TUN interface $TUN_DEV created with IP ${TUN_IP}"
}

setup_routing() {
    log_info "Setting up routing tables..."
    
    # Create routing table if not exists
    if ! grep -q "$MESH_TABLE" /etc/iproute2/rt_tables 2>/dev/null; then
        echo "${MESH_TABLE_ID} ${MESH_TABLE}" >> /etc/iproute2/rt_tables
        log_info "Created routing table: $MESH_TABLE"
    fi
    
    # Add default route through TUN
    ip route add default dev $TUN_DEV table $MESH_TABLE 2>/dev/null || {
        ip route replace default dev $TUN_DEV table $MESH_TABLE
    }
    
    # Add policy rule for marked packets
    ip rule add fwmark $MARK lookup $MESH_TABLE prio 100 2>/dev/null || {
        ip rule replace fwmark $MARK lookup $MESH_TABLE prio 100
    }
    
    # Enable IP forwarding
    sysctl -w net.ipv4.ip_forward=1 > /dev/null
    
    # Disable reverse path filtering
    sysctl -w net.ipv4.conf.$TUN_DEV.rp_filter=0 > /dev/null
    sysctl -w net.ipv4.conf.all.rp_filter=0 > /dev/null
    
    log_info "Routing configured: table=$MESH_TABLE, mark=$MARK"
}

setup_iptables() {
    log_info "Setting up iptables rules..."
    
    # Create custom chain
    iptables -t mangle -N X0TTA6BL4_MESH 2>/dev/null || {
        iptables -t mangle -F X0TTA6BL4_MESH
    }
    
    # Exclude local traffic
    iptables -t mangle -A X0TTA6BL4_MESH -d 10.0.0.0/8 -j RETURN
    iptables -t mangle -A X0TTA6BL4_MESH -d 172.16.0.0/12 -j RETURN
    iptables -t mangle -A X0TTA6BL4_MESH -d 192.168.0.0/16 -j RETURN
    iptables -t mangle -A X0TTA6BL4_MESH -d 127.0.0.0/8 -j RETURN
    
    # Exclude mesh node itself (VPS IP)
    # iptables -t mangle -A X0TTA6BL4_MESH -d 89.125.1.107 -j RETURN
    
    # Mark remaining packets
    iptables -t mangle -A X0TTA6BL4_MESH -j MARK --set-mark $MARK
    
    # Apply chain to OUTPUT and PREROUTING
    iptables -t mangle -A OUTPUT -j X0TTA6BL4_MESH
    iptables -t mangle -A PREROUTING -j X0TTA6BL4_MESH
    
    # NAT for TUN traffic
    iptables -t nat -A POSTROUTING -o $TUN_DEV -j MASQUERADE
    
    # Allow forwarding
    iptables -A FORWARD -i $TUN_DEV -j ACCEPT
    iptables -A FORWARD -o $TUN_DEV -j ACCEPT
    
    # Redirect TCP to SOCKS5 proxy
    iptables -t nat -A OUTPUT -p tcp -m mark --mark $MARK -j REDIRECT --to-ports $SOCKS_PORT
    
    log_info "iptables rules configured"
}

setup_dns() {
    log_info "Setting up DNS..."
    
    # Redirect DNS queries to local DoH resolver
    iptables -t nat -A OUTPUT -p udp --dport 53 -j REDIRECT --to-ports $DNS_PORT 2>/dev/null || true
    iptables -t nat -A OUTPUT -p tcp --dport 53 -j REDIRECT --to-ports $DNS_PORT 2>/dev/null || true
    
    log_info "DNS redirect configured to port $DNS_PORT"
}

setup_kill_switch() {
    log_info "Setting up kill switch..."
    
    # Block all non-mesh traffic (uncomment to enable)
    # iptables -A OUTPUT ! -o $TUN_DEV -m mark ! --mark $MARK -j DROP
    
    log_info "Kill switch configured (disabled by default)"
}

# Teardown Functions

teardown_iptables() {
    log_info "Removing iptables rules..."
    
    # Remove custom chain
    iptables -t mangle -F X0TTA6BL4_MESH 2>/dev/null || true
    iptables -t mangle -D OUTPUT -j X0TTA6BL4_MESH 2>/dev/null || true
    iptables -t mangle -D PREROUTING -j X0TTA6BL4_MESH 2>/dev/null || true
    iptables -t mangle -X X0TTA6BL4_MESH 2>/dev/null || true
    
    # Remove NAT rules
    iptables -t nat -D POSTROUTING -o $TUN_DEV -j MASQUERADE 2>/dev/null || true
    iptables -t nat -D OUTPUT -p tcp -m mark --mark $MARK -j REDIRECT --to-ports $SOCKS_PORT 2>/dev/null || true
    iptables -t nat -D OUTPUT -p udp --dport 53 -j REDIRECT --to-ports $DNS_PORT 2>/dev/null || true
    iptables -t nat -D OUTPUT -p tcp --dport 53 -j REDIRECT --to-ports $DNS_PORT 2>/dev/null || true
    
    # Remove forwarding rules
    iptables -D FORWARD -i $TUN_DEV -j ACCEPT 2>/dev/null || true
    iptables -D FORWARD -o $TUN_DEV -j ACCEPT 2>/dev/null || true
    
    log_info "iptables rules removed"
}

teardown_routing() {
    log_info "Removing routing rules..."
    
    # Remove policy rule
    ip rule del fwmark $MARK lookup $MESH_TABLE 2>/dev/null || true
    
    # Remove route
    ip route del default dev $TUN_DEV table $MESH_TABLE 2>/dev/null || true
    
    log_info "Routing rules removed"
}

teardown_tun() {
    log_info "Removing TUN interface..."
    
    # Bring down interface
    ip link set $TUN_DEV down 2>/dev/null || true
    
    # Remove IP address
    ip addr del ${TUN_IP}/32 dev $TUN_DEV 2>/dev/null || true
    
    # Delete TUN interface
    ip tuntap del dev $TUN_DEV mode tun 2>/dev/null || true
    
    log_info "TUN interface removed"
}

# Status Functions

show_status() {
    echo "=== x0tta6bl4 Mesh Gateway Status ==="
    echo ""
    
    echo "--- TUN Interface ---"
    ip addr show $TUN_DEV 2>/dev/null || echo "  Not configured"
    echo ""
    
    echo "--- Routing Table ($MESH_TABLE) ---"
    ip route show table $MESH_TABLE 2>/dev/null || echo "  Not configured"
    echo ""
    
    echo "--- Policy Rules ---"
    ip rule list | grep -E "fwmark|$MESH_TABLE" || echo "  No mesh rules"
    echo ""
    
    echo "--- iptables (mangle) ---"
    iptables -t mangle -L X0TTA6BL4_MESH -n -v 2>/dev/null || echo "  Chain not found"
    echo ""
    
    echo "--- iptables (nat) ---"
    iptables -t nat -L OUTPUT -n -v 2>/dev/null | grep -E "REDIRECT|MARK" || echo "  No NAT rules"
    echo ""
    
    echo "--- IP Forwarding ---"
    sysctl net.ipv4.ip_forward
    echo ""
    
    echo "--- Connection Test ---"
    if curl -s --max-time 5 -x socks5://127.0.0.1:$SOCKS_PORT https://ifconfig.me > /dev/null 2>&1; then
        echo "  SOCKS5 proxy: ${GREEN}OK${NC}"
    else
        echo "  SOCKS5 proxy: ${RED}NOT RESPONDING${NC}"
    fi
}

# Main

case "${1:-}" in
    setup)
        check_root
        check_dependencies
        log_info "Setting up x0tta6bl4 Mesh Gateway..."
        setup_tun
        setup_routing
        setup_iptables
        setup_dns
        # setup_kill_switch  # Uncomment to enable
        log_info "Setup complete!"
        echo ""
        echo "Next steps:"
        echo "1. Start SOCKS5 proxy: python3 -m src.network.vpn_proxy --port $SOCKS_PORT"
        echo "2. Start TUN bridge: sudo python3 -m src.network.tun_socks_bridge"
        echo "3. Test: curl https://ifconfig.me"
        ;;
    
    teardown)
        check_root
        log_info "Tearing down x0tta6bl4 Mesh Gateway..."
        teardown_iptables
        teardown_routing
        teardown_tun
        log_info "Teardown complete!"
        ;;
    
    status)
        show_status
        ;;
    
    *)
        echo "Usage: $0 {setup|teardown|status}"
        echo ""
        echo "Commands:"
        echo "  setup     - Configure TUN, routing, and iptables"
        echo "  teardown  - Remove all configuration"
        echo "  status    - Show current status"
        echo ""
        echo "Environment variables:"
        echo "  TUN_DEV     - TUN interface name (default: tun0)"
        echo "  TUN_IP      - TUN local IP (default: 10.0.0.1)"
        echo "  MESH_TABLE  - Routing table name (default: x0tta6bl4_mesh)"
        echo "  SOCKS_PORT  - SOCKS5 proxy port (default: 1080)"
        exit 1
        ;;
esac