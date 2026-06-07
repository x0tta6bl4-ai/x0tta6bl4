#!/usr/bin/env bash
# Collect local VPN and NL server evidence without changing NL.
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/mnt/projects}"
SSH_TARGET="${SSH_TARGET:-nl}"
VPN_SERVER="${VPN_SERVER:-89.125.1.107}"
OUT_BASE="${OUT_BASE:-$ROOT_DIR/nl-diagnostics/snapshots}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$OUT_BASE/$STAMP"

mkdir -p "$OUT_DIR/local" "$OUT_DIR/nl"

run_local() {
    local name="$1"
    shift
    {
        echo "# command: $*"
        echo "# timestamp_utc: $(date -u -Is)"
        "$@"
    } > "$OUT_DIR/local/$name.txt" 2>&1 || {
        local rc=$?
        echo "# exit_code: $rc" >> "$OUT_DIR/local/$name.txt"
        return 0
    }
}

run_local_json() {
    local name="$1"
    shift
    "$@" > "$OUT_DIR/local/$name.json" 2> "$OUT_DIR/local/$name.err" || {
        local rc=$?
        echo "exit_code=$rc" >> "$OUT_DIR/local/$name.err"
        return 0
    }
}

run_nl() {
    local name="$1"
    local remote_cmd="$2"
    {
        echo "# ssh_target: $SSH_TARGET"
        echo "# command: $remote_cmd"
        echo "# timestamp_utc: $(date -u -Is)"
        ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_TARGET" "$remote_cmd"
    } > "$OUT_DIR/nl/$name.txt" 2>&1 || {
        local rc=$?
        echo "# exit_code: $rc" >> "$OUT_DIR/nl/$name.txt"
        return 0
    }
}

run_local vpn_status bash "$ROOT_DIR/scripts/vpn_status.sh" --check --no-color
run_local_json vpn_status bash "$ROOT_DIR/scripts/vpn_status.sh" --json
run_local local_services systemctl is-active \
    x0tta-node.service \
    x0tta-vpn-watchdog.service \
    x0tta-vpn-route-bypass.service \
    x0tta-vpn-boot-validate.timer \
    xray.service
run_local route_to_vpn ip route get "$VPN_SERVER"
run_local route_to_public ip route get 1.1.1.1
run_local watchdog_metrics curl -fsS --max-time 3 http://127.0.0.1:9091/metrics
if [ "${VPN_ENABLE_BLOCKING_PROBES:-0}" = "1" ]; then
    run_local_json blocking_probe python3 "$ROOT_DIR/nl-diagnostics/probe_blocking_paths.py" \
        --targets-file "${VPN_BLOCKING_TARGETS_FILE:-$ROOT_DIR/nl-diagnostics/blocking_probe_targets.json}"
fi

