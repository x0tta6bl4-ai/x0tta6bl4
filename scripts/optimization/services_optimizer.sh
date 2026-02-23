#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${HOME}/optimization.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$LOG_FILE" >&2
    exit 1
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Services Optimizer - Optimize systemd services and reduce boot time

OPTIONS:
    --analyze           Analyze boot time and slow services
    --optimize-boot     Optimize boot time by disabling slow services
    --optimize-network  Reduce NetworkManager-wait-online timeout
    --disable-bluetooth Disable Bluetooth services (if not used)
    --disable-cups      Disable CUPS printing services (if not used)
    --disable-plymouth  Disable Plymouth boot splash
    --all               Run all optimizations
    --dry-run           Show what would be done without making changes
    --yes               Skip confirmation prompts (for automation)
    --help              Show this help message

EXAMPLES:
    $0 --analyze
    $0 --optimize-boot --dry-run
    $0 --all --yes
    $0 --disable-plymouth --disable-bluetooth

EOF
}

DRY_RUN=false
SKIP_CONFIRM=false

check_root() {
    if [ "$EUID" -ne 0 ] && [ "$DRY_RUN" = false ]; then
        error "This script must be run as root (use sudo)"
    fi
}

confirm_action() {
    local message="$1"
    
    if [ "$SKIP_CONFIRM" = true ]; then
        log "Skipping confirmation (--yes flag)"
        return 0
    fi
    
    echo ""
    read -p "$message [y/N]: " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Operation cancelled by user"
        return 1
    fi
    
    return 0
}

analyze_boot() {
    log "Analyzing boot time and slow services..."
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    Boot Time Analysis                         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    if ! command -v systemd-analyze &> /dev/null; then
        error "systemd-analyze not found"
    fi
    
    echo "⏱️  Overall Boot Time:"
    systemd-analyze time
    echo ""
    
    echo "🐌 Top 10 Slowest Services:"
    systemd-analyze blame | head -10
    echo ""
    
    echo "🔍 Critical Chain:"
    systemd-analyze critical-chain | head -20
    echo ""
    
    log "Boot analysis complete"
}

disable_service() {
    local service="$1"
    local reason="$2"
    
    if ! systemctl is-enabled "$service" &>/dev/null; then
        log "Service $service is already disabled or not found"
        return 0
    fi
    
    log "Disabling service: $service ($reason)"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would disable: $service"
        return 0
    fi
    
    systemctl disable "$service" || log "Warning: Could not disable $service"
    systemctl stop "$service" 2>/dev/null || log "Warning: Could not stop $service"
    
    log "✅ Service disabled: $service"
}

mask_service() {
    local service="$1"
    local reason="$2"
    
    if systemctl is-masked "$service" &>/dev/null; then
        log "Service $service is already masked"
        return 0
    fi
    
    log "Masking service: $service ($reason)"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would mask: $service"
        return 0
    fi
    
    systemctl mask "$service" || log "Warning: Could not mask $service"
    
    log "✅ Service masked: $service"
}

optimize_network() {
    log "Optimizing NetworkManager-wait-online..."
    
    local override_dir="/etc/systemd/system/NetworkManager-wait-online.service.d"
    local override_file="$override_dir/override.conf"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would create override at $override_file"
        return 0
    fi
    
    if ! confirm_action "Reduce NetworkManager-wait-online timeout to 5 seconds?"; then
        return 0
    fi
    
    mkdir -p "$override_dir"
    
    cat > "$override_file" << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/nm-online -q --timeout=5
EOF
    
    systemctl daemon-reload
    
    log "✅ NetworkManager-wait-online optimized"
}

disable_plymouth() {
    log "Disabling Plymouth boot splash..."
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would disable Plymouth services"
        return 0
    fi
    
    if ! confirm_action "Disable Plymouth boot splash?"; then
        return 0
    fi
    
    disable_service "plymouth-quit-wait.service" "slow boot splash"
    disable_service "plymouth-start.service" "slow boot splash"
    mask_service "plymouth-quit-wait.service" "prevent re-enabling"
    
    log "✅ Plymouth disabled"
}

disable_bluetooth() {
    log "Disabling Bluetooth services..."
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would disable Bluetooth services"
        return 0
    fi
    
    if ! confirm_action "Disable Bluetooth services?"; then
        return 0
    fi
    
    disable_service "bluetooth.service" "not needed"
    
    log "✅ Bluetooth disabled"
}

disable_cups() {
    log "Disabling CUPS printing services..."
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would disable CUPS services"
        return 0
    fi
    
    if ! confirm_action "Disable CUPS printing services?"; then
        return 0
    fi
    
    disable_service "cups.service" "no printer"
    disable_service "cups-browsed.service" "no printer"
    
    log "✅ CUPS disabled"
}

optimize_boot_time() {
    log "Running comprehensive boot time optimization..."
    
    disable_plymouth
    optimize_network
    
    log "Checking for other slow services..."
    
    local slow_services=$(systemd-analyze blame | awk '$1 ~ /s$/ && $1+0 > 5' | awk '{print $2}')
    
    if [ -z "$slow_services" ]; then
        log "No additional slow services found"
    else
        log "Found slow services (>5s):"
        echo "$slow_services"
        log "Review these services manually and consider disabling if not needed"
    fi
    
    log "✅ Boot time optimization complete"
}

optimize_all() {
    log "Running comprehensive system services optimization..."
    
    check_root
    
    optimize_boot_time
    
    if systemctl is-enabled bluetooth.service &>/dev/null; then
        if confirm_action "Disable Bluetooth? (Only if you don't use it)"; then
            disable_bluetooth
        fi
    fi
    
    if systemctl is-enabled cups.service &>/dev/null; then
        if confirm_action "Disable CUPS printing? (Only if you don't have a printer)"; then
            disable_cups
        fi
    fi
    
    systemctl daemon-reload
    
    log "✅ Comprehensive optimization complete"
    log "⚠️  Reboot required for changes to take full effect"
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    local action_taken=false
    local actions_to_run=()
    
    while [ $# -gt 0 ]; do
        case "$1" in
            --analyze|--optimize-boot|--optimize-network|--disable-bluetooth|--disable-cups|--disable-plymouth|--all)
                actions_to_run+=("$1")
                ;;
            --dry-run)
                DRY_RUN=true
                log "DRY-RUN MODE ENABLED"
                ;;
            --yes)
                SKIP_CONFIRM=true
                log "Auto-confirm enabled (skipping prompts)"
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
        shift
    done
    
    for action in "${actions_to_run[@]}"; do
        case "$action" in
            --analyze)
                analyze_boot
                action_taken=true
                ;;
            --optimize-boot)
                check_root
                optimize_boot_time
                action_taken=true
                ;;
            --optimize-network)
                check_root
                optimize_network
                action_taken=true
                ;;
            --disable-bluetooth)
                check_root
                disable_bluetooth
                action_taken=true
                ;;
            --disable-cups)
                check_root
                disable_cups
                action_taken=true
                ;;
            --disable-plymouth)
                check_root
                disable_plymouth
                action_taken=true
                ;;
            --all)
                optimize_all
                action_taken=true
                ;;
        esac
    done
    
    if [ "$action_taken" = false ]; then
        error "No action specified. Use --help for usage information"
    fi
    
    log "Services optimization complete"
}

main "$@"
