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

Disk Cleanup - Clean up system disk space by removing unnecessary files

OPTIONS:
    --apt-cache         Clean apt package cache
    --old-kernels       Remove old kernel versions (keep latest 2)
    --journal           Clean old journal logs (keep last 7 days)
    --tmp               Clean /tmp and /var/tmp directories
    --thumbnails        Clean thumbnail cache
    --snap              Remove old snap revisions (keep latest 2)
    --all               Run all cleanup operations
    --analyze           Analyze disk usage without cleaning
    --dry-run           Show what would be done without making changes
    --yes               Skip confirmation prompts (for automation)
    --help              Show this help message

EXAMPLES:
    $0 --analyze
    $0 --apt-cache --dry-run
    $0 --all
    $0 --old-kernels --journal --yes

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

get_size() {
    local path="$1"
    if [ -e "$path" ]; then
        du -sh "$path" 2>/dev/null | cut -f1 || echo "0"
    else
        echo "0"
    fi
}

analyze_disk() {
    log "Analyzing disk usage..."
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    Disk Usage Analysis                        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "📊 Overall Disk Usage:"
    df -h / | tail -1
    echo ""
    
    echo "📦 Apt Cache:"
    local apt_size=$(get_size "/var/cache/apt")
    echo "  /var/cache/apt: $apt_size"
    echo ""
    
    echo "📝 Journal Logs:"
    journalctl --disk-usage 2>/dev/null || echo "  Unable to check journal size"
    echo ""
    
    echo "🗂️  Temporary Files:"
    local tmp_size=$(get_size "/tmp")
    local var_tmp_size=$(get_size "/var/tmp")
    echo "  /tmp: $tmp_size"
    echo "  /var/tmp: $var_tmp_size"
    echo ""
    
    echo "🖼️  Thumbnail Cache:"
    local thumb_size=$(get_size "$HOME/.cache/thumbnails")
    echo "  ~/.cache/thumbnails: $thumb_size"
    echo ""
    
    echo "🧩 Snap Packages:"
    if command -v snap &> /dev/null; then
        snap list --all 2>/dev/null | grep disabled | wc -l | xargs -I {} echo "  Disabled revisions: {}"
    else
        echo "  Snap not installed"
    fi
    echo ""
    
    echo "🐧 Old Kernels:"
    local current_kernel=$(uname -r)
    local kernel_count=$(dpkg -l 'linux-image-*' 2>/dev/null | grep "^ii" | wc -l || echo "0")
    echo "  Current kernel: $current_kernel"
    echo "  Installed kernels: $kernel_count"
    echo ""
    
    log "Disk analysis complete"
}

clean_apt_cache() {
    log "Cleaning apt cache..."
    
    local before_size=$(get_size "/var/cache/apt")
    log "Apt cache size before: $before_size"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would run: apt-get clean && apt-get autoclean"
        return 0
    fi
    
    if ! confirm_action "Clean apt cache?"; then
        return 0
    fi
    
    apt-get clean
    apt-get autoclean -y
    
    local after_size=$(get_size "/var/cache/apt")
    log "Apt cache size after: $after_size"
    log "✅ Apt cache cleaned"
}

clean_old_kernels() {
    log "Cleaning old kernels..."
    
    local current_kernel=$(uname -r)
    log "Current kernel: $current_kernel"
    
    local old_kernels=$(dpkg -l 'linux-image-*' 2>/dev/null | grep "^ii" | awk '{print $2}' | grep -v "$current_kernel" | sort -V | head -n -1)
    
    if [ -z "$old_kernels" ]; then
        log "No old kernels to remove"
        return 0
    fi
    
    local count=$(echo "$old_kernels" | wc -l)
    log "Found $count old kernel(s) to remove"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would remove old kernels:"
        echo "$old_kernels"
        return 0
    fi
    
    if ! confirm_action "Remove $count old kernel(s)?"; then
        return 0
    fi
    
    echo "$old_kernels" | xargs apt-get purge -y
    
    log "✅ Old kernels removed"
}

