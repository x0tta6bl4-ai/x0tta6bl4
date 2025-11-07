#!/bin/bash
# Entrypoint for x0tta6bl4 Docker containers
# Generates Yggdrasil config with peer connections and starts mesh node

set -e

# Environment variables:
# - NODE_ID: unique identifier (node-a, node-b, node-c)
# - YGGDRASIL_PEERS: comma-separated list of peer URIs
# - LISTEN_HOST: API server bind address (default: 0.0.0.0)
# - LISTEN_PORT: API server port (default: 8000)

NODE_ID="${NODE_ID:-node-unknown}"
LISTEN_HOST="${LISTEN_HOST:-0.0.0.0}"
LISTEN_PORT="${LISTEN_PORT:-8000}"
CONFIG_FILE="/etc/yggdrasil/yggdrasil.conf"

echo "[$(date)] Starting x0tta6bl4 mesh node: ${NODE_ID}"

# Generate Yggdrasil configuration if not exists
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "[$(date)] Generating Yggdrasil configuration..."
    yggdrasil -genconf > "${CONFIG_FILE}"
    
    # Add peer connections from environment
    if [ -n "${YGGDRASIL_PEERS}" ]; then
        echo "[$(date)] Configuring peers: ${YGGDRASIL_PEERS}"
        # Convert comma-separated list to JSON array format
        PEERS_JSON=$(echo "${YGGDRASIL_PEERS}" | awk 'BEGIN{RS=","} {printf "\"%s\",", $0}' | sed 's/,$//')
        
        # Update Peers array in config (using inline replacement)
        sed -i "s|\"Peers\": \[\]|\"Peers\": [${PEERS_JSON}]|g" "${CONFIG_FILE}"
    fi
    
    # Enable TUN interface for mesh routing
    sed -i 's/"IfName": "auto"/"IfName": "tun0"/g' "${CONFIG_FILE}"
    
    # Set NodeInfo for identification
    sed -i "s|\"NodeInfo\": {}|\"NodeInfo\": {\"name\": \"${NODE_ID}\", \"project\": \"x0tta6bl4\"}|g" "${CONFIG_FILE}"
fi

# Start Yggdrasil daemon in background
echo "[$(date)] Starting Yggdrasil daemon..."
sudo -u root yggdrasil -useconffile "${CONFIG_FILE}" &
YGGDRASIL_PID=$!

# Wait for Yggdrasil to initialize (check for tun0 interface)
echo "[$(date)] Waiting for Yggdrasil mesh interface..."
for i in {1..30}; do
    if ip addr show tun0 &>/dev/null; then
        echo "[$(date)] Yggdrasil mesh interface ready"
        break
    fi
    sleep 1
done

# Display Yggdrasil node info
echo "[$(date)] Yggdrasil node information:"
sudo yggdrasilctl getSelf | head -n 5

# Export environment for application
export HOST="${LISTEN_HOST}"
export PORT="${LISTEN_PORT}"
export NODE_ID="${NODE_ID}"

# Launch application (exec to replace shell with main process)
echo "[$(date)] Launching x0tta6bl4 server on ${LISTEN_HOST}:${LISTEN_PORT}..."
exec "$@"
