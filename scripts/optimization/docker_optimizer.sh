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

Docker Optimizer - Clean up Docker images, volumes, containers, and build cache

OPTIONS:
    --analyze           Analyze Docker disk usage without making changes
    --clean-images      Remove unused and dangling images
    --clean-volumes     Remove unused volumes
    --clean-containers  Remove stopped containers
    --clean-cache       Remove build cache
    --clean-all         Remove all unused Docker resources (combines all above)
    --prune-all         Run 'docker system prune -a --volumes' (DESTRUCTIVE!)
    --setup-log-rotation  Configure Docker log rotation
    --dry-run           Show what would be done without making changes
    --yes               Skip confirmation prompts (for automation)
    --help              Show this help message

EXAMPLES:
    $0 --analyze
    $0 --clean-images --dry-run
    $0 --clean-all
    $0 --prune-all --yes
    $0 --setup-log-rotation

EOF
}

DRY_RUN=false
SKIP_CONFIRM=false

check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    if ! docker ps &> /dev/null; then
        error "Cannot connect to Docker daemon. Is it running?"
    fi
}

analyze_docker() {
    log "Analyzing Docker disk usage..."
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    Docker Disk Usage Analysis                 ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    docker system df -v
    
    echo ""
    log "Docker analysis complete"
    
    local images_count=$(docker images -q | wc -l)
    local dangling_images=$(docker images -f "dangling=true" -q | wc -l)
    local volumes_count=$(docker volume ls -q | wc -l)
    local containers_stopped=$(docker ps -a -q -f status=exited | wc -l)
    
    echo ""
    echo "Summary:"
    echo "  Total images:        $images_count"
    echo "  Dangling images:     $dangling_images"
    echo "  Total volumes:       $volumes_count"
    echo "  Stopped containers:  $containers_stopped"
    echo ""
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
        exit 0
    fi
}

clean_images() {
    log "Cleaning Docker images..."
    
    local dangling_count=$(docker images -f "dangling=true" -q | wc -l)
    local unused_count=$(docker images | grep -v "REPOSITORY" | wc -l)
    
    if [ "$dangling_count" -eq 0 ]; then
        log "No dangling images to remove"
    else
        log "Found $dangling_count dangling images"
        
        if [ "$DRY_RUN" = true ]; then
            log "[DRY-RUN] Would remove dangling images"
            docker images -f "dangling=true"
        else
            confirm_action "Remove $dangling_count dangling images?"
            docker rmi $(docker images -f "dangling=true" -q) 2>/dev/null || log "No dangling images removed"
            log "✅ Dangling images removed"
        fi
    fi
    
    log "Removing unused images..."
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would run: docker image prune -a"
        docker images
    else
        confirm_action "Remove all unused images (not used by any container)?"
        docker image prune -a -f
        log "✅ Unused images removed"
    fi
}

clean_volumes() {
    log "Cleaning Docker volumes..."
    
    local volumes_count=$(docker volume ls -q | wc -l)
    local dangling_volumes=$(docker volume ls -f "dangling=true" -q | wc -l)
    
    if [ "$volumes_count" -eq 0 ]; then
        log "No volumes found"
        return 0
    fi
    
    log "Found $volumes_count total volumes, $dangling_volumes dangling"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would remove unused volumes"
        docker volume ls -f "dangling=true"
    else
        confirm_action "Remove $dangling_volumes unused volumes?"
        docker volume prune -f
        log "✅ Unused volumes removed"
    fi
}

clean_containers() {
    log "Cleaning Docker containers..."
    
    local stopped_count=$(docker ps -a -q -f status=exited | wc -l)
    
    if [ "$stopped_count" -eq 0 ]; then
        log "No stopped containers to remove"
        return 0
    fi
    
    log "Found $stopped_count stopped containers"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would remove stopped containers"
        docker ps -a -f status=exited
    else
        confirm_action "Remove $stopped_count stopped containers?"
        docker container prune -f
        log "✅ Stopped containers removed"
    fi
}

clean_cache() {
    log "Cleaning Docker build cache..."
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would run: docker builder prune -a"
        docker builder du
    else
        confirm_action "Remove all build cache?"
        docker builder prune -a -f
        log "✅ Build cache removed"
    fi
}

clean_all() {
    log "Running comprehensive Docker cleanup..."
    
    clean_containers
    clean_images
    clean_volumes
    clean_cache
    
    log "✅ Comprehensive cleanup complete"
}

prune_all() {
    log "Running docker system prune -a --volumes..."
    log "⚠️  WARNING: This will remove ALL unused Docker resources!"
    
    if [ "$DRY_RUN" = true ]; then
        log "[DRY-RUN] Would run: docker system prune -a --volumes -f"
        analyze_docker
        return 0
    fi
    
    confirm_action "⚠️  Are you SURE you want to remove ALL unused Docker resources (images, volumes, networks, cache)?"
    
    docker system prune -a --volumes -f
    
    log "✅ Docker system prune complete"
}

setup_log_rotation() {
    log "Setting up Docker log rotation..."
    
    local docker_config="/etc/docker/daemon.json"
    local backup_config="/etc/docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)"
    
    if [ ! -f "$docker_config" ]; then
        log "Creating new Docker daemon configuration"
        
        if [ "$DRY_RUN" = true ]; then
            log "[DRY-RUN] Would create $docker_config with log rotation settings"
            return 0
        fi
        
        sudo tee "$docker_config" > /dev/null << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
        log "✅ Docker daemon configuration created"
    else
        log "Backing up existing configuration to $backup_config"
        
        if [ "$DRY_RUN" = true ]; then
            log "[DRY-RUN] Would backup and update $docker_config"
            return 0
        fi
        
        sudo cp "$docker_config" "$backup_config"
        
        if grep -q "log-driver" "$docker_config"; then
            log "Log rotation already configured"
            return 0
        fi
        
        log "Adding log rotation to existing configuration"
        
        sudo tee "$docker_config" > /dev/null << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
        
        log "✅ Docker daemon configuration updated"
    fi
    
    log "⚠️  You need to restart Docker daemon for changes to take effect"
    log "Run: sudo systemctl restart docker"
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    check_docker
    
    local action_taken=false
    local actions_to_run=()
    
    while [ $# -gt 0 ]; do
        case "$1" in
            --analyze|--clean-images|--clean-volumes|--clean-containers|--clean-cache|--clean-all|--prune-all|--setup-log-rotation)
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
                analyze_docker
                action_taken=true
                ;;
            --clean-images)
                clean_images
                action_taken=true
                ;;
            --clean-volumes)
                clean_volumes
                action_taken=true
                ;;
            --clean-containers)
                clean_containers
                action_taken=true
                ;;
            --clean-cache)
                clean_cache
                action_taken=true
                ;;
            --clean-all)
                clean_all
                action_taken=true
                ;;
            --prune-all)
                prune_all
                action_taken=true
                ;;
            --setup-log-rotation)
                setup_log_rotation
                action_taken=true
                ;;
        esac
    done
    
    if [ "$action_taken" = false ]; then
        error "No action specified. Use --help for usage information"
    fi
    
    log "Docker optimization complete"
}

main "$@"
