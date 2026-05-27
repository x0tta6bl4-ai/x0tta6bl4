#!/usr/bin/env bash
# Keep the VPN server endpoint outside the sing-box policy route.
set -euo pipefail

VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
ROUTE_PRIORITY="${VPN_ROUTE_BYPASS_PRIORITY:-8999}"
TUN_IFACE="${VPN_TUN_IFACE:-singbox_tun}"

if ! command -v ip >/dev/null 2>&1; then
    echo "ip command not found" >&2
    exit 1
fi

DEFAULT_LINE="$(
    ip route show default |
        awk -v tun="$TUN_IFACE" '$0 !~ tun { print; exit }'
)"

if [[ -z "$DEFAULT_LINE" ]]; then
    echo "could not find non-$TUN_IFACE default route" >&2
    exit 1
fi

DEV="$(awk '{for (i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}' <<< "$DEFAULT_LINE")"
GW="$(awk '{for (i=1;i<=NF;i++) if ($i=="via") {print $(i+1); exit}}' <<< "$DEFAULT_LINE")"

if [[ -z "$DEV" || -z "$GW" ]]; then
    echo "could not parse default route: $DEFAULT_LINE" >&2
    exit 1
fi

ip route replace "$VPN_SERVER/32" via "$GW" dev "$DEV"

if ! ip rule show | grep -q "to $VPN_SERVER lookup main"; then
    ip rule add priority "$ROUTE_PRIORITY" to "$VPN_SERVER/32" lookup main
fi

ROUTE_CHECK="$(ip route get "$VPN_SERVER" 2>/dev/null | head -1 || true)"
if [[ -z "$ROUTE_CHECK" ]]; then
    echo "could not resolve route to $VPN_SERVER after bypass install" >&2
    exit 1
fi

if grep -q "$TUN_IFACE" <<< "$ROUTE_CHECK"; then
    echo "route loop guard failed: $VPN_SERVER still resolves via $TUN_IFACE: $ROUTE_CHECK" >&2
    exit 1
fi

echo "$ROUTE_CHECK"
