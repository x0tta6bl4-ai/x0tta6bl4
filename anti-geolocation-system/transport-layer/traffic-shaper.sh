#!/bin/bash
# Traffic Shaping and Timing Obfuscation
# Implements traffic shaping to prevent timing analysis attacks

set -euo pipefail

LOG_FILE="/var/log/traffic-shaper.log"
TC_CONFIG="/etc/traffic-shaper.conf"

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

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
        exit 1
    fi
}

# Get VPN interface
get_vpn_interface() {
    ip link show | grep -oE "tun-[^:]+|tun[0-9]+|wg[0-9]+" | head -n1
}

# Get default interface
get_default_interface() {
    ip route | grep default | awk '{print $5}' | head -n1
}

# Apply traffic shaping rules
apply_shaping() {
    local iface="${1:-$(get_vpn_interface)}"
    
    if [[ -z "$iface" ]]; then
        error "No interface specified and no VPN interface found"
        exit 1
    fi
    
    log "Applying traffic shaping to interface: $iface"
    
    # Remove existing qdiscs
    tc qdisc del dev "$iface" root 2>/dev/null || true
    tc qdisc del dev "$iface" ingress 2>/dev/null || true
    
    # HTB (Hierarchical Token Bucket) for bandwidth control
    # Add root qdisc
    tc qdisc add dev "$iface" root handle 1: htb default 12
    
    # Root class
    tc class add dev "$iface" parent 1: classid 1:1 htb rate 100mbit burst 15k
    
    # Interactive traffic (SSH, DNS) - high priority
    tc class add dev "$iface" parent 1:1 classid 1:10 htb rate 5mbit ceil 50mbit
    tc qdisc add dev "$iface" parent 1:10 handle 10: sfq perturb 10
    tc filter add dev "$iface" protocol ip parent 1:0 prio 1 u32 \
        match ip dport 22 0xffff flowid 1:10
    tc filter add dev "$iface" protocol ip parent 1:0 prio 1 u32 \
        match ip sport 22 0xffff flowid 1:10
    tc filter add dev "$iface" protocol ip parent 1:0 prio 1 u32 \
        match ip dport 53 0xffff flowid 1:10
    tc filter add dev "$iface" protocol ip parent 1:0 prio 1 u32 \
        match ip sport 53 0xffff flowid 1:10
    
    # HTTPS traffic - normal priority with padding
    tc class add dev "$iface" parent 1:1 classid 1:11 htb rate 20mbit ceil 80mbit
    tc qdisc add dev "$iface" parent 1:11 handle 11: netem delay 10ms 5ms distribution normal
    tc filter add dev "$iface" protocol ip parent 1:0 prio 2 u32 \
        match ip dport 443 0xffff flowid 1:11
    tc filter add dev "$iface" protocol ip parent 1:0 prio 2 u32 \
        match ip sport 443 0xffff flowid 1:11
    
    # Default traffic - low priority with jitter
    tc class add dev "$iface" parent 1:1 classid 1:12 htb rate 10mbit ceil 50mbit
    tc qdisc add dev "$iface" parent 1:12 handle 12: netem \
        delay 20ms 10ms 25% distribution pareto \
        loss 0.1% 25% \
        corrupt 0.01%
    
    # Ingress shaping (for incoming traffic)
    tc qdisc add dev "$iface" handle ffff: ingress
    tc filter add dev "$iface" parent ffff: protocol ip u32 match u32 0 0 \
        police rate 50mbit burst 10k drop flowid :1
    
    success "Traffic shaping applied to $iface"
}

# Add timing obfuscation with random delays
add_timing_obfuscation() {
    local iface="${1:-$(get_vpn_interface)}"
    
    log "Adding timing obfuscation to $iface"
    
    # Add netem qdisc for timing obfuscation
    # This adds random delays to make traffic analysis harder
    tc qdisc change dev "$iface" parent 1:12 handle 12: netem \
        delay 30ms 15ms distribution normal \
        reorder 5% 10% \
        gap 5
    
    success "Timing obfuscation enabled"
}

# Create cover traffic generator
create_cover_traffic() {
    log "Setting up cover traffic generator..."
    
    cat > /usr/local/bin/cover-traffic.sh << 'EOF'
#!/bin/bash
# Cover traffic generator - generates background noise

INTERVAL_MIN=30
INTERVAL_MAX=120
TARGETS=(
    "https://www.google.com"
    "https://www.cloudflare.com"
    "https://www.wikipedia.org"
    "https://www.github.com"
    "https://www.reddit.com"
)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> /var/log/cover-traffic.log
}