run_nl identity 'hostname; who -b; uptime; uname -a'
run_nl failed_units 'systemctl --failed --no-pager'
run_nl key_services 'for u in x-ui warp-svc ghost-vpn ghost-tcp-bridge ghost-access-nl-beta ghost-access-nl-xhttp.service ghost-access-nl-xhttp-sync.timer ghost-access-nl-https-ws.service ghost-access-nl-https-ws-sync.timer ghost-access-transport-usage-evidence.timer nginx docker x0tta6bl4-profile-status-api x0tta6bl4-runtime-state.timer; do printf "%s=" "$u"; systemctl is-active "$u" 2>/dev/null || true; done'
run_nl timers 'systemctl list-timers --all --no-pager | egrep -i "x0tta|vpn|ghost|xray|runtime|listener|health|rotation|fallback|audit" || true'
run_nl listeners 'ss -lntup | egrep ":(443|2083|39829|2443|4433|4434|51820|8443|62789)" || true'
run_nl xui_inbounds 'sqlite3 -readonly /etc/x-ui/x-ui.db "select id,port,protocol,enable,remark from inbounds order by port;" 2>/dev/null || true'
run_nl resources 'free -h; df -h /; cat /proc/loadavg'
run_nl runtime_state_summary 'if command -v jq >/dev/null && [ -f /opt/x0tta6bl4-mesh/state/runtime-state.json ]; then jq "{generated_at,mode,reason,recommended_action,hot_path_summary,probes:{listener_443_ok:.probes.listener_443_ok,xui_service_ok:.probes.xui_service_ok,warp_ok:.probes.warp_ok,ghost_ready:.probes.ghost_ready,ghost_xhttp_ready:.probes.ghost_xhttp_ready,ghost_https_ws_ready:.probes.ghost_https_ws_ready,subscription_health_status:.probes.subscription_health_status,transport_summary:.probes.transport_summary,transport_usage_60m:.probes.transport_usage_evidence.summary_60m}}" /opt/x0tta6bl4-mesh/state/runtime-state.json; else sed -E "s/(uuid|password|secret|token|privateKey|publicKey|email)[^,}]*/REDACTED/Ig" /opt/x0tta6bl4-mesh/state/runtime-state.json 2>/dev/null || true; fi'
run_nl boot_history 'journalctl --list-boots --no-pager | tail -10'
run_nl last_reboots 'last -x -F | head -40 || true'
run_nl current_boot_integrity 'journalctl -b 0 --no-pager 2>/dev/null | grep -Ei "uncleanly shut down|corrupted or uncleanly|recovering journal|journal recovery|EXT4-fs|fsck|orphan" | head -100 || true'
run_nl previous_boot_tail 'journalctl -b -1 --no-pager -n 260 2>/dev/null || true'
run_nl previous_boot_gap_indicators 'journalctl -b -1 --no-pager -n 400 2>/dev/null | grep -Ei "guest-shutdown|hypervisor initiated shutdown|System is powering down|systemd-shutdown|poweroff|shutdown|panic|Out of memory|oom-killer|watchdog|hung daemon|Long readout|hogged CPU|I/O error|blocked for more|soft lockup|hard LOCKUP|timed out" | tail -160 || true'
run_nl provider_signals 'printf "PROVIDER_SHUTDOWN_LINES\n"; journalctl -b -1 --no-pager 2>/dev/null | grep -Ei "guest-shutdown|hypervisor initiated shutdown|System is powering down|systemd-shutdown|poweroff|shutdown|panic|Out of memory" | tail -80 || true; printf "\nCURRENT_CPU_STEAL\n"; if command -v mpstat >/dev/null; then mpstat 1 3; else echo "mpstat unavailable"; fi; printf "\nCURRENT_IOSTAT\n"; if command -v iostat >/dev/null; then iostat -xz 1 2; else echo "iostat unavailable"; fi'

find "$OUT_DIR" -type f -print0 | while IFS= read -r -d '' file; do
    perl -0pi \
        -e 's/RegistrationInfo: Some\(RegistrationInfo \{.*?alternate_networks: None \}\)/RegistrationInfo: REDACTED/g;' \
        -e 's/[0-9]{8,10}:[A-Za-z0-9_-]{35,}/REDACTED_BOT_TOKEN/g;' \
        -e 's/\b(vless|vmess|trojan|ss):\/\/[^\s)]+/REDACTED_VPN_URI/gi;' \
        -e 's/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/REDACTED_UUID/g;' \
        -e 's/license: "[^"]+"/license: "REDACTED"/g;' \
        -e 's/public_key: \[[^\]]+\]/public_key: REDACTED/g;' \
        -e 's/(token|secret|password|privateKey|publicKey|webBasePath)\s*[:=]\s*['\''"]?[^,'\''"\s}]+/$1=REDACTED/gi;' \
        "$file"
done

cat > "$OUT_DIR/README.txt" <<EOF
VPN read-only snapshot
timestamp_utc=$STAMP
root_dir=$ROOT_DIR
ssh_target=$SSH_TARGET
vpn_server=$VPN_SERVER

This snapshot is intended to be safe to share after manual review.
It does not write to NL. Remote commands are read-only.

Important files:
- local/vpn_status.txt
- local/vpn_status.json
- local/watchdog_metrics.txt
- nl/runtime_state_summary.txt
- nl/key_services.txt
- nl/listeners.txt
- nl/xui_inbounds.txt
- nl/failed_units.txt
- nl/last_reboots.txt
- nl/current_boot_integrity.txt
- nl/previous_boot_tail.txt
- nl/previous_boot_gap_indicators.txt
- nl/provider_signals.txt
EOF

echo "$OUT_DIR"
