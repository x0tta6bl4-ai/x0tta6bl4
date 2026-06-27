#!/usr/bin/env bash
# x0tta6bl4 Network Setup Helper - FULL FUNCTIONALITY VERSION
set -e

IFACE=$1
ADDR=$2
GW=$3
USER_NAME=$4
MODE=$5 # "p2p" or "full"

LOG_FILE="/tmp/x0t_network_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "--- Setup started at $(date) ---"
echo "Params: IFACE=$IFACE, ADDR=$ADDR, GW=$GW, USER=$USER_NAME, MODE=$MODE"

# 1. Ensure TUN device accessibility for this session
chmod 666 /dev/net/tun

# 2. Clean up old interface
ip link delete "$IFACE" 2>/dev/null || true

# 3. Create persistent TUN owned by the user
ip tuntap add dev "$IFACE" mode tun user "$USER_NAME"

# 4. Configure IP and bring it up
ip addr add "$ADDR" dev "$IFACE"
ip link set dev "$IFACE" up

# 5. Routing
if [ "$MODE" == "full" ]; then
    echo "Configuring FULL TUNNEL (Default Gateway)..."
    # Get current default gateway and interface
    DEFAULT_GW=$(ip route show default | awk '/default/ {print $3}')
    DEFAULT_IFACE=$(ip route show default | awk '/default/ {print $5}')
    SERVER_IP="89.125.1.107"

    # Route to the VPN server itself via the old gateway (to avoid loops)
    ip route add "$SERVER_IP" via "$DEFAULT_GW" dev "$DEFAULT_IFACE" || true

    # Replace default gateway
    ip route add 0.0.0.0/1 dev "$IFACE"
    ip route add 128.0.0.0/1 dev "$IFACE"

    # Set DNS to Cloudflare/Google to ensure no leaks
    echo "nameserver 1.1.1.1" > /etc/resolv.conf
    echo "nameserver 8.8.8.8" >> /etc/resolv.conf
else
    echo "Configuring P2P TUNNEL (Direct server access only)..."
    ip route add "$GW" dev "$IFACE"
fi

echo "Network setup SUCCESSFUL."
