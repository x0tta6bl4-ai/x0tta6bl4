#!/usr/bin/env bash
# Ghost Pulse VPN Client Start Script

export VPN_ENCRYPTION_KEY="VMYlEF9wQr47XZb4x+V1J57SWj4/bdNLVXWquSXaCyM="
export VPN_SERVER="89.125.1.107"
export VPN_PORT="9999"
export PULSE_MODE="corporate"
export PULSE_SEED="20260521"

echo "Starting Ghost Pulse VPN Client..."
echo "Server: $VPN_SERVER:$VPN_PORT"
echo "Mode: $PULSE_MODE"

# Run the client
# Note: Requires sudo for TUN interface
sudo VPN_ENCRYPTION_KEY="$VPN_ENCRYPTION_KEY" \
     VPN_SERVER="$VPN_SERVER" \
     VPN_PORT="$VPN_PORT" \
     PULSE_MODE="$PULSE_MODE" \
     PULSE_SEED="$PULSE_SEED" \
     python3 ghost_pulse_vpn.py client
