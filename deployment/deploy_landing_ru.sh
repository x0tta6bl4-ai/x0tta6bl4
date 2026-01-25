#!/bin/bash
# Deploy Russian Landing (v8) to ALL nodes

deploy_ru() {
    IP=$1
    PASS=$2
    echo "🇷🇺 Deploying Russian Landing to $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v8_ru.html root@$IP:/opt/x0tta6bl4/landing.html
}

deploy_ru "89.125.1.107" "lhJOTi8vrB01aQ12C0"
deploy_ru "77.83.245.27" "13Vbkkbjyjd$"
deploy_ru "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ Russian Landing LIVE."
