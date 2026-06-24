#!/bin/bash
IP="62.133.60.252"
PASS="${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🔧 Repairing Node 3..."
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "ufw allow 9091/tcp || true"
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "iptables -A INPUT -p tcp --dport 9091 -j ACCEPT || true"
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart x0tta6bl4-brain && systemctl status x0tta6bl4-brain --no-pager"
echo "✅ Done."
