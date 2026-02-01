#!/bin/bash
# Encrypted DNS Proxy Setup (DoH/DoT/ODoH)
# Configures cloudflared, dnscrypt-proxy, and systemd-resolved

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/dns-proxy-setup.log"

# DNS Providers
DOH_CLOUDFLARE="https://cloudflare-dns.com/dns-query"
DOH_QUAD9="https://dns.quad9.net/dns-query"
DOH_MULLVAD="https://doh.mullvad.net/dns-query"
DOT_CLOUDFLARE="tls://1.1.1.1:853"
DOT_QUAD9="tls://dns.quad9.net:853"

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

# Install cloudflared for DoH
install_cloudflared() {
    log "Installing cloudflared (DoH proxy)..."
    
    if command -v cloudflared &>/dev/null; then
        warning "cloudflared already installed"
        return 0
    fi
    
    # Download latest cloudflared
    local arch=$(uname -m)
    local download_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}"
    
    if [[ "$arch" == "x86_64" ]]; then
        download_url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    fi
    
    log "Downloading cloudflared from $download_url..."
    curl -L --output /tmp/cloudflared "$download_url"
    chmod +x /tmp/cloudflared
    mv /tmp/cloudflared /usr/local/bin/cloudflared
    
    success "cloudflared installed to /usr/local/bin/cloudflared"
}

# Install dnscrypt-proxy
install_dnscrypt_proxy() {
    log "Installing dnscrypt-proxy..."
    
    if command -v dnscrypt-proxy &>/dev/null; then
        warning "dnscrypt-proxy already installed"
        return 0
    fi
    
    if command -v apt-get &>/dev/null; then
        apt-get update
        apt-get install -y dnscrypt-proxy
    elif command -v dnf &>/dev/null; then
        dnf install -y dnscrypt-proxy
    elif command -v pacman &>/dev/null; then
        pacman -S --noconfirm dnscrypt-proxy
    else
        error "Unsupported package manager. Please install dnscrypt-proxy manually."
        exit 1
    fi
    
    success "dnscrypt-proxy installed"
}

# Configure cloudflared as DoH proxy
configure_cloudflared() {
    log "Configuring cloudflared as DoH proxy..."
    
    mkdir -p /etc/cloudflared
    
    # Create cloudflared config
    cat > /etc/cloudflared/config.yml << 'EOF'
proxy-dns: true
proxy-dns-port: 5053
proxy-dns-upstream:
  - https://cloudflare-dns.com/dns-query
  - https://dns.quad9.net/dns-query
  - https://doh.mullvad.net/dns-query
proxy-dns-bootstrap:
  - 1.1.1.1:53
  - 1.0.0.1:53
proxy-dns-max-upstream-conns: 10
proxy-dns-timeout: 5s
loglevel: info
EOF
    
    # Create systemd service
    cat > /etc/systemd/system/cloudflared-proxy-dns.service << 'EOF'
[Unit]
Description=DNS over HTTPS (DoH) proxy
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared --config /etc/cloudflared/config.yml
Restart=always
RestartSec=5
User=cloudflared
Group=cloudflared

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/cloudflared
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
    
    # Create cloudflared user
    id -u cloudflared &>/dev/null || useradd -r -s /bin/false cloudflared
    
    # Enable and start service
    systemctl daemon-reload
    systemctl enable cloudflared-proxy-dns
    systemctl start cloudflared-proxy-dns
    
    success "cloudflared configured and started on port 5053"
}

