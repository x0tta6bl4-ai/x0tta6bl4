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
╔════════════════════════════════════════════════════════════════╗
║           Ubuntu System Optimization Master Script            ║
║                        Version 1.0                             ║
╚════════════════════════════════════════════════════════════════╝

Usage: $0 [OPTIONS]

Master orchestrator for Ubuntu system optimization

OPTIONS:
    --analyze           Analyze system state (non-destructive)
    --p0                Run P0 critical optimizations (disk cleanup, Docker, git fix)
    --p1                Run P1 optimizations (services, boot time)
    --all               Run all optimizations (P0 + P1)
    --setup-automation  Set up automated maintenance (timers/cron)
    --dry-run           Show what would be done without making changes
    --yes               Skip all confirmation prompts (for automation)
    --help              Show this help message

OPTIMIZATION PHASES:
    P0 (Critical - MUST DO):
      • Clean Docker (free ~10-15GB)
      • Clean apt cache (free ~1-2GB)
      • Clean journal logs (free ~400MB)
      • Fix git safe.directory errors
      • Remove old kernels (free ~1-2GB)

    P1 (High Priority - RECOMMENDED):
      • Optimize systemd services
      • Reduce boot time by 50%+
      • Set up automated maintenance

EXAMPLES:
    # Analyze current state
    $0 --analyze

    # Run critical optimizations with confirmation
    sudo $0 --p0

    # Run all optimizations without prompts
    sudo $0 --all --yes

    # Dry-run to see what would be done
    sudo $0 --all --dry-run

    # Set up automated maintenance
    sudo $0 --setup-automation

WORKFLOW:
    1. Run --analyze to see current state
    2. Create system snapshot (recommended)
    3. Run --p0 to free critical disk space
    4. Run --p1 to optimize system performance
    5. Run --setup-automation for ongoing maintenance

REQUIREMENTS:
    • Root access (sudo) for most operations
    • At least 5GB free space for operations
    • Docker installed (for Docker cleanup)

EOF
}

DRY_RUN=""
SKIP_CONFIRM=""

check_requirements() {
    log "Checking requirements..."
    
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root (use sudo)"
    fi
    
    local required_scripts=(
        "system_analyzer.sh"
        "git_fix.sh"
        "docker_optimizer.sh"
        "disk_cleanup.sh"
        "services_optimizer.sh"
        "automated_maintenance.sh"
    )
    
    for script in "${required_scripts[@]}"; do
        if [ ! -x "$SCRIPT_DIR/$script" ]; then
            error "Required script not found or not executable: $script"
        fi
    done
    
    log "✅ All requirements met"
}

run_analysis() {
    log "======================================"
    log "PHASE: System Analysis"
    log "======================================"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                    System Analysis Report                     ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    "$SCRIPT_DIR/system_analyzer.sh" --snapshot "analysis"
    
    echo ""
    echo "📊 Current System State:"
    df -h / | tail -1
    echo ""
    
    if command -v docker &> /dev/null; then
        echo "🐳 Docker Resources:"
        docker system df 2>/dev/null || echo "  Docker daemon not running"
        echo ""
    fi
    
    echo "📝 Journal Size:"
    journalctl --disk-usage 2>/dev/null || echo "  Unable to check"
    echo ""
    
    echo "⏱️  Boot Time:"
    systemd-analyze time 2>/dev/null || echo "  Unable to check"
    echo ""
    
    log "✅ Analysis complete"
}

run_p0_optimizations() {
    log "======================================"
    log "PHASE: P0 Critical Optimizations"
    log "======================================"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║              P0: Critical Optimizations                       ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    log "Creating 'before' snapshot..."
    "$SCRIPT_DIR/system_analyzer.sh" --snapshot "before"
    
    log "Step 1/5: Fixing git safe.directory issues..."
    "$SCRIPT_DIR/git_fix.sh" --auto $DRY_RUN || log "Warning: git_fix had issues"
    
    log "Step 2/5: Cleaning Docker resources..."
    if command -v docker &> /dev/null; then
        "$SCRIPT_DIR/docker_optimizer.sh" --clean-all $DRY_RUN $SKIP_CONFIRM || log "Warning: docker_optimizer had issues"
    else
        log "Docker not installed, skipping"
    fi
    
    log "Step 3/5: Cleaning system disk..."
    "$SCRIPT_DIR/disk_cleanup.sh" --apt-cache --journal --tmp $DRY_RUN $SKIP_CONFIRM || log "Warning: disk_cleanup had issues"
    
    log "Step 4/5: Removing old kernels..."
    "$SCRIPT_DIR/disk_cleanup.sh" --old-kernels $DRY_RUN $SKIP_CONFIRM || log "Warning: kernel cleanup had issues"
    
    log "Step 5/5: Cleaning thumbnails cache..."
    "$SCRIPT_DIR/disk_cleanup.sh" --thumbnails $DRY_RUN $SKIP_CONFIRM || log "Warning: thumbnails cleanup had issues"
    
    log "Creating 'after-p0' snapshot..."
    "$SCRIPT_DIR/system_analyzer.sh" --snapshot "after-p0"
    
    echo ""
    log "✅ P0 optimizations complete"
    
    echo ""
    echo "📊 P0 Results:"
    "$SCRIPT_DIR/system_analyzer.sh" --compare "before" "after-p0"
    echo ""
}

