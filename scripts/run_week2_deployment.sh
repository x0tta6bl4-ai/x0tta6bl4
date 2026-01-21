#!/bin/bash

# Week 2: Production Deployment Script
# Manages complete production deployment process

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

DEPLOYMENT_STAGE="${1:-all}"  # all, canary, rollout, full

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 WEEK 2: PRODUCTION DEPLOYMENT                         ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

case "$DEPLOYMENT_STAGE" in
    canary)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "CANARY DEPLOYMENT: 5% → 25%"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Starting canary deployment..."
        echo "This will deploy 5% traffic, monitor, then scale to 25%"
        echo ""
        read -p "Continue? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 scripts/canary_deployment.py --stages 5,25
        fi
        ;;
    
    rollout)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "GRADUAL ROLLOUT: 50% → 75%"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Starting gradual rollout..."
        echo "This will deploy 50% traffic, monitor, then scale to 75%"
        echo ""
        read -p "Continue? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 scripts/canary_deployment.py --stages 50,75
        fi
        ;;
    
    full)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "FULL DEPLOYMENT: 100%"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Starting full deployment..."
        echo "This will deploy 100% traffic and monitor for 24 hours"
        echo ""
        read -p "Continue? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 scripts/canary_deployment.py --stages 100
            # Start 24-hour monitoring
            python3 scripts/production_monitor.py --duration 1440 --interval 60 &
            MONITOR_PID=$!
            echo "Monitoring started (PID: $MONITOR_PID)"
            echo "To stop monitoring: kill $MONITOR_PID"
        fi
        ;;
    
    all)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "COMPLETE DEPLOYMENT: 5% → 25% → 50% → 75% → 100%"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "⚠️  WARNING: This will execute complete production deployment"
        echo "   Make sure you have:"
        echo "   1. Executive approval"
        echo "   2. Team on standby"
        echo "   3. Rollback plan ready"
        echo ""
        read -p "Continue with full deployment? (yes/no): "
        if [[ $REPLY != "yes" ]]; then
            echo "Deployment cancelled."
            exit 0
        fi
        
        # Execute full deployment
        python3 scripts/canary_deployment.py
        ;;
    
    monitor)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "PRODUCTION MONITORING"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        DURATION=${2:-60}
        echo "Starting monitoring for $DURATION minutes..."
        python3 scripts/production_monitor.py --duration "$DURATION"
        ;;
    
    *)
        echo "Usage: $0 {canary|rollout|full|all|monitor} [duration]"
        echo ""
        echo "Stages:"
        echo "  canary   - Deploy 5% → 25% (Jan 8-9)"
        echo "  rollout  - Deploy 50% → 75% (Jan 10-11)"
        echo "  full     - Deploy 100% (Jan 12-13)"
        echo "  all      - Complete deployment (5% → 100%)"
        echo "  monitor  - Monitor production (default: 60 minutes)"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT SCRIPT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

