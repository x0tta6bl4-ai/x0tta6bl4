#!/bin/bash
# Rollback to Landing v2 (Manifesto Style)

rollback_landing() {
    IP=$1
    PASS=$2
    echo "🔙 Rolling back Landing on $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v2.html root@$IP:/opt/x0tta6bl4/landing.html
}

rollback_landing "89.125.1.107" "lhJOTi8vrB01aQ12C0"
rollback_landing "77.83.245.27" "13Vbkkbjyjd$"
rollback_landing "62.133.60.252" "13Vbkkbjyjd$"

echo "✅ Manifesto Style Restored."