while true; do
    # Random interval
    interval=$((RANDOM % (INTERVAL_MAX - INTERVAL_MIN + 1) + INTERVAL_MIN))
    
    # Random target
    target=${TARGETS[$RANDOM % ${#TARGETS[@]}]}
    
    # Random user agent
    user_agents=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    )
    ua="${user_agents[$RANDOM % ${#user_agents[@]}]}"
    
    log "Fetching $target (next in ${interval}s)"
    
    # Fetch with random timeout
    curl -s -A "$ua" --max-time 10 "$target" > /dev/null 2>&1 || true
    
    sleep "$interval"
done
EOF
    
    chmod +x /usr/local/bin/cover-traffic.sh
    
    # Create systemd service
    cat > /etc/systemd/system/cover-traffic.service << 'EOF'
[Unit]
Description=Cover Traffic Generator
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cover-traffic.sh
Restart=always
RestartSec=10
User=nobody
Group=nogroup

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable cover-traffic.service
    
    success "Cover traffic generator created"
}

# Start cover traffic
start_cover_traffic() {
    log "Starting cover traffic generator..."
    systemctl start cover-traffic.service
    success "Cover traffic started"
}

# Stop cover traffic
stop_cover_traffic() {
    log "Stopping cover traffic generator..."
    systemctl stop cover-traffic.service
    success "Cover traffic stopped"
}

# Pad packets to uniform size
enable_packet_padding() {
    local iface="${1:-$(get_vpn_interface)}"
    
    log "Enabling packet padding on $iface"
    
    # Use iptables to pad packets (via TEE target or custom module)
    # This is a simplified version - real implementation would use eBPF
    
    # Add mark for packets to be padded
    iptables -t mangle -A OUTPUT -o "$iface" -p tcp --dport 443 -j MARK --set-mark 0x1
    iptables -t mangle -A OUTPUT -o "$iface" -p tcp --sport 443 -j MARK --set-mark 0x1
    
    success "Packet padding rules added (mark 0x1)"
    warning "Note: Full packet padding requires eBPF or kernel module"
}

# Remove all shaping
remove_shaping() {
    local iface="${1:-$(get_vpn_interface)}"
    
    if [[ -z "$iface" ]]; then
        error "No interface specified"
        exit 1
    fi
    
    log "Removing traffic shaping from $iface"
    
    tc qdisc del dev "$iface" root 2>/dev/null || true
    tc qdisc del dev "$iface" ingress 2>/dev/null || true
    
    success "Traffic shaping removed from $iface"
}

# Show current shaping status
status() {
    local iface="${1:-$(get_vpn_interface)}"
    
    if [[ -z "$iface" ]]; then
        # Show all interfaces
        echo "=== Traffic Shaping Status ==="
        for i in $(ls /sys/class/net/); do
            echo ""
            echo "--- Interface: $i ---"
            tc qdisc show dev "$i" 2>/dev/null || echo "No shaping"
            tc class show dev "$i" 2>/dev/null || true
            tc filter show dev "$i" 2>/dev/null || true
        done
    else
        echo "=== Traffic Shaping Status for $iface ==="
        echo ""
        echo "--- QDiscs ---"
        tc qdisc show dev "$iface"
        echo ""
        echo "--- Classes ---"
        tc class show dev "$iface"
        echo ""
        echo "--- Filters ---"
        tc filter show dev "$iface"
    fi
    
    echo ""
    echo "=== Cover Traffic Status ==="
    if systemctl is-active --quiet cover-traffic.service 2>/dev/null; then
        success "Cover traffic: RUNNING"
    else
        warning "Cover traffic: NOT RUNNING"
    fi
}

# Save configuration
save_config() {
    local iface="${1:-$(get_vpn_interface)}"
    
    cat > "$TC_CONFIG" << EOF
# Traffic Shaper Configuration
INTERFACE=$iface
SHAPING_ENABLED=true
TIMING_OBFUSCATION=true
COVER_TRAFFIC=true
PACKET_PADDING=true
EOF
    
    success "Configuration saved to $TC_CONFIG"
}

# Load and apply saved configuration
load_config() {
    if [[ -f "$TC_CONFIG" ]]; then
        source "$TC_CONFIG"
        log "Loaded configuration from $TC_CONFIG"
        
        if [[ "${SHAPING_ENABLED:-false}" == "true" ]]; then
            apply_shaping "${INTERFACE:-}"
        fi
        
        if [[ "${TIMING_OBFUSCATION:-false}" == "true" ]]; then
            add_timing_obfuscation "${INTERFACE:-}"
        fi
        
        if [[ "${COVER_TRAFFIC:-false}" == "true" ]]; then
            create_cover_traffic
            start_cover_traffic
        fi
        
        if [[ "${PACKET_PADDING:-false}" == "true" ]]; then
            enable_packet_padding "${INTERFACE:-}"
        fi
    else
        warning "No configuration file found at $TC_CONFIG"
    fi
}

# Main function
main() {
    check_root
    
    case "${1:-}" in
        apply|start)
            apply_shaping "${2:-}"
            ;;
        remove|stop)
            remove_shaping "${2:-}"
            ;;
        timing)
            add_timing_obfuscation "${2:-}"
            ;;
        cover)
            create_cover_traffic
            start_cover_traffic
            ;;
        padding)
            enable_packet_padding "${2:-}"
            ;;
        status)
            status "${2:-}"
            ;;
        save)
            save_config "${2:-}"
            ;;
        load)
            load_config
            ;;
        full)
            # Apply full protection
            local iface="${2:-$(get_vpn_interface)}"
            apply_shaping "$iface"
            add_timing_obfuscation "$iface"
            create_cover_traffic
            start_cover_traffic
            enable_packet_padding "$iface"
            save_config "$iface"
            success "Full traffic shaping protection enabled"
            ;;
        *)
            echo "Traffic Shaping and Timing Obfuscation"
            echo ""
            echo "Usage: $0 {apply|remove|timing|cover|padding|status|save|load|full} [interface]"
            echo ""
            echo "Commands:"
            echo "  apply [iface]   - Apply traffic shaping to interface"
            echo "  remove [iface]  - Remove traffic shaping"
            echo "  timing [iface]  - Add timing obfuscation"
            echo "  cover           - Enable cover traffic generator"
            echo "  padding [iface] - Enable packet padding"
            echo "  status [iface]  - Show current status"
            echo "  save [iface]    - Save current configuration"
            echo "  load            - Load and apply saved configuration"
            echo "  full [iface]    - Apply all protections"
            echo ""
            echo "If no interface is specified, the VPN interface will be auto-detected."
            exit 1
            ;;
    esac
}

main "$@"