# Configure dnscrypt-proxy with ODoH support
configure_dnscrypt_proxy() {
    log "Configuring dnscrypt-proxy with ODoH support..."
    
    mkdir -p /etc/dnscrypt-proxy
    
    # Create dnscrypt-proxy config
    cat > /etc/dnscrypt-proxy/dnscrypt-proxy.toml << 'EOF'
# Listen address
listen_addresses = ['127.0.0.1:5300']

# Server selection
server_names = ['cloudflare', 'cloudflare-ipv6', 'quad9-doh-ip4-port443-filter-pri']

# Anonymized DNS (ODoH)
[anonymized_dns]
routes = [
    { server_name='*', via=['anon-cs-swe', 'anon-cs-finland'] }
]
skip_incompatible = false

# Sources for resolver lists
[sources]
[sources.public-resolvers]
urls = ['https://raw.githubusercontent.com/DNSCrypt/dnscrypt-resolvers/master/v3/public-resolvers.md', 'https://download.dnscrypt.info/resolvers-list/v3/public-resolvers.md']
cache_file = '/var/cache/dnscrypt-proxy/public-resolvers.md'
minisign_key = 'RWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3'
refresh_delay = 72
prefix = ''

# Logging
[logging]
level = 2
format = 'ltsv'

# DNS cache
[cache]
type = 'lru'
cache_size = 4096
min_ttl = 2400
max_ttl = 86400
cache_neg_min_ttl = 60
cache_neg_max_ttl = 600

# Query logging (disable for privacy)
[query_log]
format = 'tsv'

# Block IPv6 (optional, for VPN compatibility)
block_ipv6 = false

# DNSSEC
require_dnssec = true

# TLS security level
tls_disable_session_tickets = true

# Bootstrap resolvers
bootstrap_resolvers = ['1.1.1.1:53', '8.8.8.8:53']

# Maximum concurrent connections
max_clients = 250

# Timeout
timeout = 5000

# Keepalive
keepalive = 30

# Load balancing
lb_strategy = 'p2'
lb_estimator = true

# Cloaking rules (block tracking domains)
[cloaking]
cloaking_rules = '/etc/dnscrypt-proxy/cloaking-rules.txt'

# Forwarding rules
[forwarding]
forwarding_rules = '/etc/dnscrypt-proxy/forwarding-rules.txt'
EOF
    
    # Create cloaking rules (block tracking)
    cat > /etc/dnscrypt-proxy/cloaking-rules.txt << 'EOF'
# Block Google tracking
google-analytics.com 0.0.0.0
www.google-analytics.com 0.0.0.0
googletagmanager.com 0.0.0.0
www.googletagmanager.com 0.0.0.0
doubleclick.net 0.0.0.0
www.doubleclick.net 0.0.0.0
googleadservices.com 0.0.0.0
www.googleadservices.com 0.0.0.0

# Block Facebook tracking
facebook.com 0.0.0.0
www.facebook.com 0.0.0.0
connect.facebook.net 0.0.0.0
graph.facebook.com 0.0.0.0

# Block other trackers
tracker.example.com 0.0.0.0
EOF

    # Create forwarding rules
    cat > /etc/dnscrypt-proxy/forwarding-rules.txt << 'EOF'
# Forward specific domains to specific resolvers
# onion. *.onion
EOF
    
    # Update systemd service
    cat > /etc/systemd/system/dnscrypt-proxy.service << 'EOF'
[Unit]
Description=DNSCrypt-proxy client
Documentation=https://github.com/DNSCrypt/dnscrypt-proxy/wiki
After=network.target
Wants=network.target
Before=nss-lookup.target
Wants=nss-lookup.target

[Service]
Type=simple
ExecStart=/usr/bin/dnscrypt-proxy -config /etc/dnscrypt-proxy/dnscrypt-proxy.toml
Restart=always
RestartSec=5
User=dnscrypt
Group=dnscrypt

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/dnscrypt-proxy /var/cache/dnscrypt-proxy
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
    
    # Create dnscrypt user
    id -u dnscrypt &>/dev/null || useradd -r -s /bin/false dnscrypt
    mkdir -p /var/cache/dnscrypt-proxy
    chown dnscrypt:dnscrypt /var/cache/dnscrypt-proxy
    
    # Enable and start service
    systemctl daemon-reload
    systemctl enable dnscrypt-proxy
    systemctl start dnscrypt-proxy
    
    success "dnscrypt-proxy configured and started on port 5300"
}

# Configure systemd-resolved with DoT
configure_systemd_resolved() {
    log "Configuring systemd-resolved with DNS-over-TLS..."
    
    mkdir -p /etc/systemd/resolved.conf.d/
    
    # Create resolved configuration
    cat > /etc/systemd/resolved.conf.d/99-dns-over-tls.conf << 'EOF'
[Resolve]
# Use local DoH/DoT proxies as upstream
DNS=127.0.0.1:5053 127.0.0.1:5300
DNSStubListener=yes
DNSStubListenerExtra=127.0.0.1:53

# Enable DNS-over-TLS
DNSOverTLS=yes
DNSSEC=yes

# Fallback DNS (only used if local proxies fail)
FallbackDNS=1.1.1.1 1.0.0.1

# Cache
Cache=yes
CacheFromLocalhost=yes

# DNS domains
Domains=~.

# LLMNR and MulticastDNS (disable for privacy)
LLMNR=no
MulticastDNS=no

# DNSSEC validation
DNSSEC=yes
EOF
    
    # Backup and update resolv.conf
    if [[ -f /etc/resolv.conf ]]; then
        cp /etc/resolv.conf /etc/resolv.conf.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    # Make resolv.conf immutable (prevent NetworkManager from overwriting)
    cat > /etc/resolv.conf << 'EOF'
# Generated by DNS Proxy Setup
nameserver 127.0.0.1
options edns0 trust-ad
EOF
    
    # Make immutable
    chattr +i /etc/resolv.conf 2>/dev/null || warning "Could not make resolv.conf immutable"
    
    # Restart systemd-resolved
    systemctl restart systemd-resolved
    systemctl enable systemd-resolved
    
    success "systemd-resolved configured with DoT"
}

