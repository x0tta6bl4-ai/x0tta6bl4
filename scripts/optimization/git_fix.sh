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

Git Configuration Fixer - Fix 'dubious ownership' errors by adding repositories to safe.directory

OPTIONS:
    --auto              Automatically find and fix all Git repositories in HOME
    --add <path>        Add specific repository to safe.directory
    --list              List all safe.directory entries
    --dry-run           Show what would be done without making changes
    --help              Show this help message

EXAMPLES:
    $0 --auto
    $0 --add /home/user/project
    $0 --list
    $0 --auto --dry-run

EOF
}

DRY_RUN=false

add_safe_directory() {
    local repo_path="$1"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would add to safe.directory: $repo_path"
        return 0
    fi
    
    if git config --global --get-all safe.directory | grep -q "^${repo_path}$"; then
        log "Already in safe.directory: $repo_path"
        return 0
    fi
    
    log "Adding to safe.directory: $repo_path"
    git config --global --add safe.directory "$repo_path"
    
    if [ $? -eq 0 ]; then
        log "✅ Successfully added: $repo_path"
    else
        log "❌ Failed to add: $repo_path"
        return 1
    fi
}

find_and_fix_all() {
    log "Searching for Git repositories in HOME directory..."
    
    local repos=$(find "$HOME" -name ".git" -type d 2>/dev/null)
    local count=0
    local fixed=0
    local skipped=0
    
    if [ -z "$repos" ]; then
        log "No Git repositories found"
        return 0
    fi
    
    echo "$repos" | while read -r git_dir; do
        local repo_path=$(dirname "$git_dir")
        count=$((count + 1))
        
        log "Found repository: $repo_path"
        
        cd "$repo_path" || continue
        
        if git status &>/dev/null; then
            log "✅ Repository OK: $repo_path"
            skipped=$((skipped + 1))
        else
            log "⚠️  Repository has issues: $repo_path"
            if add_safe_directory "$repo_path"; then
                fixed=$((fixed + 1))
            fi
        fi
    done
    
    log "Summary: Found $count repositories, Fixed $fixed, Skipped $skipped"
}

list_safe_directories() {
    log "Listing all safe.directory entries:"
    
    local entries=$(git config --global --get-all safe.directory 2>/dev/null || true)
    
    if [ -z "$entries" ]; then
        log "No safe.directory entries found"
        return 0
    fi
    
    echo "$entries" | while read -r entry; do
        echo "  - $entry"
    done
}

fix_zenflow_worktrees() {
    log "Fixing zenflow worktrees..."
    
    local zenflow_dir="${HOME}/.zenflow/worktrees"
    
    if [ ! -d "$zenflow_dir" ]; then
        log "Zenflow worktrees directory not found: $zenflow_dir"
        return 0
    fi
    
    local repos=$(find "$zenflow_dir" -maxdepth 2 -name ".git" -type d 2>/dev/null)
    
    if [ -z "$repos" ]; then
        log "No zenflow repositories found"
        return 0
    fi
    
    echo "$repos" | while read -r git_dir; do
        local repo_path=$(dirname "$git_dir")
        log "Fixing zenflow repository: $repo_path"
        add_safe_directory "$repo_path"
    done
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    while [ $# -gt 0 ]; do
        case "$1" in
            --auto)
                fix_zenflow_worktrees
                find_and_fix_all
                ;;
            --add)
                if [ -z "${2:-}" ]; then
                    error "Repository path required for --add"
                fi
                add_safe_directory "$2"
                shift
                ;;
            --list)
                list_safe_directories
                ;;
            --dry-run)
                DRY_RUN=true
                log "DRY-RUN MODE ENABLED"
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
}

main "$@"
