#!/bin/bash
# Start port-forward for demo access

set -e

echo "🌐 Starting port-forward for x0tta6bl4 demo..."
echo ""
echo "Access the demo at: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

kubectl port-forward svc/x0tta6bl4 8080:80

