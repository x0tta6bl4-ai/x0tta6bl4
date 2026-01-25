#!/bin/bash
# Deploy Final Landing (v9) to ALL nodes

deploy_final() {
    IP=$1
    PASS=$2
    echo "🏁 Deploying Final Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v9_final.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_final "89.125.1.107" "lhJOTi8vrB01aQ12C0"
deploy_final "77.83.245.27" "13Vbkkbjyjd$"
deploy_final "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ Final Landing LIVE."
