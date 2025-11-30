#!/bin/bash
# Deploy Hybrid Landing (Shock + Manifesto) to ALL nodes

deploy_hybrid() {
    IP=$1
    PASS=$2
    echo "🌩️ Deploying Hybrid Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v5_hybrid.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_hybrid "89.125.1.107" "lhJOTi8vrB01aQ12C0"
deploy_hybrid "77.83.245.27" "13Vbkkbjyjd$"
deploy_hybrid "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ Hybrid Landing LIVE."
