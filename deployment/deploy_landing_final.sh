#!/bin/bash
# Deploy Final Landing (v9) to ALL nodes

deploy_final() {
    IP=$1
    PASS=$2
    echo "🏁 Deploying Final Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v9_final.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_final "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
deploy_final "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
deploy_final "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "✅ Final Landing LIVE."
