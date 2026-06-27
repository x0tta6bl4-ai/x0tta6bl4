#!/bin/bash
# exchange_pqc_keys.sh — Exchange PQC signing keys between mesh nodes
#
# Usage:
#   ./exchange_pqc_keys.sh --local-ip 89.125.1.107 --peer-ip 1.2.3.4 --peer-port 5000
#
# This script sends the local node's PQC signing public key to a peer
# and registers it as a trusted peer for handshake verification.

set -euo pipefail

LOCAL_IP="${1:-$(hostname -I | awk '{print $1}')}"
LOCAL_PORT="${2:-5000}"
PEER_IP="${3:-}"
PEER_PORT="${4:-5000}"

if [ -z "$PEER_IP" ]; then
    echo "Usage: $0 <local-ip> <local-port> <peer-ip> <peer-port>"
    echo "Example: $0 89.125.1.107 5000 1.2.3.4 5000"
    exit 1
fi

echo "🔐 PQC Key Exchange"
echo "   Local:  $LOCAL_IP:$LOCAL_PORT"
echo "   Peer:   $PEER_IP:$PEER_PORT"

# The PQC key exchange happens automatically during mesh handshake.
# This script triggers it by sending a probe to the peer.

# Send a mesh probe (raw UDP with PQC init prefix)
python3 -c "
import socket, json, time, hashlib

# Create a simple mesh announce
msg = json.dumps({
    'type': 1,
    'sender': '$(hostname)-$(date +%s)',
    'payload': {
        'peer': {
            'node_id': '$(hostname)',
            'addresses': [['$LOCAL_IP', $LOCAL_PORT]],
            'services': ['mesh', 'pqc'],
            'version': '3.4.0'
        }
    },
    'ts': int(time.time() * 1000)
}).encode()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(msg, ('$PEER_IP', 7777))  # Send to discovery port
sock.close()
print(f'✅ Probe sent to {\"$PEER_IP\"}:7777')
print(f'   If peer is running, it will discover us and initiate PQC handshake.')
print(f'   Check logs on both nodes for \"PQC handshake completed\".')
"

echo ""
echo "📋 Next steps:"
echo "   1. Check peer logs: ssh root@$PEER_IP 'journalctl -u x0t-agent -f'"
echo "   2. Verify handshake: ssh root@$PEER_IP 'grep \"PQC handshake\" /var/log/x0t-agent.log'"
echo "   3. Test connectivity: ssh root@$PEER_IP 'curl http://$LOCAL_IP:8080/health'"
