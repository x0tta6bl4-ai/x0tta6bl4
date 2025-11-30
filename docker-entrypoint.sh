#!/bin/bash
# Entrypoint for x0tta6bl4 mesh node
# 1. Generate Yggdrasil config (peers, admin socket, tun0)
# 2. Start Yggdrasil (root required for TUN)
# 3. Launch FastAPI app

set -euo pipefail

NODE_ID="${NODE_ID:-node-unknown}"
LISTEN_HOST="${LISTEN_HOST:-0.0.0.0}"
LISTEN_PORT="${LISTEN_PORT:-8000}"
CONFIG_FILE="/etc/yggdrasil/yggdrasil.conf"
ADMIN_SOCKET="/var/run/yggdrasil/yggdrasil.sock"

log() { echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"; }

log "Starting x0tta6bl4 mesh node: ${NODE_ID}"

# Generate Yggdrasil configuration if not exists
if [ ! -f "${CONFIG_FILE}" ]; then
  log "Generating Yggdrasil configuration..."
  yggdrasil -genconf > "${CONFIG_FILE}"

  # Inject peers if provided
  if [ -n "${YGGDRASIL_PEERS:-}" ]; then
    log "Configuring peers: ${YGGDRASIL_PEERS}"
    PEERS_JSON=$(echo "${YGGDRASIL_PEERS}" | awk 'BEGIN{RS=","} {printf "\"%s\",", $0}' | sed 's/,$//')
    sed -i "s|\"Peers\": \[\]|\"Peers\": [${PEERS_JSON}]|g" "${CONFIG_FILE}"
  fi

  # Force deterministic tun interface name
  sed -i 's/"IfName": "auto"/"IfName": "tun0"/g' "${CONFIG_FILE}"

  # Enable admin socket for yggdrasilctl (unix)
  sed -i "s|\"AdminListen\": \"\"|\"AdminListen\": \"unix://${ADMIN_SOCKET}\"|g" "${CONFIG_FILE}"

  # Annotate node info
  sed -i "s|\"NodeInfo\": {}|\"NodeInfo\": {\"name\": \"${NODE_ID}\", \"project\": \"x0tta6bl4\"}|g" "${CONFIG_FILE}"
fi

# Ensure runtime directory exists
mkdir -p "$(dirname "${ADMIN_SOCKET}")" /var/log/yggdrasil

log "Starting Yggdrasil daemon..."
yggdrasil -useconffile "${CONFIG_FILE}" &
YGGDRASIL_PID=$!

# Wait for tun0 and admin socket readiness
READY=0
for i in $(seq 1 30); do
  TUN_READY=0; SOCK_READY=0
  ip addr show tun0 &>/dev/null && TUN_READY=1
  [ -S "${ADMIN_SOCKET}" ] && SOCK_READY=1
  if [ ${TUN_READY} -eq 1 ] && [ ${SOCK_READY} -eq 1 ]; then
    READY=1
    break
  fi
  sleep 1
done

if [ ${READY} -ne 1 ]; then
  log "ERROR: Yggdrasil did not become ready (tun0/admin socket missing)" >&2
  kill ${YGGDRASIL_PID} || true
  exit 1
fi
log "Yggdrasil mesh interface and admin socket ready"

log "Yggdrasil node information (truncated):"
# yggdrasilctl expects YGG_ADMIN_SOCKET env when using unix socket
export YGG_ADMIN_SOCKET="${ADMIN_SOCKET}"
if command -v yggdrasilctl >/dev/null 2>&1; then
  yggdrasilctl getSelf | head -n 8 || log "yggdrasilctl getSelf failed"
else
  log "yggdrasilctl not found"
fi

# Export runtime env for application
export HOST="${LISTEN_HOST}" PORT="${LISTEN_PORT}" NODE_ID="${NODE_ID}" YGG_ADMIN_SOCKET

trap 'log "Shutdown signal received"; kill ${YGGDRASIL_PID} 2>/dev/null || true' TERM INT

log "Launching FastAPI server on ${LISTEN_HOST}:${LISTEN_PORT} (PID will replace shell)"
exec "$@"
