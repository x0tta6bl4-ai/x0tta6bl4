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

Automated Maintenance - Set up automated system maintenance tasks

OPTIONS:
    --setup-timers      Create systemd timers for automated cleanup
    --setup-cron        Create cron jobs for automated cleanup
    --setup-monitor     Set up disk usage monitoring with alerts
    --remove-timers     Remove systemd timers
    --remove-cron       Remove cron jobs
    --list              List all automated maintenance tasks
    --test              Test maintenance scripts
    --help              Show this help message

EXAMPLES:
    $0 --setup-timers
    $0 --setup-cron
    $0 --setup-monitor
    $0 --list
    $0 --test

EOF
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root (use sudo)"
    fi
}

setup_systemd_timers() {
    log "Setting up systemd timers for automated maintenance..."
    
    check_root
    
    local timer_dir="/etc/systemd/system"
    
    cat > "$timer_dir/disk-cleanup.service" << 'EOF'
[Unit]
Description=Weekly disk cleanup
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'if [ -x /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/disk_cleanup.sh ]; then /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/disk_cleanup.sh --apt-cache --journal --tmp --yes; fi'
EOF
    
    cat > "$timer_dir/disk-cleanup.timer" << 'EOF'
[Unit]
Description=Weekly disk cleanup timer
Requires=disk-cleanup.service

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    cat > "$timer_dir/docker-cleanup.service" << 'EOF'
[Unit]
Description=Weekly Docker cleanup
After=docker.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'if [ -x /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/docker_optimizer.sh ]; then /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/docker_optimizer.sh --clean-images --clean-containers --yes; fi'
EOF
    
    cat > "$timer_dir/docker-cleanup.timer" << 'EOF'
[Unit]
Description=Weekly Docker cleanup timer
Requires=docker-cleanup.service

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    systemctl daemon-reload
    systemctl enable disk-cleanup.timer
    systemctl enable docker-cleanup.timer
    systemctl start disk-cleanup.timer
    systemctl start docker-cleanup.timer
    
    log "✅ Systemd timers created and enabled"
    log "   - disk-cleanup.timer (weekly)"
    log "   - docker-cleanup.timer (weekly)"
}

setup_cron_jobs() {
    log "Setting up cron jobs for automated maintenance..."
    
    check_root
    
    local cron_file="/etc/cron.d/system-optimization"
    
    cat > "$cron_file" << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

0 2 * * 0 root [ -x /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/disk_cleanup.sh ] && /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/disk_cleanup.sh --apt-cache --journal --tmp --yes >> /var/log/optimization.log 2>&1

0 3 * * 0 root [ -x /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/docker_optimizer.sh ] && /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/docker_optimizer.sh --clean-images --clean-containers --yes >> /var/log/optimization.log 2>&1

0 4 1 * * root [ -x /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/disk_cleanup.sh ] && /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/disk_cleanup.sh --old-kernels --yes >> /var/log/optimization.log 2>&1

0 */6 * * * root /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559/scripts/optimization/automated_maintenance.sh --check-disk >> /var/log/optimization.log 2>&1
EOF
    
    chmod 644 "$cron_file"
    
    log "✅ Cron jobs created:"
    log "   - Weekly disk cleanup (Sunday 2 AM)"
    log "   - Weekly Docker cleanup (Sunday 3 AM)"
    log "   - Monthly kernel cleanup (1st day, 4 AM)"
    log "   - Disk monitoring (every 6 hours)"
}

setup_disk_monitor() {
    log "Setting up disk usage monitoring..."
    
    check_root
    
    local monitor_script="/usr/local/bin/check-disk-usage"
    
    cat > "$monitor_script" << 'EOF'
#!/bin/bash

THRESHOLD=85
USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "⚠️  WARNING: Disk usage is ${USAGE}% (threshold: ${THRESHOLD}%)" | systemd-cat -t disk-monitor -p warning
    
    if command -v notify-send &> /dev/null; then
        notify-send "Disk Usage Alert" "Disk usage is ${USAGE}%. Consider running cleanup." -u critical
    fi
fi
EOF
    
    chmod +x "$monitor_script"
    
    log "✅ Disk monitoring script created at $monitor_script"
}

