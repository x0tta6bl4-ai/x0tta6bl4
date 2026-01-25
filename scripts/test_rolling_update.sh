#!/bin/bash
# Test rolling update strategy for x0tta6bl4

set -e

echo "🔄 Testing Rolling Update Strategy..."

# Get current image
CURRENT_IMAGE=$(kubectl get deployment x0tta6bl4 -o jsonpath='{.spec.template.spec.containers[0].image}')

echo "Current image: $CURRENT_IMAGE"

# Simulate update by changing environment variable
echo "📝 Updating deployment..."
kubectl set env deployment/x0tta6bl4 TEST_UPDATE=$(date +%s)

# Watch rollout
echo "👀 Watching rollout status..."
kubectl rollout status deployment/x0tta6bl4 --timeout=300s

# Verify all pods are ready
echo "✅ Verifying pods..."
READY_PODS=$(kubectl get deployment x0tta6bl4 -o jsonpath='{.status.readyReplicas}')
DESIRED_PODS=$(kubectl get deployment x0tta6bl4 -o jsonpath='{.spec.replicas}')

if [ "$READY_PODS" = "$DESIRED_PODS" ]; then
    echo "✅ All $DESIRED_PODS pods are ready"
else
    echo "⚠️  Only $READY_PODS/$DESIRED_PODS pods ready"
fi

# Check health after update
echo "🏥 Checking health after update..."
kubectl get pods -l app=x0tta6bl4 -o wide

echo "✅ Rolling update test complete"

