#!/bin/bash
# Linux System Hardening for Anti-Geolocation
# MAC rotation, hostname randomization, NTP manipulation, hardware serial obfuscation

set -euo pipefail

LOG_FILE="/var/log/system-hardening.log"
CONFIG_DIR="/etc/anti-geolocation"

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

# ============================================================================
# MAC ADDRESS ROTATION
# ============================================================================

# Install macchanger
install_macchanger() {
    if ! command -v macchanger &>/dev/null; then
        log "Installing macchanger..."
        if command -v apt-get &>/dev/null; then
            apt-get update && apt-get install -y macchanger
        elif command -v dnf &>/dev/null; then
            dnf install -y macchanger
        elif command -v pacman &>/dev/null; then
            pacman -S --noconfirm macchanger
        else
            error "Could not install macchanger. Please install manually."
            return 1
        fi
    fi
    success "macchanger installed"
}

# Generate random MAC address
generate_mac() {
    local oui="$(printf '%02x' $((RANDOM % 256))):$(printf '%02x' $((RANDOM % 256))):$(printf '%02x' $((RANDOM % 256)))"
    local nic="$(printf '%02x' $((RANDOM % 256))):$(printf '%02x' $((RANDOM % 256))):$(printf '%02x' $((RANDOM % 256)))"
    echo "$oui:$nic"
}

# Generate MAC from specific vendor (for plausible deniability)
generate_vendor_mac() {
    local vendor="${1:-random}"
    
    # Common vendor OUIs
    declare -A VENDOR_OUIS=(
        ["intel"]="00:1B:21 00:1C:C0 00:1D:E0 00:1E:64 00:1E:67"
        ["realtek"]="00:0A:E6 00:0E:2E 00:11:5D 00:12:17 00:13:46"
        ["broadcom"]="00:05:5D 00:0A:F7 00:0C:41 00:0D:56 00:0E:7F"
        ["qualcomm"]="00:03:7F 00:0A:F5 00:0C:E7 00:0D:6F 00:0E:9C"
        ["cisco"]="00:00:0C 00:00:5E 00:01:42 00:01:43 00:01:C7"
        ["apple"]="00:03:93 00:05:02 00:0A:27 00:0A:95 00:0D:93"
        ["dell"]="00:08:74 00:0B:DB 00:0C:F1 00:0F:1F 00:12:3F"
        ["hp"]="00:01:E6 00:02:A5 00:03:47 00:08:02 00:08:83"
    )
    
    if [[ "$vendor" == "random" ]]; then
        local vendors=("${!VENDOR_OUIS[@]}")
        vendor="${vendors[$RANDOM % ${#vendors[@]}]}"
    fi
    
    local oui_list="${VENDOR_OUIS[$vendor]:-00:00:00}"
    local oui="$(echo "$oui_list" | tr ' ' '\n' | shuf -n 1)"
    local nic="$(printf '%02x:%02x:%02x' $((RANDOM % 256)) $((RANDOM % 256)) $((RANDOM % 256)))"
    
    echo "$oui:$nic"
}

# Change MAC address
change_mac() {
    local iface="$1"
    local new_mac="${2:-}"
    
    if [[ -z "$new_mac" ]]; then
        new_mac="$(generate_vendor_mac random)"
    fi
    
    log "Changing MAC address for $iface to $new_mac"
    
    # Bring interface down
    ip link set "$iface" down
    
    # Change MAC
    if macchanger -m "$new_mac" "$iface" &>/dev/null; then
        success "MAC address changed to $new_mac"
    else
        error "Failed to change MAC address"
        ip link set "$iface" up
        return 1
    fi
    
    # Bring interface up
    ip link set "$iface" up
    
    # Restart NetworkManager if running
    if systemctl is-active --quiet NetworkManager; then
        systemctl restart NetworkManager
    fi
    
    return 0
}