run_p1_optimizations() {
    log "======================================"
    log "PHASE: P1 High Priority Optimizations"
    log "======================================"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║           P1: High Priority Optimizations                     ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    log "Analyzing boot time..."
    "$SCRIPT_DIR/services_optimizer.sh" --analyze || log "Warning: services analysis had issues"
    
    log "Optimizing systemd services..."
    "$SCRIPT_DIR/services_optimizer.sh" --optimize-boot $DRY_RUN $SKIP_CONFIRM || log "Warning: services optimization had issues"
    
    log "Setting up Docker log rotation..."
    if command -v docker &> /dev/null; then
        "$SCRIPT_DIR/docker_optimizer.sh" --setup-log-rotation $DRY_RUN || log "Warning: Docker log rotation setup had issues"
    fi
    
    log "Creating 'after-p1' snapshot..."
    "$SCRIPT_DIR/system_analyzer.sh" --snapshot "after-p1"
    
    echo ""
    log "✅ P1 optimizations complete"
    log "⚠️  NOTE: Reboot required for full effect"
    echo ""
}

setup_automation() {
    log "======================================"
    log "PHASE: Automated Maintenance Setup"
    log "======================================"
    
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║            Automated Maintenance Setup                        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    log "Setting up systemd timers..."
    "$SCRIPT_DIR/automated_maintenance.sh" --setup-timers || log "Warning: timer setup had issues"
    
    log "Setting up disk monitoring..."
    "$SCRIPT_DIR/automated_maintenance.sh" --setup-monitor || log "Warning: monitor setup had issues"
    
    log "Testing maintenance scripts..."
    "$SCRIPT_DIR/automated_maintenance.sh" --test
    
    echo ""
    log "✅ Automated maintenance configured"
    log "   - Weekly disk cleanup (systemd timer)"
    log "   - Weekly Docker cleanup (systemd timer)"
    log "   - Disk usage monitoring (every 6 hours)"
    echo ""
}

print_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                  Optimization Summary                         ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "✅ Optimization Complete!"
    echo ""
    echo "📊 Final System State:"
    df -h / | tail -1
    echo ""
    
    echo "📝 Log File: $LOG_FILE"
    echo ""
    
    if [ -d "$HOME/.system_snapshots" ]; then
        echo "📸 Snapshots saved to: $HOME/.system_snapshots"
        "$SCRIPT_DIR/system_analyzer.sh" --list
        echo ""
    fi
    
    echo "🔄 Next Steps:"
    echo "  1. Review the logs: cat $LOG_FILE"
    echo "  2. Reboot system for full effect: sudo reboot"
    echo "  3. After reboot, check boot time: systemd-analyze time"
    echo "  4. Monitor disk usage: df -h /"
    echo ""
}

main() {
    if [ $# -eq 0 ]; then
        show_usage
        exit 0
    fi
    
    local run_analyze=false
    local run_p0=false
    local run_p1=false
    local run_automation=false
    
    while [ $# -gt 0 ]; do
        case "$1" in
            --analyze)
                run_analyze=true
                ;;
            --p0)
                check_requirements
                run_p0=true
                ;;
            --p1)
                check_requirements
                run_p1=true
                ;;
            --all)
                check_requirements
                run_p0=true
                run_p1=true
                ;;
            --setup-automation)
                check_requirements
                run_automation=true
                ;;
            --dry-run)
                DRY_RUN="--dry-run"
                log "🔍 DRY-RUN MODE ENABLED"
                ;;
            --yes)
                SKIP_CONFIRM="--yes"
                log "⚡ Auto-confirm enabled (skipping prompts)"
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                error "Unknown option: $1. Use --help for usage."
                ;;
        esac
        shift
    done
    
    log "======================================"
    log "Ubuntu System Optimization Started"
    log "======================================"
    
    if [ "$run_analyze" = true ]; then
        run_analysis
    fi
    
    if [ "$run_p0" = true ]; then
        run_p0_optimizations
    fi
    
    if [ "$run_p1" = true ]; then
        run_p1_optimizations
    fi
    
    if [ "$run_automation" = true ]; then
        setup_automation
    fi
    
    if [ "$run_p0" = true ] || [ "$run_p1" = true ]; then
        print_summary
    fi
    
    log "======================================"
    log "Ubuntu System Optimization Finished"
    log "======================================"
}

main "$@"