remove_systemd_timers() {
    log "Removing systemd timers..."
    
    check_root
    
    systemctl stop disk-cleanup.timer 2>/dev/null || true
    systemctl stop docker-cleanup.timer 2>/dev/null || true
    systemctl disable disk-cleanup.timer 2>/dev/null || true
    systemctl disable docker-cleanup.timer 2>/dev/null || true
    
    rm -f /etc/systemd/system/disk-cleanup.service
    rm -f /etc/systemd/system/disk-cleanup.timer
    rm -f /etc/systemd/system/docker-cleanup.service
    rm -f /etc/systemd/system/docker-cleanup.timer
    
    systemctl daemon-reload
    
    log "✅ Systemd timers removed"
}

remove_cron_jobs() {
    log "Removing cron jobs..."
    
    check_root
    
    rm -f /etc/cron.d/system-optimization
    
    log "✅ Cron jobs removed"
}

list_maintenance_tasks() {
    log "Listing automated maintenance tasks..."
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              Automated Maintenance Tasks                      ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "📅 SYSTEMD TIMERS:"
    if systemctl list-timers disk-cleanup.timer &>/dev/null; then
        systemctl list-timers disk-cleanup.timer --no-pager
    else
        echo "  disk-cleanup.timer: NOT INSTALLED"
    fi
    
    if systemctl list-timers docker-cleanup.timer &>/dev/null; then
        systemctl list-timers docker-cleanup.timer --no-pager
    else
        echo "  docker-cleanup.timer: NOT INSTALLED"
    fi
    echo ""
    
    echo "📅 CRON JOBS:"
    if [ -f /etc/cron.d/system-optimization ]; then
        echo "  /etc/cron.d/system-optimization: INSTALLED"
        cat /etc/cron.d/system-optimization
    else
        echo "  /etc/cron.d/system-optimization: NOT INSTALLED"
    fi
    echo ""
    
    echo "📊 DISK MONITOR:"
    if [ -x /usr/local/bin/check-disk-usage ]; then
        echo "  /usr/local/bin/check-disk-usage: INSTALLED"
    else
        echo "  /usr/local/bin/check-disk-usage: NOT INSTALLED"
    fi
    echo ""
}

test_maintenance() {
    log "Testing maintenance scripts..."
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              Maintenance Scripts Test                         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    local scripts=(
        "system_analyzer.sh"
        "git_fix.sh"
        "docker_optimizer.sh"
        "disk_cleanup.sh"
        "services_optimizer.sh"
    )
    
    for script in "${scripts[@]}"; do
        local script_path="$SCRIPT_DIR/$script"
        
        if [ -x "$script_path" ]; then
            echo "✅ $script: EXECUTABLE"
            
            if "$script_path" --help &>/dev/null; then
                echo "   --help works"
            else
                echo "   ⚠️  --help failed"
            fi
        else
            echo "❌ $script: NOT FOUND or NOT EXECUTABLE"
        fi
    done
    echo ""
    
    log "Maintenance scripts test complete"
}

check_disk() {
    local threshold=85
    local usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [ "$usage" -gt "$threshold" ]; then
        log "⚠️  WARNING: Disk usage is ${usage}% (threshold: ${threshold}%)"
        return 1
    else
        log "✅ Disk usage is ${usage}% (healthy)"
        return 0
    fi
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 1
    fi
    
    case "$1" in
        --setup-timers)
            setup_systemd_timers
            ;;
        --setup-cron)
            setup_cron_jobs
            ;;
        --setup-monitor)
            setup_disk_monitor
            ;;
        --remove-timers)
            remove_systemd_timers
            ;;
        --remove-cron)
            remove_cron_jobs
            ;;
        --list)
            list_maintenance_tasks
            ;;
        --test)
            test_maintenance
            ;;
        --check-disk)
            check_disk
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