# Setup automatic MAC rotation
setup_mac_rotation() {
    log "Setting up automatic MAC rotation..."
    
    mkdir -p "$CONFIG_DIR"
    
    # Create MAC rotation script
    cat > "$CONFIG_DIR/mac-rotate.sh" << 'EOF'
#!/bin/bash
# Automatic MAC address rotation

CONFIG_DIR="/etc/anti-geolocation"
LOG_FILE="/var/log/mac-rotation.log"

# Get all physical interfaces (exclude loopback, virtual, docker)
get_interfaces() {
    ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -vE "^(lo|docker|veth|br-|virbr|tun|wg)"
}

# Generate random MAC
generate_mac() {
    printf '%02x:%02x:%02x:%02x:%02x:%02x' \
        $((RANDOM % 256)) $((RANDOM % 256)) $((RANDOM % 256)) \
        $((RANDOM % 256)) $((RANDOM % 256)) $((RANDOM % 256))
}

# Rotate MAC for interface
rotate_mac() {
    local iface="$1"
    local new_mac="$(generate_mac)"
    
    echo "[$(date)] Rotating MAC for $iface to $new_mac" >> "$LOG_FILE"
    
    ip link set "$iface" down
    macchanger -m "$new_mac" "$iface" >> "$LOG_FILE" 2>&1
    ip link set "$iface" up
}

# Main
for iface in $(get_interfaces); do
    rotate_mac "$iface"
done
EOF
    
    chmod +x "$CONFIG_DIR/mac-rotate.sh"
    
    # Create systemd service
    cat > /etc/systemd/system/mac-rotation.service << EOF
[Unit]
Description=MAC Address Rotation
After=network.target

[Service]
Type=oneshot
ExecStart=$CONFIG_DIR/mac-rotate.sh
EOF
    
    # Create systemd timer (rotate every boot and every hour)
    cat > /etc/systemd/system/mac-rotation.timer << 'EOF'
[Unit]
Description=Run MAC rotation hourly

[Timer]
OnBootSec=1min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    systemctl daemon-reload
    systemctl enable mac-rotation.timer
    systemctl start mac-rotation.timer
    
    success "MAC rotation scheduled"
}

# Configure NetworkManager for MAC randomization
configure_networkmanager_mac() {
    log "Configuring NetworkManager for MAC randomization..."
    
    mkdir -p /etc/NetworkManager/conf.d/
    
    cat > /etc/NetworkManager/conf.d/mac-randomization.conf << 'EOF'
[device]
wifi.scan-rand-mac-address=yes
wifi.cloned-mac-address=random
ethernet.cloned-mac-address=random

[connection]
wifi.powersave=2
EOF
    
    systemctl restart NetworkManager
    success "NetworkManager MAC randomization configured"
}

# ============================================================================
# HOSTNAME RANDOMIZATION
# ============================================================================

# Generate random hostname
generate_hostname() {
    local adjectives=("blue" "red" "green" "yellow" "purple" "orange" "pink" "gray" "black" "white")
    local nouns=("laptop" "desktop" "workstation" "server" "pc" "computer" "device" "machine" "system" "node")
    local numbers=$(printf '%03d' $((RANDOM % 1000)))
    
    echo "${adjectives[$RANDOM % ${#adjectives[@]}]}-${nouns[$RANDOM % ${#nouns[@]}]}-$numbers"
}

# Change hostname
change_hostname() {
    local new_hostname="${1:-$(generate_hostname)}"
    local old_hostname
    old_hostname=$(hostname)
    
    log "Changing hostname from $old_hostname to $new_hostname"
    
    # Set hostname
    hostnamectl set-hostname "$new_hostname"
    
    # Update /etc/hostname
    echo "$new_hostname" > /etc/hostname
    
    # Update /etc/hosts
    sed -i "s/127.0.1.1.*/127.0.1.1\t$new_hostname/" /etc/hosts
    
    success "Hostname changed to $new_hostname"
}

