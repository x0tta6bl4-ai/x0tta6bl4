#!/usr/bin/env bash

# Week 2 rollout orchestrator.
# This can call live rollout commands, but script completion is not production proof.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REAL_READINESS_JSON=".tmp/validation-shards/real-readiness-current.json"
REAL_READINESS_MD=".tmp/validation-shards/real-readiness-current.md"
ALLOW_LIVE_ROLLOUT="${X0TTA6BL4_ALLOW_LIVE_ROLLOUT:-}"
cd "$ROOT_DIR"

DEPLOYMENT_STAGE="${1:-all}"  # all, canary, rollout, full

claim_boundary() {
    echo "Claim boundary: this script may orchestrate rollout commands, but it does not"
    echo "prove live customer traffic, external DPI bypass, settlement finality,"
    echo "production SLOs, or production readiness without separate evidence."
}

require_live_rollout_preflight() {
    local stage="$1"
    echo "Running fail-closed real-readiness gate before live rollout stage: $stage"
    if ! python3 "$ROOT_DIR/scripts/ops/check_real_readiness.py" \
        --write-json "$REAL_READINESS_JSON" \
        --write-md "$REAL_READINESS_MD" >/dev/null; then
        echo "❌ REAL READINESS GATE: BLOCKED"
        echo "Live rollout stage '$stage' is not allowed yet."
        echo "Report: $REAL_READINESS_JSON"
        exit 1
    fi

    if [ "$ALLOW_LIVE_ROLLOUT" != "yes" ]; then
        echo "❌ LIVE ROLLOUT AUTHORIZATION: BLOCKED"
        echo "Set X0TTA6BL4_ALLOW_LIVE_ROLLOUT=yes locally after approval."
        echo "Do not paste secrets or approvals into chat."
        exit 1
    fi

    echo "✅ REAL READINESS GATE: PASSED"
    echo "✅ LIVE ROLLOUT AUTHORIZATION: PRESENT"
}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 WEEK 2: ROLLOUT ORCHESTRATOR                          ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
claim_boundary
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
            require_live_rollout_preflight "canary"
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
            require_live_rollout_preflight "rollout"
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
            require_live_rollout_preflight "full"
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
        require_live_rollout_preflight "all"
        python3 scripts/canary_deployment.py
        ;;
    
    monitor)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "PRODUCTION MONITORING"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        DURATION=${2:-60}
        echo "Starting monitoring for $DURATION minutes..."
        echo "Monitoring is observational only and is not production readiness proof."
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
echo "✅ ROLLOUT ORCHESTRATOR COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
claim_boundary
echo ""