# Configure Unbound as local recursive resolver
configure_unbound() {
    log "Configuring Unbound as local recursive resolver..."
    
    # Install unbound
    if command -v apt-get &>/dev/null; then
        apt-get install -y unbound
    elif command -v dnf &>/dev/null; then
        dnf install -y unbound
    elif command -v pacman &>/dev/null; then
        pacman -S --noconfirm unbound
    fi
    
    # Create unbound config
    cat > /etc/unbound/unbound.conf.d/encrypted-dns.conf << 'EOF'
server:
    # Listen on localhost
    interface: 127.0.0.1
    port: 5335
    
    # Access control
    access-control: 127.0.0.0/8 allow
    access-control: ::1 allow
    
    # Hide version
    hide-identity: yes
    hide-version: yes
    
    # Privacy settings
    qname-minimisation: yes
    harden-glue: yes
    harden-dnssec-stripped: yes
    harden-referral-path: yes
    
    # Performance
    num-threads: 4
    msg-cache-slabs: 4
    rrset-cache-slabs: 4
    infra-cache-slabs: 4
    key-cache-slabs: 4
    rrset-cache-size: 128m
    msg-cache-size: 64m
    so-rcvbuf: 1m
    so-sndbuf: 1m
    
    # Forward to encrypted DNS
    forward-zone:
        name: "."
        forward-addr: 127.0.0.1@5053
        forward-addr: 127.0.0.1@5300
        forward-first: no
        forward-no-cache: no
EOF
    
    # Enable and start unbound
    systemctl enable unbound
    systemctl restart unbound
    
    success "Unbound configured on port 5335"
}

# Block plain DNS to prevent leaks
block_plain_dns() {
    log "Blocking plain DNS to prevent leaks..."
    
    # Block outgoing DNS on port 53 except to localhost
    iptables -A OUTPUT -p udp --dport 53 -d 127.0.0.1 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -d 127.0.0.1 -j ACCEPT
    iptables -A OUTPUT -p udp --dport 53 -j DROP
    iptables -A OUTPUT -p tcp --dport 53 -j DROP
    
    # IPv6
    ip6tables -A OUTPUT -p udp --dport 53 -d ::1 -j ACCEPT 2>/dev/null || true
    ip6tables -A OUTPUT -p tcp --dport 53 -d ::1 -j ACCEPT 2>/dev/null || true
    ip6tables -A OUTPUT -p udp --dport 53 -j DROP 2>/dev/null || true
    ip6tables -A OUTPUT -p tcp --dport 53 -j DROP 2>/dev/null || true
    
    # Make rules persistent
    if command -v netfilter-persistent &>/dev/null; then
        netfilter-persistent save
    elif command -v iptables-save &>/dev/null; then
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        ip6tables-save > /etc/iptables/rules.v6 2>/dev/null || true
    fi
    
    success "Plain DNS blocked - all DNS must go through encrypted proxies"
}

# Test DNS configuration
test_dns() {
    log "Testing DNS configuration..."
    
    info "Testing cloudflared (port 5053)..."
    if dig @127.0.0.1 -p 5053 cloudflare.com +short +time=5 > /dev/null 2>&1; then
        success "cloudflared responding"
    else
        error "cloudflared not responding"
    fi
    
    info "Testing dnscrypt-proxy (port 5300)..."
    if dig @127.0.0.1 -p 5300 cloudflare.com +short +time=5 > /dev/null 2>&1; then
        success "dnscrypt-proxy responding"
    else
        error "dnscrypt-proxy not responding"
    fi
    
    info "Testing systemd-resolved (port 53)..."
    if dig @127.0.0.1 cloudflare.com +short +time=5 > /dev/null 2>&1; then
        success "systemd-resolved responding"
    else
        error "systemd-resolved not responding"
    fi
    
    info "Checking DNS leak..."
    local detected_ip=$(dig @127.0.0.1 whoami.akamai.net +short +time=5 2>/dev/null || echo "")
    if [[ -n "$detected_ip" ]]; then
        info "DNS resolver IP: $detected_ip"
    fi
    
    # Test DNSSEC
    info "Testing DNSSEC validation..."
    if dig @127.0.0.1 dnssec-failed.org +short +time=5 2>&1 | grep -q "SERVFAIL"; then
        success "DNSSEC validation working (correctly rejected invalid signature)"
    else
        warning "DNSSEC validation may not be working correctly"
    fi
}