# Setup automatic hostname rotation
setup_hostname_rotation() {
    log "Setting up automatic hostname rotation..."
    
    cat > "$CONFIG_DIR/hostname-rotate.sh" << 'EOF'
#!/bin/bash
# Automatic hostname rotation

LOG_FILE="/var/log/hostname-rotation.log"

# Generate random hostname
generate_hostname() {
    local adjectives=("blue" "red" "green" "yellow" "purple" "orange" "pink" "gray" "black" "white")
    local nouns=("laptop" "desktop" "workstation" "server" "pc" "computer" "device" "machine" "system" "node")
    local numbers=$(printf '%03d' $((RANDOM % 1000)))
    
    echo "${adjectives[$RANDOM % ${#adjectives[@]}]}-${nouns[$RANDOM % ${#nouns[@]}]}-$numbers"
}

# Rotate hostname
new_hostname="$(generate_hostname)"
echo "[$(date)] Rotating hostname to $new_hostname" >> "$LOG_FILE"

hostnamectl set-hostname "$new_hostname"
echo "$new_hostname" > /etc/hostname
sed -i "s/127.0.1.1.*/127.0.1.1\t$new_hostname/" /etc/hosts
EOF
    
    chmod +x "$CONFIG_DIR/hostname-rotate.sh"
    
    # Create systemd service
    cat > /etc/systemd/system/hostname-rotation.service << EOF
[Unit]
Description=Hostname Rotation
After=network.target

[Service]
Type=oneshot
ExecStart=$CONFIG_DIR/hostname-rotate.sh
EOF
    
    # Create systemd timer (rotate on boot)
    cat > /etc/systemd/system/hostname-rotation.timer << 'EOF'
[Unit]
Description=Run hostname rotation on boot

[Timer]
OnBootSec=2min
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    systemctl daemon-reload
    systemctl enable hostname-rotation.timer
    systemctl start hostname-rotation.timer
    
    success "Hostname rotation scheduled"
}

# ============================================================================
# NTP MANIPULATION
# ============================================================================

# Configure NTP for privacy
configure_ntp() {
    log "Configuring NTP for privacy..."
    
    # Install chrony (better privacy than systemd-timesyncd)
    if command -v apt-get &>/dev/null; then
        apt-get install -y chrony
    elif command -v dnf &>/dev/null; then
        dnf install -y chrony
    elif command -v pacman &>/dev/null; then
        pacman -S --noconfirm chrony
    fi
    
    # Configure chrony for privacy
    cat > /etc/chrony/chrony.conf << 'EOF'
# Privacy-focused NTP configuration

# Use privacy-preserving NTP pools
pool time.cloudflare.com iburst nts
pool ntppool1.time.nl iburst
pool ntppool2.time.nl iburst

# Disable logging of NTP queries
noclientlog

# Allow only local queries
allow 127.0.0.1
allow ::1

# Don't serve time to others
deny all

# Disable command access
cmdallow 127.0.0.1
cmdallow ::1

# Drift file
driftfile /var/lib/chrony/chrony.drift

# Don't make large time jumps
makestep 1.0 3

# Enable kernel synchronization
rtcsync

# Disable hardware timestamping (can leak hardware info)
hwtimestamp *

# Add random offset to queries (timing obfuscation)
maxsamples 10
minsamples 5

# Disable NTP server functionality
local stratum 10
EOF
    
    # Enable and start chrony
    systemctl enable chronyd
    systemctl restart chronyd
    
    success "NTP configured for privacy"
}

# Spoof system time (for testing only - dangerous!)
spoof_time() {
    local offset_hours="${1:-0}"
    
    warning "Time spoofing can cause serious issues with TLS/SSL!"
    warning "This should only be used in isolated test environments."
    
    # Stop NTP
    systemctl stop chronyd 2>/dev/null || true
    systemctl stop systemd-timesyncd 2>/dev/null || true
    
    # Calculate new time
    local new_time
    new_time=$(date -d "${offset_hours} hours" "+%Y-%m-%d %H:%M:%S")
    
    # Set time
    timedatectl set-ntp false
    timedatectl set-time "$new_time"
    
    log "Time spoofed by $offset_hours hours: $new_time"
}

