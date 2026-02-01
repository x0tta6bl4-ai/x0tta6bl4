#!/bin/bash
# Xray Configuration Backup Script
# Creates timestamped backups of Xray configuration
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
LOG_DIR="/var/log/xray"
RETENTION_DAYS=30

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Show usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Create backup of Xray configuration and related files.

OPTIONS:
    -p, --pre-deployment    Mark as pre-deployment backup
    -r, --restore FILE      Restore from backup file
    -l, --list              List available backups
    -c, --clean             Clean old backups (older than $RETENTION_DAYS days)
    -h, --help              Show this help message

EXAMPLES:
    $0                      Create standard backup
    $0 -p                   Create pre-deployment backup
    $0 -r backup-20260131.tar.gz    Restore from backup
    $0 -l                   List all backups
    $0 -c                   Clean old backups
EOF
}

# Create backup directory
create_backup_dir() {
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_type="${1:-standard}"
    local backup_name="${backup_type}-${timestamp}"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    mkdir -p "$backup_path"
    echo "$backup_path"
}

# Backup configuration
backup_config() {
    local backup_path="$1"
    
    log_info "Backing up Xray configuration..."
    
    if [[ -d "$CONFIG_DIR" ]]; then
        cp -r "$CONFIG_DIR" "$backup_path/"
        log_success "Configuration backed up"
    else
        log_warn "Configuration directory not found: $CONFIG_DIR"
    fi
}

# Backup SSL certificates
backup_certs() {
    local backup_path="$1"
    
    log_info "Backing up SSL certificates..."
    
    if [[ -d "$SSL_DIR" ]]; then
        cp -r "$SSL_DIR" "$backup_path/ssl"
        log_success "Certificates backed up"
    else
        log_warn "SSL directory not found: $SSL_DIR"
    fi
}

# Backup service file
backup_service() {
    local backup_path="$1"
    
    log_info "Backing up service file..."
    
    if [[ -f /etc/systemd/system/xray.service ]]; then
        cp /etc/systemd/system/xray.service "$backup_path/"
        log_success "Service file backed up"
    else
        log_warn "Service file not found"
    fi
}

# Backup client configurations
backup_clients() {
    local backup_path="$1"
    
    log_info "Backing up client configurations..."
    
    if [[ -d /root/xray-clients ]]; then
        cp -r /root/xray-clients "$backup_path/"
        log_success "Client configurations backed up"
    else
        log_warn "Client configurations not found"
    fi
}

# Backup system settings
backup_system() {
    local backup_path="$1"
    
    log_info "Backing up system settings..."
    
    # Backup sysctl settings
    sysctl -a > "$backup_path/sysctl.conf" 2>/dev/null || true
    
    # Backup iptables rules
    iptables-save > "$backup_path/iptables.rules" 2>/dev/null || true
    
    # Backup UFW status
    ufw status verbose > "$backup_path/ufw-status.txt" 2>/dev/null || true
    
    log_success "System settings backed up"
}

# Create backup metadata
create_metadata() {
    local backup_path="$1"
    local backup_type="${2:-standard}"
    
    cat > "$backup_path/metadata.json" << EOF
{
  "backup_type": "$backup_type",
  "created_at": "$(date -Iseconds)",
  "hostname": "$(hostname)",
  "xray_version": "$(xray -version 2>/dev/null | head -1 || echo 'unknown')",
  "kernel_version": "$(uname -r)",
  "os_info": "$(lsb_release -ds 2>/dev/null || cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)",
  "files_included": [
    "xray configuration",
    "ssl certificates",
    "service file",
    "client configurations",
    "system settings"
  ]
}
EOF
    
    log_success "Metadata created"
}

# Create compressed archive
create_archive() {
    local backup_path="$1"
    local archive_name="$(basename $backup_path).tar.gz"
    local archive_path="${BACKUP_DIR}/${archive_name}"
    
    log_info "Creating compressed archive..."
    
    cd "$BACKUP_DIR"
    tar -czf "$archive_name" "$(basename $backup_path)"
    rm -rf "$backup_path"
    
    log_success "Archive created: $archive_path"
    
    # Display archive info
    local size=$(du -h "$archive_path" | cut -f1)
    log_info "Archive size: $size"
    
    echo "$archive_path"
}

