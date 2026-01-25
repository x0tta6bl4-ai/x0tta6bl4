#!/bin/bash
# Rollback script for x0tta6bl4 deployment
# Usage: ./scripts/rollback.sh [namespace] [revision]

set -e

NAMESPACE=${1:-"x0tta6bl4"}
REVISION=${2:-"previous"}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Rollback Script                                          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Safety check
if [ "$NAMESPACE" = "x0tta6bl4" ] && [ -z "$CONFIRM_ROLLBACK" ]; then
    echo "⚠️  PRODUCTION ROLLBACK"
    echo "   This will rollback PRODUCTION deployment"
    echo "   Set CONFIRM_ROLLBACK=true to proceed"
    exit 1
fi

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "❌ helm not found"; exit 1; }

# Check if release exists
if ! helm list -n $NAMESPACE | grep -q "x0tta6bl4"; then
    echo "❌ Helm release 'x0tta6bl4' not found in namespace '$NAMESPACE'"
    exit 1
fi

# Get current revision
CURRENT_REVISION=$(helm history x0tta6bl4 -n $NAMESPACE --max 1 --output json 2>/dev/null | grep -oP '"revision":\s*\K\d+' || echo "1")

echo "📋 Current Revision: $CURRENT_REVISION"
echo ""

# List recent revisions
echo "📜 Recent Revisions:"
helm history x0tta6bl4 -n $NAMESPACE --max 5
echo ""

# Determine target revision
if [ "$REVISION" = "previous" ]; then
    TARGET_REVISION=$((CURRENT_REVISION - 1))
    if [ "$TARGET_REVISION" -lt 1 ]; then
        echo "❌ No previous revision to rollback to"
        exit 1
    fi
else
    TARGET_REVISION=$REVISION
fi

echo "🔄 Rolling back to revision: $TARGET_REVISION"
echo ""

# Perform rollback
helm rollback x0tta6bl4 $TARGET_REVISION -n $NAMESPACE --wait --timeout 10m

# Wait for deployment
echo "⏳ Waiting for rollback to complete..."
kubectl wait --for=condition=available --timeout=300s \
    deployment/x0tta6bl4 -n $NAMESPACE || echo "⚠️  Deployment may still be rolling out"

# Check health
echo "🏥 Checking health..."
sleep 5
kubectl port-forward -n $NAMESPACE svc/x0tta6bl4 8000:8000 &
PF_PID=$!
sleep 3

if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Health check passed"
    curl -s http://localhost:8000/health | jq '.' || curl -s http://localhost:8000/health
else
    echo "⚠️  Health check failed - monitor deployment closely"
fi

kill $PF_PID 2>/dev/null || true

# Show status
echo ""
echo "📊 Rollback Status:"
kubectl get pods -n $NAMESPACE
kubectl get svc -n $NAMESPACE

echo ""
echo "✅ Rollback complete!"
echo "   Namespace: $NAMESPACE"
echo "   Revision: $TARGET_REVISION"

