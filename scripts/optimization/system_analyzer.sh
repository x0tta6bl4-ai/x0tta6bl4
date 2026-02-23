#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${HOME}/optimization.log"
SNAPSHOT_DIR="${HOME}/.system_snapshots"

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

System Analyzer - Collect system state metrics for before/after comparison

OPTIONS:
    --snapshot <name>       Create a snapshot with given name (e.g., 'before', 'after')
    --compare <name1> <name2>  Compare two snapshots
    --list                  List all available snapshots
    --help                  Show this help message

EXAMPLES:
    $0 --snapshot before
    $0 --snapshot after
    $0 --compare before after
    $0 --list

EOF
}

create_snapshot() {
    local name="$1"
    mkdir -p "$SNAPSHOT_DIR"
    
    local snapshot_file="${SNAPSHOT_DIR}/${name}_$(date +%Y%m%d_%H%M%S).json"
    
    log "Creating system snapshot: $name"
    log "Snapshot file: $snapshot_file"
    
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    local disk_used=$(df / | tail -1 | awk '{print $3}')
    local disk_avail=$(df / | tail -1 | awk '{print $4}')
    local disk_total=$(df / | tail -1 | awk '{print $2}')
    
    local docker_images_count=0
    local docker_images_size=0
    local docker_volumes_count=0
    local docker_volumes_size=0
    local docker_containers_count=0
    
    if command -v docker &> /dev/null; then
        docker_images_count=$(docker images -q | wc -l)
        docker_images_size=$(docker system df -v 2>/dev/null | grep "Images space usage" | awk '{print $4}' || echo "0")
        docker_volumes_count=$(docker volume ls -q | wc -l)
        docker_volumes_size=$(docker system df -v 2>/dev/null | grep "Local Volumes space usage" | awk '{print $4}' || echo "0")
        docker_containers_count=$(docker ps -a -q | wc -l)
    fi
    
    local journal_size=$(journalctl --disk-usage 2>/dev/null | grep -oP '\d+\.\d+[A-Z]+' | head -1 || echo "0")
    
    local boot_time=""
    if command -v systemd-analyze &> /dev/null; then
        boot_time=$(systemd-analyze time 2>/dev/null | grep "Overall" | awk '{print $4}' || echo "N/A")
    fi
    
    local slow_services_count=$(systemd-analyze blame 2>/dev/null | awk '$1 ~ /s$/ && $1+0 > 1' | wc -l || echo "0")
    
    local ram_total=$(free -h | grep "Mem:" | awk '{print $2}')
    local ram_used=$(free -h | grep "Mem:" | awk '{print $3}')
    local ram_avail=$(free -h | grep "Mem:" | awk '{print $7}')
    
    local cpu_cores=$(nproc)
    local cpu_model=$(lscpu | grep "Model name" | cut -d: -f2 | xargs)
    
    cat > "$snapshot_file" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "name": "$name",
  "disk": {
    "usage_percent": $disk_usage,
    "used_kb": $disk_used,
    "available_kb": $disk_avail,
    "total_kb": $disk_total
  },
  "docker": {
    "images_count": $docker_images_count,
    "images_size": "$docker_images_size",
    "volumes_count": $docker_volumes_count,
    "volumes_size": "$docker_volumes_size",
    "containers_count": $docker_containers_count
  },
  "system": {
    "journal_size": "$journal_size",
    "boot_time": "$boot_time",
    "slow_services_count": $slow_services_count,
    "ram_total": "$ram_total",
    "ram_used": "$ram_used",
    "ram_available": "$ram_avail",
    "cpu_cores": $cpu_cores,
    "cpu_model": "$cpu_model"
  }
}
EOF
    
    log "Snapshot created successfully: $snapshot_file"
    echo "$snapshot_file"
}

list_snapshots() {
    log "Available snapshots:"
    
    if [ ! -d "$SNAPSHOT_DIR" ]; then
        log "No snapshots found"
        return
    fi
    
    local snapshots=$(find "$SNAPSHOT_DIR" -name "*.json" -type f | sort)
    
    if [ -z "$snapshots" ]; then
        log "No snapshots found"
        return
    fi
    
    echo "$snapshots" | while read -r snapshot; do
        local name=$(basename "$snapshot" | sed 's/_[0-9]*\.json$//')
        local timestamp=$(jq -r '.timestamp' "$snapshot" 2>/dev/null || echo "N/A")
        echo "  - $name ($timestamp): $snapshot"
    done
}

