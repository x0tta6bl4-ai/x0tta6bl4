#!/bin/bash
# Deploy Fonts Landing (v7) to ALL nodes

deploy_fonts() {
    IP=$1
    PASS=$2
    echo "☢️ Deploying Atomic/Cyber Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v7_fonts.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_fonts "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
deploy_fonts "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
deploy_fonts "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "✅ Fonts Landing LIVE."
