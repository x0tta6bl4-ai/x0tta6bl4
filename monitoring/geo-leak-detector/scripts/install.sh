#!/bin/bash
#
# Geo-Leak Detector Installation Script
# For x0tta6bl4 project
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/geo-leak-detector"
SERVICE_NAME="geo-leak-detector"
USER="geo-leak"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    local deps=("python3" "pip3" "curl" "iptables")
    local missing=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done
    
    if [[ ${#missing[@]} -ne 0 ]]; then
        log_warning "Missing dependencies: ${missing[*]}"
        log_info "Installing dependencies..."
        apt-get update
        apt-get install -y python3 python3-pip curl iptables nftables postgresql-client redis-tools
    fi
    
    log_success "Dependencies OK"
}

create_user() {
    log_info "Creating service user..."
    
    if ! id "$USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$USER"
        log_success "User $USER created"
    else
        log_warning "User $USER already exists"
    fi
}

install_app() {
    log_info "Installing Geo-Leak Detector..."
    
    # Create directories
    mkdir -p "$INSTALL_DIR"
    mkdir -p "/var/log/geo-leak-detector"
    mkdir -p "/etc/geo-leak-detector"
    
    # Copy application files
    cp -r ../src "$INSTALL_DIR/"
    cp -r ../config "$INSTALL_DIR/"
    cp ../requirements.txt "$INSTALL_DIR/"
    
    # Install Python dependencies
    pip3 install -r "$INSTALL_DIR/requirements.txt"
    
    # Set permissions
    chown -R "$USER:$USER" "$INSTALL_DIR"
    chown -R "$USER:$USER" "/var/log/geo-leak-detector"
    chmod 750 "$INSTALL_DIR"
    
    log_success "Application installed to $INSTALL_DIR"
}

setup_database() {
    log_info "Setting up database..."
    
    # Check if PostgreSQL is installed
    if ! command -v psql &> /dev/null; then
        log_warning "PostgreSQL not found. Please install and configure manually."
        return
    fi
    
    # Create database and user (requires PostgreSQL superuser)
    sudo -u postgres psql << EOF
CREATE USER geo_leak WITH PASSWORD 'changeme';
CREATE DATABASE geo_leak_detector OWNER geo_leak;
GRANT ALL PRIVILEGES ON DATABASE geo_leak_detector TO geo_leak;
EOF
    
    log_success "Database configured"
}

setup_redis() {
    log_info "Setting up Redis..."
    
    if ! command -v redis-cli &> /dev/null; then
        log_warning "Redis not found. Please install and configure manually."
        return
    fi
    
    # Enable Redis persistence
    if [[ -f /etc/redis/redis.conf ]]; then
        sed -i 's/^# appendonly no/appendonly yes/' /etc/redis/redis.conf
        systemctl restart redis
    fi
    
    log_success "Redis configured"
}

create_systemd_service() {
    log_info "Creating systemd service..."
    
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Geo-Leak Detector Service
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR
EnvironmentFile=/etc/geo-leak-detector/env
ExecStart=/usr/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8080
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/geo-leak-detector

# Network capabilities for kill-switch
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF
    
    # Create environment file
    cat > "/etc/geo-leak-detector/env" << EOF
GEO_ENV=production
GEO_DB_HOST=localhost
GEO_DB_PORT=5432
GEO_DB_NAME=geo_leak_detector
GEO_DB_USER=geo_leak
GEO_DB_PASSWORD=changeme
GEO_REDIS_HOST=localhost
GEO_REDIS_PORT=6379
GEO_TELEGRAM_ENABLED=false
GEO_CHECK_INTERVAL=30
GEO_AUTO_REMEDIATE=true
GEO_MAPEK_ENABLED=true
GEO_MAPEK_NODE_ID=geo-leak-detector
EOF
    
    chmod 600 "/etc/geo-leak-detector/env"
    
    systemctl daemon-reload
    log_success "Systemd service created"
}

setup_iptables() {
    log_info "Setting up iptables rules..."
    
    # Create killswitch script
    cat > "/usr/local/bin/killswitch.sh" << 'EOF'
#!/bin/bash
# Kill-switch script for Geo-Leak Detector

ACTION=$1

case $ACTION in
    enable)
        # Block all outbound traffic
        iptables -F OUTPUT
        iptables -A OUTPUT -o lo -j ACCEPT
        iptables -A OUTPUT -j DROP
        echo "Kill-switch enabled: All outbound traffic blocked"
        ;;
    disable)
        # Restore normal traffic
        iptables -F OUTPUT
        echo "Kill-switch disabled: Traffic restored"
        ;;
    status)
        iptables -L OUTPUT -n -v
        ;;
    *)
        echo "Usage: $0 {enable|disable|status}"
        exit 1
        ;;
esac
EOF
    
    chmod +x "/usr/local/bin/killswitch.sh"
    
    log_success "Kill-switch script installed"
}

enable_service() {
    log_info "Enabling and starting service..."
    
    systemctl enable "$SERVICE_NAME"
    
    log_info "Service enabled. Start with: systemctl start $SERVICE_NAME"
}

print_config_info() {
    echo ""
    echo "========================================"
    echo "  Geo-Leak Detector Installation"
    echo "========================================"
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Log directory: /var/log/geo-leak-detector"
    echo "Config directory: /etc/geo-leak-detector"
    echo ""
    echo "Next steps:"
    echo "  1. Edit configuration: nano /etc/geo-leak-detector/env"
    echo "  2. Configure Telegram bot (optional)"
    echo "  3. Set expected exit IPs in config"
    echo "  4. Start service: systemctl start $SERVICE_NAME"
    echo "  5. Check status: systemctl status $SERVICE_NAME"
    echo ""
    echo "API endpoints:"
    echo "  Health: http://localhost:8080/api/v1/health"
    echo "  Status: http://localhost:8080/api/v1/status"
    echo "  Metrics: http://localhost:8080/api/v1/metrics"
    echo ""
    echo "WebSocket: ws://localhost:8080/api/v1/ws"
    echo ""
    echo "Documentation: $INSTALL_DIR/README.md"
    echo "========================================"
}

# Main installation
main() {
    echo "========================================"
    echo "  Geo-Leak Detector Installer"
    echo "  For x0tta6bl4 Project"
    echo "========================================"
    echo ""
    
    check_root
    check_dependencies
    create_user
    install_app
    setup_database
    setup_redis
    create_systemd_service
    setup_iptables
    enable_service
    
    log_success "Installation complete!"
    print_config_info
}

# Run main
main "$@"
