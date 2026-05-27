#!/usr/bin/env bash
# Roll back the NL VPN route-bypass/watchdog install. Dry-run by default.
set -euo pipefail

VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
ROUTE_PRIORITY="${VPN_ROUTE_BYPASS_PRIORITY:-8999}"
TUN_IFACE="${VPN_TUN_IFACE:-singbox_tun}"

APPLY=0
RESTART_NODE=0

usage() {
    cat <<USAGE
Usage: $0 [--dry-run] [--apply] [--restart-node]

Options:
  --dry-run       Print rollback actions without changing the system (default)
  --apply         Execute rollback actions
  --restart-node  Restart x0tta-node.service after rollback (explicit downtime)
  -h, --help      Show this help

Environment:
  VPN_SERVER=$VPN_SERVER
  VPN_ROUTE_BYPASS_PRIORITY=$ROUTE_PRIORITY
  VPN_TUN_IFACE=$TUN_IFACE
USAGE
}

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            APPLY=0
            ;;
        --apply)
            APPLY=1
            ;;
        --restart-node)
            RESTART_NODE=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "$APPLY" -eq 1 ]]; then
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        SUDO=()
    elif command -v sudo >/dev/null 2>&1; then
        SUDO=(sudo)
    else
        echo "--apply requires root or sudo" >&2
        exit 1
    fi
else
    SUDO=(sudo)
fi

print_command() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
}

run() {
    print_command "$@"
    if [[ "$APPLY" -eq 1 ]]; then
        "$@"
    fi
}

run_optional() {
    print_command "$@"
    if [[ "$APPLY" -eq 1 ]]; then
        "$@" 2>/dev/null || true
    fi
}

show_state() {
    echo "Current state:"
    systemctl is-active x0tta-vpn-route-bypass.service 2>/dev/null \
        | sed 's/^/  x0tta-vpn-route-bypass.service: /' || true
    systemctl is-active x0tta-vpn-watchdog.service 2>/dev/null \
        | sed 's/^/  x0tta-vpn-watchdog.service: /' || true
    systemctl is-active x0tta-vpn-boot-validate.timer 2>/dev/null \
        | sed 's/^/  x0tta-vpn-boot-validate.timer: /' || true
    ip rule show 2>/dev/null | awk -v priority="${ROUTE_PRIORITY}:" '$1 == priority {print "  ip rule: " $0}' || true
    ip route get "$VPN_SERVER" 2>/dev/null | sed 's/^/  route: /' || true
}

echo "=== NL VPN Route Bypass Rollback ==="
echo "Mode: $([[ "$APPLY" -eq 1 ]] && echo apply || echo dry-run)"
echo "Target: $VPN_SERVER | priority=$ROUTE_PRIORITY | tunnel=$TUN_IFACE"
echo
show_state
echo

if [[ "$APPLY" -eq 0 ]]; then
    echo "Dry-run only. Re-run with --apply to execute these actions."
    echo
fi

run_optional "${SUDO[@]}" systemctl disable --now x0tta-vpn-watchdog.service
run_optional "${SUDO[@]}" systemctl disable --now x0tta-vpn-boot-validate.timer
run_optional "${SUDO[@]}" systemctl stop x0tta-vpn-boot-validate.service
run_optional "${SUDO[@]}" systemctl disable --now x0tta-vpn-route-bypass.service
run_optional "${SUDO[@]}" rm -f /etc/systemd/system/x0tta-vpn-watchdog.service
run_optional "${SUDO[@]}" rm -f /etc/systemd/system/x0tta-vpn-boot-validate.service
run_optional "${SUDO[@]}" rm -f /etc/systemd/system/x0tta-vpn-boot-validate.timer
run_optional "${SUDO[@]}" rm -f /etc/systemd/system/x0tta-vpn-route-bypass.service
run_optional "${SUDO[@]}" rm -f /etc/systemd/system/x0tta-node.service.d/10-route-bypass.conf
run_optional "${SUDO[@]}" rm -f /usr/local/sbin/x0tta-vpn-boot-validate
run_optional "${SUDO[@]}" rm -f /usr/local/sbin/x0tta-vpn-route-bypass
run "${SUDO[@]}" systemctl daemon-reload
run_optional "${SUDO[@]}" ip rule del priority "$ROUTE_PRIORITY" to "$VPN_SERVER/32" lookup main
run_optional "${SUDO[@]}" ip route del "$VPN_SERVER/32"

if [[ "$RESTART_NODE" -eq 1 ]]; then
    run "${SUDO[@]}" systemctl restart x0tta-node.service
else
    echo "+ skip systemctl restart x0tta-node.service (pass --restart-node to allow downtime)"
fi

if [[ "$APPLY" -eq 1 ]]; then
    echo
    echo "Post-rollback state:"
    show_state

    ROUTE_CHECK="$(ip route get "$VPN_SERVER" 2>/dev/null | head -1 || true)"
    if [[ -z "$ROUTE_CHECK" ]]; then
        echo "WARNING: cannot resolve route to $VPN_SERVER after rollback" >&2
        exit 1
    fi
    if grep -q "$TUN_IFACE" <<< "$ROUTE_CHECK"; then
        echo "WARNING: route to $VPN_SERVER now resolves via $TUN_IFACE: $ROUTE_CHECK" >&2
        echo "Rollback executed, but route-loop risk is present. Reapply bypass before restarting VPN clients." >&2
        exit 1
    fi
fi

echo
echo "Rollback command completed."
