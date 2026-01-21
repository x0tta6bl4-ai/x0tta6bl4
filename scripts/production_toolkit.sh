#!/bin/bash

# Production Toolkit - All-in-one script for production operations

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

TOOL="${1:-help}"

case "$TOOL" in
    health)
        echo "🏥 Health Check Dashboard"
        python3 scripts/health_check_dashboard.py "${@:2}"
        ;;
    
    monitor)
        echo "📊 Production Monitoring"
        python3 scripts/production_monitor.py "${@:2}"
        ;;
    
    collect)
        echo "📈 Metrics Collection"
        python3 scripts/metrics_collector.py "${@:2}"
        ;;
    
    compare)
        echo "🔍 Baseline Comparison"
        python3 scripts/compare_baseline.py "${@:2}"
        ;;
    
    rollback)
        echo "🔄 Auto-Rollback Monitor"
        python3 scripts/auto_rollback.py "${@:2}"
        ;;
    
    deploy)
        echo "🚀 Deployment"
        bash scripts/run_week2_deployment.sh "${@:2}"
        ;;
    
    audit)
        echo "🔐 Security Audit"
        python3 scripts/security_audit_checklist.py
        ;;
    
    baseline)
        echo "📊 Performance Baseline"
        python3 scripts/performance_baseline.py
        ;;
    
    help|*)
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                                                              ║"
        echo "║     🛠️  PRODUCTION TOOLKIT                                   ║"
        echo "║                                                              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo ""
        echo "Usage: $0 {tool} [options]"
        echo ""
        echo "Tools:"
        echo "  health    - Health check dashboard"
        echo "  monitor   - Production monitoring"
        echo "  collect   - Metrics collection"
        echo "  compare   - Compare against baseline"
        echo "  rollback  - Auto-rollback monitor"
        echo "  deploy    - Deployment orchestration"
        echo "  audit     - Security audit"
        echo "  baseline  - Performance baseline"
        echo ""
        echo "Examples:"
        echo "  $0 health --interval 5"
        echo "  $0 monitor --duration 60"
        echo "  $0 collect --duration 30 --interval 10"
        echo "  $0 compare --metrics metrics_20250101.json"
        echo "  $0 rollback --interval 10"
        echo "  $0 deploy canary"
        echo ""
        ;;
esac