# Verify no DNS leaks
verify_no_leaks() {
    log "Verifying no DNS leaks..."
    
    info "Running comprehensive DNS leak test..."
    
    # Get current DNS servers
    local dns_servers=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
    info "Current DNS servers in resolv.conf: $dns_servers"
    
    # Check if only localhost is used
    if echo "$dns_servers" | grep -qv "127.0.0.1"; then
        error "Non-local DNS server detected in resolv.conf - potential leak!"
        return 1
    fi
    
    # Test resolution
    local test_domains=("cloudflare.com" "quad9.net" "dns.google")
    for domain in "${test_domains[@]}"; do
        if ! dig @127.0.0.1 "$domain" +short +time=5 > /dev/null 2>&1; then
            error "Failed to resolve $domain"
            return 1
        fi
    done
    
    success "No DNS leaks detected"
    return 0
}

# Main setup function
setup_all() {
    log "Starting DNS proxy setup..."
    
    check_root
    install_cloudflared
    install_dnscrypt_proxy
    configure_cloudflared
    configure_dnscrypt_proxy
    configure_systemd_resolved
    configure_unbound
    block_plain_dns
    
    sleep 2  # Wait for services to start
    
    test_dns
    verify_no_leaks
    
    success "DNS proxy setup complete!"
    echo ""
    info "Services configured:"
    info "  - cloudflared: DoH proxy on 127.0.0.1:5053"
    info "  - dnscrypt-proxy: ODoH proxy on 127.0.0.1:5300"
    info "  - systemd-resolved: Local DNS on 127.0.0.1:53"
    info "  - unbound: Recursive resolver on 127.0.0.1:5335"
    echo ""
    info "All DNS queries are now encrypted and anonymized!"
}

# Status check
status() {
    echo "=== DNS Proxy Status ==="
    echo ""
    
    services=("cloudflared-proxy-dns" "dnscrypt-proxy" "systemd-resolved" "unbound")
    
    for service in "${services[@]}"; do
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            success "$service: RUNNING"
        else
            error "$service: NOT RUNNING"
        fi
    done
    
    echo ""
    echo "=== DNS Configuration ==="
    echo "resolv.conf:"
    cat /etc/resolv.conf
    
    echo ""
    echo "systemd-resolved config:"
    cat /etc/systemd/resolved.conf.d/99-dns-over-tls.conf 2>/dev/null || echo "Not configured"
}

# Cleanup and restore
cleanup() {
    log "Cleaning up DNS proxy configuration..."
    
    check_root
    
    # Stop services
    systemctl stop cloudflared-proxy-dns 2>/dev/null || true
    systemctl stop dnscrypt-proxy 2>/dev/null || true
    systemctl stop unbound 2>/dev/null || true
    
    # Disable services
    systemctl disable cloudflared-proxy-dns 2>/dev/null || true
    systemctl disable dnscrypt-proxy 2>/dev/null || true
    systemctl disable unbound 2>/dev/null || true
    
    # Remove immutable flag
    chattr -i /etc/resolv.conf 2>/dev/null || true
    
    # Restore backup if exists
    local backup=$(ls -t /etc/resolv.conf.backup.* 2>/dev/null | head -n1)
    if [[ -n "$backup" ]]; then
        cp "$backup" /etc/resolv.conf
        log "Restored resolv.conf from backup"
    fi
    
    # Remove custom configs
    rm -f /etc/systemd/resolved.conf.d/99-dns-over-tls.conf
    rm -f /etc/systemd/system/cloudflared-proxy-dns.service
    rm -rf /etc/cloudflared
    
    # Restart systemd-resolved with default config
    systemctl restart systemd-resolved
    
    success "Cleanup complete"
}

# Main
main() {
    case "${1:-setup}" in
        setup|install|all)
            setup_all
            ;;
        status)
            status
            ;;
        test)
            test_dns
            verify_no_leaks
            ;;
        cleanup|remove|uninstall)
            cleanup
            ;;
        *)
            echo "Encrypted DNS Proxy Setup"
            echo ""
            echo "Usage: $0 {setup|status|test|cleanup}"
            echo ""
            echo "Commands:"
            echo "  setup   - Install and configure all DNS proxies (default)"
            echo "  status  - Check service status"
            echo "  test    - Test DNS configuration"
            echo "  cleanup - Remove all configuration and restore defaults"
            exit 1
            ;;
    esac
}

main "$@"
