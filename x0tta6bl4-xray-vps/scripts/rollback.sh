#!/bin/bash
# Xray Rollback Script
# Rolls back Xray configuration to a previous state
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

# Configuration
BACKUP_DIR="/root/xray-backups"
CONFIG_DIR="/usr/local/etc/xray"
SSL_DIR="/etc/ssl/xray"

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_section() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS] [BACKUP_FILE]

Rollback Xray configuration to a previous backup.

OPTIONS:
    -l, --list              List available backups
    -a, --auto              Rollback to most recent backup
    -f, --force             Force rollback without confirmation
    -c, --current           Create backup of current state before rollback
    -h, --help              Show this help message

EXAMPLES:
    $0 -l                           List all backups
    $0 backup-20260131-120000.tar.gz  Rollback to specific backup
    $0 -a                           Rollback to most recent backup
    $0 -a -c                        Rollback with current state backup
EOF
}

# List available backups
list_backups() {
    log_section "AVAILABLE BACKUPS"
    
    if [[ ! -d "$BACKUP_DIR" ]] || [[ -z $(ls -A "$BACKUP_DIR" 2>/dev/null) ]]; then
        log_warn "No backups found in $BACKUP_DIR"
        return 1
    fi
    
    printf "%-5s %-35s %-15s %-20s\n" "NUM" "BACKUP NAME" "SIZE" "CREATED"
    printf "%s\n" "$(printf '%*s' 80 '' | tr ' ' '-')"
    
    local count=1
    for archive in $(ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null); do
        if [[ -f "$archive" ]]; then
            local name=$(basename "$archive")
            local size=$(du -h "$archive" | cut -f1)
            local created=$(stat -c %y "$archive" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1 || stat -f %Sm "$archive" 2>/dev/null)
            printf "%-5s %-35s %-15s %-20s\n" "[$count]" "$name" "$size" "$created"
            ((count++))
        fi
    done
    
    return 0
}

# Get latest backup
get_latest_backup() {
    local latest=$(ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | head -1)
    if [[ -z "$latest" ]]; then
        log_error "No backups found"
        exit 1
    fi
    echo "$latest"
}

# Get backup by number
get_backup_by_number() {
    local num="$1"
    local backup=$(ls -1t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | sed -n "${num}p")
    if [[ -z "$backup" ]]; then
        log_error "Backup #$num not found"
        exit 1
    fi
    echo "$backup"
}

# Create pre-rollback backup
create_current_backup() {
    log_info "Creating backup of current state..."
    
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_path="${BACKUP_DIR}/pre-rollback-${timestamp}"
    
    mkdir -p "$backup_path"
    
    # Backup current configuration
    if [[ -d "$CONFIG_DIR" ]]; then
        cp -r "$CONFIG_DIR" "$backup_path/"
    fi
    
    # Backup certificates
    if [[ -d "$SSL_DIR" ]]; then
        cp -r "$SSL_DIR" "$backup_path/ssl"
    fi
    
    # Backup service file
    if [[ -f /etc/systemd/system/xray.service ]]; then
        cp /etc/systemd/system/xray.service "$backup_path/"
    fi
    
    # Create archive
    cd "$BACKUP_DIR"
    tar -czf "pre-rollback-${timestamp}.tar.gz" "pre-rollback-${timestamp}"
    rm -rf "pre-rollback-${timestamp}"
    
    log_success "Current state backed up: pre-rollback-${timestamp}.tar.gz"
}

# Verify backup integrity
verify_backup() {
    local archive="$1"
    
    log_info "Verifying backup integrity..."
    
    if ! tar -tzf "$archive" &>/dev/null; then
        log_error "Backup archive is corrupted"
        return 1
    fi
    
    log_success "Backup integrity verified"
    return 0
}

# Extract backup
extract_backup() {
    local archive="$1"
    local extract_dir="$2"
    
    log_info "Extracting backup..."
    
    tar -xzf "$archive" -C "$extract_dir"
    
    # Get extracted directory name
    local extracted_dir=$(ls -1 "$extract_dir" | head -1)
    echo "$extract_dir/$extracted_dir"
}

# Stop Xray service
stop_service() {
    log_info "Stopping Xray service..."
    
    if systemctl is-active --quiet xray; then
        systemctl stop xray
        sleep 2
        
        if systemctl is-active --quiet xray; then
            log_error "Failed to stop Xray service"
            return 1
        fi
    fi
    
    log_success "Xray service stopped"
    return 0
}

# Start Xray service
start_service() {
    log_info "Starting Xray service..."
    
    systemctl start xray
    sleep 3
    
    if systemctl is-active --quiet xray; then
        log_success "Xray service started"
        return 0
    else
        log_error "Failed to start Xray service"
        return 1
    fi
}

