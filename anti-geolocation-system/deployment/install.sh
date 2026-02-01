#!/bin/bash
# Anti-Geolocation System Installation Script
# Deploys the complete multi-layered anti-geolocation hardening system

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/anti-geolocation"
CONFIG_DIR="/etc/anti-geolocation"
LOG_FILE="/var/log/anti-geolocation-install.log"

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

check_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        error "Cannot detect OS"
        exit 1
    fi
    
    log "Detected OS: $OS $VER"
}

install_dependencies() {
    log "Installing dependencies..."
    
    if command -v apt-get &>/dev/null; then
        # Debian/Ubuntu
        apt-get update
        apt-get install -y \
            curl wget git \
            iptables ipset \
            wireguard wireguard-tools \
            openvpn \
            macchanger \
            dnsutils \
            net-tools \
            jq \
            python3 python3-pip python3-venv \
            docker.io \
            chrony \
            systemd-resolved
            
    elif command -v dnf &>/dev/null; then
        # Fedora/RHEL
        dnf install -y \
            curl wget git \
            iptables ipset \
            wireguard-tools \
            openvpn \
            macchanger \
            bind-utils \
            net-tools \
            jq \
            python3 python3-pip \
            docker \
            chrony \
            systemd-resolved
            
    elif command -v pacman &>/dev/null; then
        # Arch
        pacman -Sy --noconfirm \
            curl wget git \
            iptables ipset \
            wireguard-tools \
            openvpn \
            macchanger \
            bind \
            net-tools \
            jq \
            python python-pip \
            docker \
            chrony \
            systemd-resolvconf
    else
        error "Unsupported package manager"
        exit 1
    fi
    
    success "Dependencies installed"
}

install_python_packages() {
    log "Installing Python packages..."
    
    pip3 install --upgrade pip
    pip3 install \
        aiohttp \
        pyyaml \
        requests \
        docker
    
    success "Python packages installed"
}

create_directories() {
    log "Creating directories..."
    
    mkdir -p "$INSTALL_DIR"/{network-layer,transport-layer,application-layer,system-hardening,identity-compartmentalization,monitoring,ops-security}
    mkdir -p "$CONFIG_DIR"/{identities,profiles}
    mkdir -p /var/log/anti-geolocation
    mkdir -p /etc/wireguard
    
    success "Directories created"
}

copy_files() {
    log "Copying system files..."
    
    # Network layer
    cp "$SCRIPT_DIR/../network-layer/vpn-chain-manager.py" "$INSTALL_DIR/network-layer/"
    cp "$SCRIPT_DIR/../network-layer/vpn-chain-config.yaml" "$CONFIG_DIR/"
    cp "$SCRIPT_DIR/../network-layer/killswitch.sh" "$INSTALL_DIR/network-layer/"
    chmod +x "$INSTALL_DIR/network-layer/killswitch.sh"
    
    # Transport layer
    cp "$SCRIPT_DIR/../transport-layer/dns-proxy.sh" "$INSTALL_DIR/transport-layer/"
    cp "$SCRIPT_DIR/../transport-layer/traffic-shaper.sh" "$INSTALL_DIR/transport-layer/"
    chmod +x "$INSTALL_DIR/transport-layer/"*.sh
    
    # Application layer
    cp "$SCRIPT_DIR/../application-layer/firefox-hardening.js" "$INSTALL_DIR/application-layer/"
    cp "$SCRIPT_DIR/../application-layer/chrome-hardening.sh" "$INSTALL_DIR/application-layer/"
    chmod +x "$INSTALL_DIR/application-layer/chrome-hardening.sh"
    
    # System hardening
    cp "$SCRIPT_DIR/../system-hardening/linux-hardening.sh" "$INSTALL_DIR/system-hardening/"
    chmod +x "$INSTALL_DIR/system-hardening/linux-hardening.sh"
    
    # Identity compartmentalization
    cp "$SCRIPT_DIR/../identity-compartmentalization/container-manager.py" "$INSTALL_DIR/identity-compartmentalization/"
    chmod +x "$INSTALL_DIR/identity-compartmentalization/container-manager.py"
    
    # Monitoring
    cp "$SCRIPT_DIR/../monitoring/leak-detector.py" "$INSTALL_DIR/monitoring/"
    chmod +x "$INSTALL_DIR/monitoring/leak-detector.py"
    
    # Create symlinks
    ln -sf "$INSTALL_DIR/network-layer/killswitch.sh" /usr/local/bin/killswitch
    ln -sf "$INSTALL_DIR/transport-layer/dns-proxy.sh" /usr/local/bin/dns-proxy
    ln -sf "$INSTALL_DIR/transport-layer/traffic-shaper.sh" /usr/local/bin/traffic-shaper
    ln -sf "$INSTALL_DIR/system-hardening/linux-hardening.sh" /usr/local/bin/system-harden
    ln -sf "$INSTALL_DIR/identity-compartmentalization/container-manager.py" /usr/local/bin/identity-manager
    ln -sf "$INSTALL_DIR/monitoring/leak-detector.py" /usr/local/bin/leak-detector
    
    success "Files copied and linked"
}

