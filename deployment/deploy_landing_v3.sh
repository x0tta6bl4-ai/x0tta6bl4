#!/bin/bash
# Deploy SaaS Landing Page to ALL nodes

deploy_landing() {
    IP=$1
    PASS=$2
    echo "🚀 Deploying Landing v3 to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v3_saas.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_landing "89.125.1.107" "lhJOTi8vrB01aQ12C0"
deploy_landing "77.83.245.27" "13Vbkkbjyjd$"
deploy_landing "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ New Landing LIVE everywhere."
