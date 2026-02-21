#!/bin/bash
# Deploy Mystic Landing (v6) to ALL nodes

deploy_mystic() {
    IP=$1
    PASS=$2
    echo "🔮 Deploying Mystic Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v6_mystic.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_mystic "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
deploy_mystic "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
deploy_mystic "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "✅ Mystic Landing LIVE."