create_systemd_services() {
    log "Creating systemd services..."
    
    # VPN Chain Manager Service
    cat > /etc/systemd/system/vpn-chain.service << EOF
[Unit]
Description=VPN Chain Manager
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/network-layer/vpn-chain-manager.py $CONFIG_DIR/vpn-chain-config.yaml connect
ExecStop=/usr/bin/python3 $INSTALL_DIR/network-layer/vpn-chain-manager.py $CONFIG_DIR/vpn-chain-config.yaml disconnect
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

    # Leak Detector Service
    cat > /etc/systemd/system/leak-detector.service << EOF
[Unit]
Description=Geolocation Leak Detector
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/monitoring/leak-detector.py start
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF

    # MAC Rotation Timer (already created by linux-hardening.sh)
    
    # Reload systemd
    systemctl daemon-reload
    
    success "Systemd services created"
}

configure_firewall() {
    log "Configuring firewall..."
    
    # Flush existing rules
    iptables -F
    iptables -X
    iptables -t nat -F
    iptables -t nat -X
    
    # Default policies
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT ACCEPT
    
    # Allow loopback
    iptables -A INPUT -i lo -j ACCEPT
    iptables -A OUTPUT -o lo -j ACCEPT
    
    # Allow established connections
    iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    
    # Allow SSH (be careful!)
    iptables -A INPUT -p tcp --dport 22 -j ACCEPT
    
    # Allow VPN ports
    iptables -A INPUT -p udp --dport 51820 -j ACCEPT  # WireGuard
    iptables -A INPUT -p udp --dport 1194 -j ACCEPT   # OpenVPN
    
    # Allow DNS
    iptables -A INPUT -p udp --dport 53 -j ACCEPT
    iptables -A INPUT -p tcp --dport 53 -j ACCEPT
    
    # Save rules
    if command -v netfilter-persistent &>/dev/null; then
        netfilter-persistent save
    else
        mkdir -p /etc/iptables
        iptables-save > /etc/iptables/rules.v4
    fi
    
    success "Firewall configured"
}

setup_leak_detector_config() {
    log "Setting up leak detector configuration..."
    
    cat > "$CONFIG_DIR/leak-detector.yaml" << 'EOF'
# Leak Detector Configuration

# Expected VPN exit IPs (populate after connecting to VPN)
expected_exit_ips: []

# Expected DNS servers
expected_dns_servers:
  - "127.0.0.1"
  - "::1"
  - "1.1.1.1"
  - "1.0.0.1"

# Check interval in seconds
check_interval: 60

# Alert configuration
alert:
  email_enabled: false
  email_smtp_host: "smtp.gmail.com"
  email_smtp_port: 587
  email_username: ""
  email_password: ""
  email_recipients: []
  
  webhook_enabled: false
  webhook_url: ""
  webhook_headers: {}
  
  telegram_enabled: false
  telegram_bot_token: ""
  telegram_chat_id: ""
  
  alert_on_info: false
  alert_on_warning: true
  alert_on_critical: true
EOF

    success "Leak detector configuration created"
}

run_initial_setup() {
    log "Running initial system hardening..."
    
    # Run system hardening
    "$INSTALL_DIR/system-hardening/linux-hardening.sh" apply || warning "System hardening had issues"
    
    # Setup DNS proxy
    "$INSTALL_DIR/transport-layer/dns-proxy.sh" setup || warning "DNS proxy setup had issues"
    
    success "Initial setup complete"
}