# Restore from backup
restore_backup() {
    local archive_file="$1"
    
    if [[ ! -f "$archive_file" ]]; then
        log_error "Backup file not found: $archive_file"
        exit 1
    fi
    
    log_info "Restoring from backup: $archive_file"
    
    # Create restore point
    local restore_point="${BACKUP_DIR}/pre-restore-$(date +%Y%m%d-%H%M%S)"
    log_info "Creating restore point: $restore_point"
    
    # Stop service
    log_info "Stopping Xray service..."
    systemctl stop xray || true
    
    # Backup current state
    mkdir -p "$restore_point"
    cp -r "$CONFIG_DIR" "$restore_point/" 2>/dev/null || true
    cp -r "$SSL_DIR" "$restore_point/" 2>/dev/null || true
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$archive_file" -C "$temp_dir"
    
    local backup_dir=$(ls -1 "$temp_dir" | head -1)
    local full_backup_path="$temp_dir/$backup_dir"
    
    # Restore files
    log_info "Restoring configuration..."
    if [[ -d "$full_backup_path/xray" ]]; then
        rm -rf "$CONFIG_DIR"
        cp -r "$full_backup_path/xray" "$CONFIG_DIR"
    fi
    
    log_info "Restoring certificates..."
    if [[ -d "$full_backup_path/ssl" ]]; then
        rm -rf "$SSL_DIR"
        cp -r "$full_backup_path/ssl" "$SSL_DIR"
    fi
    
    log_info "Restoring service file..."
    if [[ -f "$full_backup_path/xray.service" ]]; then
        cp "$full_backup_path/xray.service" /etc/systemd/system/
        systemctl daemon-reload
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
    
    # Start service
    log_info "Starting Xray service..."
    systemctl start xray
    sleep 3
    
    # Verify
    if systemctl is-active --quiet xray; then
        log_success "Restore successful - Service running"
    else
        log_error "Restore failed - Service not running"
        log_info "You can restore from pre-restore backup: $restore_point"
        exit 1
    fi
}

# List backups
list_backups() {
    log_info "Available backups:"
    echo ""
    
    if [[ ! -d "$BACKUP_DIR" ]] || [[ -z $(ls -A "$BACKUP_DIR" 2>/dev/null) ]]; then
        log_warn "No backups found"
        return
    fi
    
    printf "%-30s %-15s %-20s\n" "BACKUP NAME" "SIZE" "CREATED"
    printf "%s\n" "$(printf '%*s' 65 '' | tr ' ' '-')"
    
    for archive in "$BACKUP_DIR"/*.tar.gz; do
        if [[ -f "$archive" ]]; then
            local name=$(basename "$archive")
            local size=$(du -h "$archive" | cut -f1)
            local created=$(stat -c %y "$archive" 2>/dev/null | cut -d' ' -f1 || stat -f %Sm "$archive" 2>/dev/null)
            printf "%-30s %-15s %-20s\n" "$name" "$size" "$created"
        fi
    done
}

# Clean old backups
clean_backups() {
    log_info "Cleaning backups older than $RETENTION_DAYS days..."
    
    local count=0
    while IFS= read -r file; do
        rm -f "$file"
        log_info "Removed: $(basename "$file")"
        ((count++))
    done < <(find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS 2>/dev/null)
    
    if [[ $count -eq 0 ]]; then
        log_info "No old backups to clean"
    else
        log_success "Cleaned $count old backup(s)"
    fi
}

# Main backup function
do_backup() {
    local backup_type="${1:-standard}"
    
    log_info "Starting backup (type: $backup_type)..."
    
    # Create backup directory
    local backup_path=$(create_backup_dir "$backup_type")
    log_info "Backup directory: $backup_path"
    
    # Perform backups
    backup_config "$backup_path"
    backup_certs "$backup_path"
    backup_service "$backup_path"
    backup_clients "$backup_path"
    backup_system "$backup_path"
    create_metadata "$backup_path" "$backup_type"
    
    # Create archive
    local archive_path=$(create_archive "$backup_path")
    
    log_success "Backup completed successfully!"
    log_info "Backup location: $archive_path"
}

# Main
main() {
    local backup_type="standard"
    local restore_file=""
    local list_only=false
    local clean_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--pre-deployment)
                backup_type="pre-deployment"
                shift
                ;;
            -r|--restore)
                restore_file="$2"
                shift 2
                ;;
            -l|--list)
                list_only=true
                shift
                ;;
            -c|--clean)
                clean_only=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
    
    # Execute requested action
    if [[ "$list_only" == true ]]; then
        list_backups
    elif [[ "$clean_only" == true ]]; then
        clean_backups
    elif [[ -n "$restore_file" ]]; then
        restore_backup "$restore_file"
    else
        do_backup "$backup_type"
    fi
}

# Run main
main "$@"