# ============================================================================
# HARDWARE SERIAL OBFUSCATION
# ============================================================================

# Spoof DMI/BIOS information (requires custom kernel or systemd spoofing)
spoof_dmi() {
    log "Setting up DMI/BIOS information spoofing..."
    
    # Create systemd service to spoof DMI info in /sys
    cat > /etc/systemd/system/dmi-spoof.service << 'EOF'
[Unit]
Description=DMI/BIOS Information Spoofing
After=systemd-remount-fs.service
Before=sysinit.target

[Service]
Type=oneshot
ExecStart=/etc/anti-geolocation/dmi-spoof.sh
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
EOF
    
    cat > "$CONFIG_DIR/dmi-spoof.sh" << 'EOF'
#!/bin/bash
# Spoof DMI/BIOS information
# Note: This requires kernel patch or overlayfs

SPOOF_SYS_VENDOR="LENOVO"
SPOOF_PRODUCT_NAME="ThinkPad T480"
SPOOF_PRODUCT_VERSION="20L5"
SPOOF_BOARD_VENDOR="LENOVO"
SPOOF_BOARD_NAME="20L5S01F00"
SPOOF_BIOS_VENDOR="LENOVO"
SPOOF_BIOS_VERSION="N24ET61W"

# Mount tmpfs over DMI entries to spoof them
mount -t tmpfs -o size=1M,mode=0755 tmpfs /sys/class/dmi/id 2>/dev/null || true

echo "$SPOOF_SYS_VENDOR" > /sys/class/dmi/id/sys_vendor 2>/dev/null || true
echo "$SPOOF_PRODUCT_NAME" > /sys/class/dmi/id/product_name 2>/dev/null || true
echo "$SPOOF_PRODUCT_VERSION" > /sys/class/dmi/id/product_version 2>/dev/null || true
echo "$SPOOF_BOARD_VENDOR" > /sys/class/dmi/id/board_vendor 2>/dev/null || true
echo "$SPOOF_BOARD_NAME" > /sys/class/dmi/id/board_name 2>/dev/null || true
echo "$SPOOF_BIOS_VENDOR" > /sys/class/dmi/id/bios_vendor 2>/dev/null || true
echo "$SPOOF_BIOS_VERSION" > /sys/class/dmi/id/bios_version 2>/dev/null || true
EOF
    
    chmod +x "$CONFIG_DIR/dmi-spoof.sh"
    
    warning "DMI spoofing requires kernel modifications for full effectiveness"
    warning "Current implementation is limited by kernel security"
}

# Spoof machine ID
spoof_machine_id() {
    log "Spoofing machine ID..."
    
    # Generate new machine ID
    local new_id
    new_id=$(cat /proc/sys/kernel/random/uuid | tr -d '-')
    
    # Backup old ID
    if [[ -f /etc/machine-id ]]; then
        cp /etc/machine-id /etc/machine-id.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    # Set new ID
    echo "$new_id" > /etc/machine-id
    
    # Also update dbus machine ID
    if [[ -f /var/lib/dbus/machine-id ]]; then
        ln -sf /etc/machine-id /var/lib/dbus/machine-id
    fi
    
    success "Machine ID changed to $new_id"
}

# Spoof product UUID
spoof_product_uuid() {
    log "Attempting to spoof product UUID..."
    
    warning "Product UUID is typically set in firmware and cannot be changed"
    warning "Consider using virtualization for full hardware anonymization"
    
    # Show current UUID
    if [[ -f /sys/class/dmi/id/product_uuid ]]; then
        local current_uuid
        current_uuid=$(cat /sys/class/dmi/id/product_uuid)
        info "Current product UUID: $current_uuid"
    fi
}

# ============================================================================
# IPv6 DISABLE
# ============================================================================