compare_snapshots() {
    local name1="$1"
    local name2="$2"
    
    local snapshot1=$(find "$SNAPSHOT_DIR" -name "${name1}_*.json" -type f | sort | tail -1)
    local snapshot2=$(find "$SNAPSHOT_DIR" -name "${name2}_*.json" -type f | sort | tail -1)
    
    if [ -z "$snapshot1" ]; then
        error "Snapshot not found: $name1"
    fi
    
    if [ -z "$snapshot2" ]; then
        error "Snapshot not found: $name2"
    fi
    
    log "Comparing snapshots: $name1 vs $name2"
    log "Snapshot 1: $snapshot1"
    log "Snapshot 2: $snapshot2"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              System Optimization Comparison Report            ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    local disk1_usage=$(jq -r '.disk.usage_percent' "$snapshot1")
    local disk2_usage=$(jq -r '.disk.usage_percent' "$snapshot2")
    local disk_diff=$((disk1_usage - disk2_usage))
    
    local disk1_used=$(jq -r '.disk.used_kb' "$snapshot1")
    local disk2_used=$(jq -r '.disk.used_kb' "$snapshot2")
    local disk_freed=$(awk "BEGIN {printf \"%.2f\", ($disk1_used - $disk2_used) / 1024 / 1024}")
    
    echo "📊 DISK USAGE:"
    echo "  Before: ${disk1_usage}%"
    echo "  After:  ${disk2_usage}%"
    if [ "$disk_diff" -gt 0 ]; then
        echo "  ✅ Freed: ${disk_diff}% (${disk_freed} GB)"
    else
        echo "  ⚠️  Increased: $((disk_diff * -1))% (${disk_freed} GB)"
    fi
    echo ""
    
    local docker1_images=$(jq -r '.docker.images_count' "$snapshot1")
    local docker2_images=$(jq -r '.docker.images_count' "$snapshot2")
    local docker_images_diff=$((docker1_images - docker2_images))
    
    local docker1_volumes=$(jq -r '.docker.volumes_count' "$snapshot1")
    local docker2_volumes=$(jq -r '.docker.volumes_count' "$snapshot2")
    local docker_volumes_diff=$((docker1_volumes - docker2_volumes))
    
    echo "🐳 DOCKER:"
    echo "  Images:  $docker1_images → $docker2_images (removed: $docker_images_diff)"
    echo "  Volumes: $docker1_volumes → $docker2_volumes (removed: $docker_volumes_diff)"
    echo ""
    
    local journal1=$(jq -r '.system.journal_size' "$snapshot1")
    local journal2=$(jq -r '.system.journal_size' "$snapshot2")
    
    echo "📝 SYSTEM:"
    echo "  Journal: $journal1 → $journal2"
    
    local boot1=$(jq -r '.system.boot_time' "$snapshot1")
    local boot2=$(jq -r '.system.boot_time' "$snapshot2")
    echo "  Boot time: $boot1 → $boot2"
    
    local slow1=$(jq -r '.system.slow_services_count' "$snapshot1")
    local slow2=$(jq -r '.system.slow_services_count' "$snapshot2")
    echo "  Slow services (>1s): $slow1 → $slow2"
    echo ""
    
    if [ "$disk2_usage" -lt 70 ] && [ "$disk_diff" -gt 0 ]; then
        echo "✅ SUCCESS: Disk usage is below 70% and space has been freed"
    elif [ "$disk2_usage" -lt 70 ]; then
        echo "✅ SUCCESS: Disk usage is below 70%"
    elif [ "$disk_diff" -gt 0 ]; then
        echo "⚠️  PARTIAL: Space has been freed but disk usage is still above 70%"
    else
        echo "❌ FAILURE: Disk usage has not improved"
    fi
    echo ""
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    case "$1" in
        --snapshot)
            if [ -z "${2:-}" ]; then
                error "Snapshot name required"
            fi
            create_snapshot "$2"
            ;;
        --compare)
            if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
                error "Two snapshot names required for comparison"
            fi
            compare_snapshots "$2" "$3"
            ;;
        --list)
            list_snapshots
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
}

main "$@"