clean_journal() {
    log "Cleaning journal logs..."
    
    local before_size=$(journalctl --disk-usage 2>/dev/null | grep -oP '\d+\.\d+[A-Z]+' | head -1 || echo "unknown")
    log "Journal size before: $before_size"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would run: journalctl --vacuum-time=7d"
        return 0
    fi
    
    if ! confirm_action "Clean journal logs (keep last 7 days)?"; then
        return 0
    fi
    
    journalctl --vacuum-time=7d
    
    local after_size=$(journalctl --disk-usage 2>/dev/null | grep -oP '\d+\.\d+[A-Z]+' | head -1 || echo "unknown")
    log "Journal size after: $after_size"
    log "✅ Journal logs cleaned"
}

clean_tmp() {
    log "Cleaning temporary directories..."
    
    local tmp_size=$(get_size "/tmp")
    local var_tmp_size=$(get_size "/var/tmp")
    log "Temporary files size: /tmp=$tmp_size, /var/tmp=$var_tmp_size"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would clean /tmp and /var/tmp (files older than 7 days)"
        return 0
    fi
    
    if ! confirm_action "Clean temporary files older than 7 days?"; then
        return 0
    fi
    
    find /tmp -type f -atime +7 -delete 2>/dev/null || log "Warning: Some files in /tmp could not be deleted"
    find /var/tmp -type f -atime +7 -delete 2>/dev/null || log "Warning: Some files in /var/tmp could not be deleted"
    
    log "✅ Temporary directories cleaned"
}

clean_thumbnails() {
    log "Cleaning thumbnail cache..."
    
    local thumb_dir="$HOME/.cache/thumbnails"
    
    if [ ! -d "$thumb_dir" ]; then
        log "Thumbnail cache directory not found"
        return 0
    fi
    
    local before_size=$(get_size "$thumb_dir")
    log "Thumbnail cache size before: $before_size"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would remove: $thumb_dir"
        return 0
    fi
    
    if ! confirm_action "Clean thumbnail cache?"; then
        return 0
    fi
    
    rm -rf "$thumb_dir"
    
    log "✅ Thumbnail cache cleaned"
}

clean_snap() {
    log "Cleaning old snap revisions..."
    
    if ! command -v snap &> /dev/null; then
        log "Snap not installed, skipping"
        return 0
    fi
    
    local disabled_snaps=$(snap list --all 2>/dev/null | grep disabled | awk '{print $1, $3}')
    
    if [ -z "$disabled_snaps" ]; then
        log "No disabled snap revisions to remove"
        return 0
    fi
    
    local count=$(echo "$disabled_snaps" | wc -l)
    log "Found $count disabled snap revision(s)"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would remove disabled snap revisions:"
        echo "$disabled_snaps"
        return 0
    fi
    
    if ! confirm_action "Remove $count disabled snap revision(s)?"; then
        return 0
    fi
    
    echo "$disabled_snaps" | while read -r snapname revision; do
        snap remove "$snapname" --revision="$revision"
    done
    
    log "✅ Snap revisions cleaned"
}

clean_all() {
    log "Running comprehensive disk cleanup..."
    
    clean_apt_cache
    clean_journal
    clean_tmp
    clean_thumbnails
    clean_old_kernels
    clean_snap
    
    log "✅ Comprehensive disk cleanup complete"
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
            --apt-cache|--old-kernels|--journal|--tmp|--thumbnails|--snap|--all|--analyze)
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
            --apt-cache)
                check_root
                clean_apt_cache
                action_taken=true
                ;;
            --old-kernels)
                check_root
                clean_old_kernels
                action_taken=true
                ;;
            --journal)
                check_root
                clean_journal
                action_taken=true
                ;;
            --tmp)
                check_root
                clean_tmp
                action_taken=true
                ;;
            --thumbnails)
                clean_thumbnails
                action_taken=true
                ;;
            --snap)
                check_root
                clean_snap
                action_taken=true
                ;;
            --all)
                check_root
                clean_all
                action_taken=true
                ;;
            --analyze)
                analyze_disk
                action_taken=true
                ;;
        esac
    done
    
    if [ "$action_taken" = false ]; then
        error "No action specified. Use --help for usage information"
    fi
    
    log "Disk cleanup complete"
}

main "$@"
