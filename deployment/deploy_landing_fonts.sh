#!/bin/bash
# Deploy Fonts Landing (v7) to ALL nodes

deploy_fonts() {
    IP=$1
    PASS=$2
    echo "☢️ Deploying Atomic/Cyber Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v7_fonts.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_fonts "89.125.1.107" "lhJOTi8vrB01aQ12C0"
deploy_fonts "77.83.245.27" "13Vbkkbjyjd$"
deploy_fonts "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ Fonts Landing LIVE."