verify_installation() {
    log "Verifying installation..."
    
    local errors=0
    
    # Check files exist
    for file in \
        "$INSTALL_DIR/network-layer/vpn-chain-manager.py" \
        "$INSTALL_DIR/network-layer/killswitch.sh" \
        "$INSTALL_DIR/transport-layer/dns-proxy.sh" \
        "$INSTALL_DIR/system-hardening/linux-hardening.sh" \
        "$INSTALL_DIR/monitoring/leak-detector.py"
    do
        if [[ -f "$file" ]]; then
            success "Found: $file"
        else
            error "Missing: $file"
            ((errors++))
        fi
    done
    
    # Check symlinks
    for link in killswitch dns-proxy traffic-shaper system-harden identity-manager leak-detector; do
        if [[ -L "/usr/local/bin/$link" ]]; then
            success "Symlink: $link"
        else
            error "Missing symlink: $link"
            ((errors++))
        fi
    done
    
    # Check services
    if [[ -f /etc/systemd/system/vpn-chain.service ]]; then
        success "Service: vpn-chain"
    else
        error "Missing service: vpn-chain"
        ((errors++))
    fi
    
    if [[ -f /etc/systemd/system/leak-detector.service ]]; then
        success "Service: leak-detector"
    else
        error "Missing service: leak-detector"
        ((errors++))
    fi
    
    if [[ $errors -eq 0 ]]; then
        success "Installation verification passed!"
        return 0
    else
        error "Installation verification failed with $errors errors"
        return 1
    fi
}

print_usage() {
    cat << 'EOF'

╔══════════════════════════════════════════════════════════════════╗
║     Anti-Geolocation System Installation Complete               ║
╚══════════════════════════════════════════════════════════════════╝

USAGE:

1. NETWORK LAYER:
   - Configure VPN endpoints in: /etc/anti-geolocation/vpn-chain-config.yaml
   - Start VPN chain: systemctl start vpn-chain
   - Enable killswitch: killswitch enable
   - Check status: killswitch status

2. TRANSPORT LAYER:
   - DNS proxy status: dns-proxy status
   - Traffic shaping: traffic-shaper full

3. APPLICATION LAYER:
   - Firefox: Copy firefox-hardening.js to your profile
   - Chrome: Run chrome-hardening.sh

4. SYSTEM HARDENING:
   - Check status: system-harden status
   - Rotate MAC: system-harden mac [interface]

5. IDENTITY MANAGEMENT:
   - Create profile: identity-manager create "Profile Name"
   - List profiles: identity-manager list
   - Activate: identity-manager activate <id>

6. MONITORING:
   - Start monitoring: systemctl start leak-detector
   - Check status: leak-detector status
   - Run check: leak-detector check

VERIFICATION:
   - IP leak: https://ipleak.net
   - DNS leak: https://dnsleaktest.com
   - WebRTC: https://browserleaks.com/webrtc
   - Fingerprint: https://coveryourtracks.eff.org

IMPORTANT:
   - Review and customize /etc/anti-geolocation/leak-detector.yaml
   - Add your VPN credentials before starting vpn-chain
   - Test thoroughly before relying on this system

EOF
}

main() {
    log "Starting Anti-Geolocation System Installation"
    
    check_root
    check_os
    install_dependencies
    install_python_packages
    create_directories
    copy_files
    create_systemd_services
    configure_firewall
    setup_leak_detector_config
    run_initial_setup
    verify_installation
    
    success "Installation complete!"
    print_usage
}

# Handle command line arguments
case "${1:-install}" in
    install)
        main
        ;;
    verify)
        verify_installation
        ;;
    uninstall)
        warning "Uninstalling Anti-Geolocation System..."
        systemctl stop vpn-chain leak-detector 2>/dev/null || true
        systemctl disable vpn-chain leak-detector 2>/dev/null || true
        rm -rf "$INSTALL_DIR" "$CONFIG_DIR"
        rm -f /usr/local/bin/{killswitch,dns-proxy,traffic-shaper,system-harden,identity-manager,leak-detector}
        rm -f /etc/systemd/system/{vpn-chain,leak-detector}.service
        systemctl daemon-reload
        success "Uninstalled"
        ;;
    *)
        echo "Usage: $0 {install|verify|uninstall}"
        exit 1
        ;;
esac
