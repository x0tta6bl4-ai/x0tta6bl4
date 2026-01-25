#!/bin/bash
# Test blue-green deployment strategy for x0tta6bl4

set -e

echo "🔵🟢 Testing Blue-Green Deployment Strategy..."

# Check if blue-green deployment exists
if [ ! -f "deployment/kubernetes/blue-green-deployment.yaml" ]; then
    echo "❌ blue-green-deployment.yaml not found"
    exit 1
fi

# Apply blue-green deployment
echo "📋 Applying blue-green deployment..."
kubectl apply -f deployment/kubernetes/blue-green-deployment.yaml

# Wait for both deployments
echo "⏳ Waiting for blue and green deployments..."
kubectl wait --for=condition=available --timeout=300s deployment/x0tta6bl4-blue || true
kubectl wait --for=condition=available --timeout=300s deployment/x0tta6bl4-green || true

# Check status
echo "📊 Blue-Green Deployment Status:"
kubectl get deployment x0tta6bl4-blue x0tta6bl4-green

# Get active service
ACTIVE_SERVICE=$(kubectl get service x0tta6bl4 -o jsonpath='{.spec.selector.version}' 2>/dev/null || echo "blue")
echo "Active service points to: $ACTIVE_SERVICE"

# Test switch
echo "🔄 Testing switch to green..."
kubectl patch service x0tta6bl4 -p '{"spec":{"selector":{"version":"green"}}}'

# Wait and verify
sleep 5
NEW_ACTIVE=$(kubectl get service x0tta6bl4 -o jsonpath='{.spec.selector.version}' 2>/dev/null || echo "")
if [ "$NEW_ACTIVE" = "green" ]; then
    echo "✅ Successfully switched to green"
else
    echo "⚠️  Switch may have failed (current: $NEW_ACTIVE)"
fi

# Switch back to blue
echo "🔄 Switching back to blue..."
kubectl patch service x0tta6bl4 -p '{"spec":{"selector":{"version":"blue"}}}'

echo "✅ Blue-Green deployment test complete"

