#!/bin/bash
# Deploy Shock Landing to ALL nodes

deploy_shock() {
    IP=$1
    PASS=$2
    echo "🌩️ Deploying Shock Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v4_shock.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_shock "89.125.1.107" "lhJOTi8vrB01aQ12C0"
deploy_shock "77.83.245.27" "13Vbkkbjyjd$"
deploy_shock "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ Shock Landing LIVE."
