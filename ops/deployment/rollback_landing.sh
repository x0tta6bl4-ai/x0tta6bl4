#!/bin/bash
# Rollback to Landing v2 (Manifesto Style)

rollback_landing() {
    IP=$1
    PASS=$2
    echo "🔙 Rolling back Landing on $IP..."
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no landing_v2.html root@$IP:/opt/x0tta6bl4/landing.html
}

rollback_landing "89.125.1.107" "${NODE1_PASS:?Set NODE1_PASS in environment}"
rollback_landing "77.83.245.27" "${NODE23_PASS:?Set NODE23_PASS in environment}"
rollback_landing "62.133.60.252" "${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "✅ Manifesto Style Restored."