# Restore configuration
restore_config() {
    local backup_path="$1"
    
    log_section "RESTORING CONFIGURATION"
    
    # Restore Xray config
    if [[ -d "$backup_path/xray" ]]; then
        log_info "Restoring Xray configuration..."
        rm -rf "$CONFIG_DIR"
        cp -r "$backup_path/xray" "$CONFIG_DIR"
        log_success "Configuration restored"
    else
        log_warn "No configuration found in backup"
    fi
    
    # Restore SSL certificates
    if [[ -d "$backup_path/ssl" ]]; then
        log_info "Restoring SSL certificates..."
        rm -rf "$SSL_DIR"
        cp -r "$backup_path/ssl" "$SSL_DIR"
        chmod 600 "$SSL_DIR"/*.key 2>/dev/null || true
        chmod 644 "$SSL_DIR"/*.crt 2>/dev/null || true
        log_success "Certificates restored"
    else
        log_warn "No certificates found in backup"
    fi
    
    # Restore service file
    if [[ -f "$backup_path/xray.service" ]]; then
        log_info "Restoring service file..."
        cp "$backup_path/xray.service" /etc/systemd/system/
        systemctl daemon-reload
        log_success "Service file restored"
    fi
    
    # Restore client configs if present
    if [[ -d "$backup_path/xray-clients" ]]; then
        log_info "Restoring client configurations..."
        rm -rf /root/xray-clients
        cp -r "$backup_path/xray-clients" /root/
        log_success "Client configurations restored"
    fi
}

# Validate restored configuration
validate_restore() {
    log_section "VALIDATING RESTORE"
    
    # Check configuration validity
    if [[ -f "${CONFIG_DIR}/config.json" ]]; then
        if xray -test -config "${CONFIG_DIR}/config.json" &>/dev/null; then
            log_success "Configuration is valid"
        else
            log_error "Configuration is invalid"
            return 1
        fi
    else
        log_error "Configuration file not found after restore"
        return 1
    fi
    
    # Check certificates
    if [[ -f "$SSL_DIR/xray.crt" && -f "$SSL_DIR/xray.key" ]]; then
        log_success "Certificates restored correctly"
    else
        log_warn "Some certificates may be missing"
    fi
    
    return 0
}

# Perform rollback
perform_rollback() {
    local archive="$1"
    local force="${2:-false}"
    local backup_current="${3:-false}"
    
    log_section "ROLLBACK PROCEDURE"
    
    # Verify backup exists
    if [[ ! -f "$archive" ]]; then
        log_error "Backup file not found: $archive"
        exit 1
    fi
    
    log_info "Rollback target: $(basename "$archive")"
    
    # Confirm rollback
    if [[ "$force" != "true" ]]; then
        echo ""
        read -p "Are you sure you want to rollback? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Rollback cancelled"
            exit 0
        fi
    fi
    
    # Create backup of current state if requested
    if [[ "$backup_current" == "true" ]]; then
        create_current_backup
    fi
    
    # Verify backup integrity
    if ! verify_backup "$archive"; then
        log_error "Backup verification failed"
        exit 1
    fi
    
    # Create temporary directory
    local temp_dir=$(mktemp -d)
    
    # Extract backup
    local backup_path=$(extract_backup "$archive" "$temp_dir")
    
    # Stop service
    if ! stop_service; then
        log_error "Cannot proceed with rollback - service failed to stop"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    # Restore configuration
    restore_config "$backup_path"
    
    # Cleanup temp directory
    rm -rf "$temp_dir"
    
    # Validate restore
    if ! validate_restore; then
        log_error "Restore validation failed"
        log_info "You may need to manually restore from backup"
        exit 1
    fi
    
    # Start service
    if ! start_service; then
        log_error "Service failed to start after rollback"
        exit 1
    fi
    
    log_section "ROLLBACK COMPLETE"
    log_success "Successfully rolled back to: $(basename "$archive")"
    
    # Show current status
    echo ""
    log_info "Current status:"
    systemctl status xray --no-pager | head -5
}

# Main function
main() {
    local backup_file=""
    local auto_select=false
    local force=false
    local backup_current=false
    local list_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -l|--list)
                list_only=true
                shift
                ;;
            -a|--auto)
                auto_select=true
                shift
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -c|--current)
                backup_current=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                backup_file="$1"
                shift
                ;;
        esac
    done
    
    # List backups and exit
    if [[ "$list_only" == true ]]; then
        list_backups
        exit 0
    fi
    
    # Auto-select latest backup
    if [[ "$auto_select" == true ]]; then
        backup_file=$(get_latest_backup)
        log_info "Auto-selected backup: $(basename "$backup_file")"
    fi
    
    # Check if backup file is specified
    if [[ -z "$backup_file" ]]; then
        log_error "No backup file specified"
        echo ""
        list_backups
        echo ""
        usage
        exit 1
    fi
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Perform rollback
    perform_rollback "$backup_file" "$force" "$backup_current"
}

# Run main
main "$@"
