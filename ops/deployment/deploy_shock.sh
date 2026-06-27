#!/bin/bash
# Deploy Shock Landing to ALL nodes

deploy_shock() {
    IP=$1
    PASS=$2
    echo "🌩️ Deploying Shock Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v4_shock.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_shock "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
deploy_shock "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
deploy_shock "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "✅ Shock Landing LIVE."