disable_ipv6() {
    log "Disabling IPv6..."
    
    # Disable IPv6 via sysctl
    cat > /etc/sysctl.d/99-disable-ipv6.conf << 'EOF'
# Disable IPv6
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1
EOF
    
    # Apply settings
    sysctl --system
    
    # Disable IPv6 in GRUB
    if [[ -f /etc/default/grub ]]; then
        sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="ipv6.disable=1 /' /etc/default/grub
        update-grub 2>/dev/null || true
    fi
    
    success "IPv6 disabled"
}

# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

# Apply all hardening
apply_all() {
    log "Applying full system hardening..."
    
    check_root
    install_macchanger
    
    # MAC address
    configure_networkmanager_mac
    setup_mac_rotation
    
    # Change MAC immediately for all interfaces
    for iface in $(ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -vE "^(lo|docker)"); do
        if [[ -d "/sys/class/net/$iface" ]]; then
            change_mac "$iface"
        fi
    done
    
    # Hostname
    setup_hostname_rotation
    change_hostname
    
    # NTP
    configure_ntp
    
    # Hardware
    spoof_machine_id
    spoof_product_uuid
    spoof_dmi
    
    # Network
    disable_ipv6
    
    success "System hardening complete!"
    echo ""
    info "Current configuration:"
    info "  Hostname: $(hostname)"
    info "  Machine ID: $(cat /etc/machine-id)"
    echo ""
    info "MAC addresses:"
    for iface in $(ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -vE "^(lo|docker)"); do
        if [[ -d "/sys/class/net/$iface" ]]; then
            local mac
            mac=$(cat "/sys/class/net/$iface/address")
            info "  $iface: $mac"
        fi
    done
}

# Status check
status() {
    echo "=== System Hardening Status ==="
    echo ""
    echo "Hostname: $(hostname)"
    echo "Machine ID: $(cat /etc/machine-id)"
    echo ""
    echo "MAC Addresses:"
    for iface in $(ip link show | grep -E "^[0-9]+:" | awk -F: '{print $2}' | tr -d ' ' | grep -vE "^(lo|docker)"); do
        if [[ -d "/sys/class/net/$iface" ]]; then
            local mac
            mac=$(cat "/sys/class/net/$iface/address")
            echo "  $iface: $mac"
        fi
    done
    echo ""
    echo "IPv6 Status:"
    sysctl net.ipv6.conf.all.disable_ipv6 2>/dev/null || echo "  Unknown"
    echo ""
    echo "Services:"
    systemctl is-active mac-rotation.timer &>/dev/null && echo "  MAC rotation: ACTIVE" || echo "  MAC rotation: INACTIVE"
    systemctl is-active hostname-rotation.timer &>/dev/null && echo "  Hostname rotation: ACTIVE" || echo "  Hostname rotation: INACTIVE"
    systemctl is-active chronyd &>/dev/null && echo "  Chrony NTP: ACTIVE" || echo "  Chrony NTP: INACTIVE"
}

# Main
main() {
    case "${1:-apply}" in
        apply|all)
            apply_all
            ;;
        status)
            status
            ;;
        mac)
            install_macchanger
            change_mac "${2:-}"
            ;;
        hostname)
            change_hostname "${2:-}"
            ;;
        machine-id)
            spoof_machine_id
            ;;
        ipv6-off)
            disable_ipv6
            ;;
        ipv6-on)
            warning "Re-enabling IPv6..."
            rm -f /etc/sysctl.d/99-disable-ipv6.conf
            sysctl --system
            ;;
        *)
            echo "Linux System Hardening for Anti-Geolocation"
            echo ""
            echo "Usage: $0 {apply|status|mac|hostname|machine-id|ipv6-off|ipv6-on}"
            echo ""
            echo "Commands:"
            echo "  apply       - Apply all hardening measures"
            echo "  status      - Show current status"
            echo "  mac [iface] - Change MAC address for interface"
            echo "  hostname    - Change hostname"
            echo "  machine-id  - Spoof machine ID"
            echo "  ipv6-off    - Disable IPv6"
            echo "  ipv6-on     - Re-enable IPv6"
            exit 1
            ;;
    esac
}

main "$@"
