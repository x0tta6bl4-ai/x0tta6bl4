#!/usr/bin/env bash
# Build a sanitized local profile of the NL server without writing to NL.
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/mnt/projects}"
SSH_TARGET="${SSH_TARGET:-nl}"
OUT_BASE="${OUT_BASE:-$ROOT_DIR/nl-diagnostics/nl-server-profile}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$OUT_BASE/$STAMP"

mkdir -p \
    "$OUT_DIR/systemd" \
    "$OUT_DIR/xui" \
    "$OUT_DIR/mesh" \
    "$OUT_DIR/ghost-access" \
    "$OUT_DIR/ghost-vpn" \
    "$OUT_DIR/cron" \
    "$OUT_DIR/network" \
    "$OUT_DIR/provider" \
    "$OUT_DIR/resources"

run_nl() {
    local path="$1"
    local remote_cmd="$2"
    {
        echo "# ssh_target: $SSH_TARGET"
        echo "# command: $remote_cmd"
        echo "# timestamp_utc: $(date -u -Is)"
        ssh -o BatchMode=yes -o ConnectTimeout=10 "$SSH_TARGET" "$remote_cmd"
    } > "$OUT_DIR/$path" 2>&1 || {
        local rc=$?
        echo "# exit_code: $rc" >> "$OUT_DIR/$path"
        return 0
    }
}

run_nl "identity.txt" 'hostname; who -b; uptime; uname -a; date -Is'
run_nl "systemd/relevant-units.txt" 'systemctl list-units --type=service --all --no-pager | egrep -i "x0tta|vpn|xray|x-ui|warp|ghost|nginx|docker|networking|ifup|open5gs|telegram" || true'
run_nl "systemd/relevant-timers.txt" 'systemctl list-timers --all --no-pager | egrep -i "x0tta|vpn|xray|x-ui|warp|ghost|listener|runtime|health|mesh|rotation|fallback|audit" || true'
run_nl "systemd/relevant-unit-files.txt" 'find /etc/systemd/system /lib/systemd/system -maxdepth 2 -type f 2>/dev/null | egrep -i "x0tta|vpn|xray|x-ui|warp|ghost|listener|runtime|health|mesh|rotation|open5gs|telegram" | sort'
run_nl "systemd/relevant-unit-definitions.sanitized.txt" 'for u in x-ui.service warp-svc.service ghost-vpn.service ghost-tcp-bridge.service ghost-access-nl-beta.service ghost-access-vpn-monitor.service x0tta6bl4-runtime-state.service x0tta6bl4-runtime-state.timer x0tta6bl4-listener-loss-signal.service x0tta6bl4-listener-loss-signal.timer x0tta6bl4-mesh-healthcheck.service x0tta6bl4-mesh-healthcheck.timer x0tta6bl4-rotation.service x0tta6bl4-rotation.timer x0tta6bl4-profile-status-api.service telegram-bot-simple.service; do echo "### $u"; systemctl cat "$u" --no-pager 2>/dev/null | sed -E "s/(Environment=[^=]+=).*/\1REDACTED/g; s/(LoadCredential=[^:]+:).*/\1REDACTED/g; s/(TOKEN|SECRET|PASSWORD|PRIVATE|PUBLIC|AUTH|CREDENTIAL|UUID)[A-Za-z0-9_=-]*/REDACTED/Ig"; done'

run_nl "cron/relevant.txt" 'printf "ROOT_CRONTAB\n"; crontab -l 2>/dev/null | sed -E "s/(TOKEN|SECRET|PASSWORD|PRIVATE|AUTH)[^[:space:]]*/REDACTED/Ig" || true; printf "\nCRON_D\n"; find /etc/cron.d -maxdepth 1 -type f -print -exec grep -HniE "x0tta|vpn|xray|x-ui|warp|ghost|fallback|audit|health|maintenance" {} \; 2>/dev/null | sed -E "s/(TOKEN|SECRET|PASSWORD|PRIVATE|AUTH)[^[:space:]]*/REDACTED/Ig" || true'

run_nl "network/listeners.txt" 'ss -lntup | egrep ":(443|2083|39829|2443|4433|4434|51820|8443|62789|628|2096|8388|9443)" || true'
run_nl "network/routes-addresses.txt" 'ip -brief addr; printf "\nROUTES\n"; ip route; printf "\nRULES\n"; ip rule'

run_nl "xui/inbounds.tsv" "sqlite3 -readonly /etc/x-ui/x-ui.db \"select id,port,protocol,coalesce(enable, ''),coalesce(remark, '') from inbounds order by port;\" 2>/dev/null || true"
run_nl "xui/settings.safe.tsv" "sqlite3 -readonly /etc/x-ui/x-ui.db \"select key,case when key='webBasePath' then 'REDACTED' else value end from settings where key in ('webPort','webBasePath','default_port');\" 2>/dev/null || true"
run_nl "xui/config-summary.json" 'if command -v jq >/dev/null && [ -f /usr/local/x-ui/bin/config.json ]; then jq "{api_tag:(.api.tag // null), inbound_count:(.inbounds|length), inbounds:[.inbounds[]? | {tag,port,protocol,listen,network:(.streamSettings.network // null),security:(.streamSettings.security // null)}], outbound_tags:[.outbounds[]?.tag], routing_rule_count:(.routing.rules|length // 0), stats_enabled:(has(\"stats\"))}" /usr/local/x-ui/bin/config.json; else python3 -c "import json; p=\"/usr/local/x-ui/bin/config.json\"; o=json.load(open(p)); print(json.dumps({\"api_tag\": (o.get(\"api\") or {}).get(\"tag\"), \"inbound_count\": len(o.get(\"inbounds\", [])), \"inbounds\": [{\"tag\": i.get(\"tag\"), \"port\": i.get(\"port\"), \"protocol\": i.get(\"protocol\"), \"listen\": i.get(\"listen\"), \"network\": (i.get(\"streamSettings\") or {}).get(\"network\"), \"security\": (i.get(\"streamSettings\") or {}).get(\"security\")} for i in o.get(\"inbounds\", [])], \"outbound_tags\": [x.get(\"tag\") for x in o.get(\"outbounds\", [])], \"routing_rule_count\": len((o.get(\"routing\") or {}).get(\"rules\", [])), \"stats_enabled\": \"stats\" in o}, indent=2))" 2>/dev/null || true; fi'
run_nl "xui/file-hashes.txt" 'for f in /usr/local/x-ui/x-ui /usr/local/x-ui/bin/xray-linux-amd64.real /usr/local/x-ui/bin/config.json /etc/x-ui/x-ui.db; do [ -e "$f" ] && sha256sum "$f" && stat -c "%n size=%s mtime=%y" "$f"; done'

run_nl "mesh/runtime-state-summary.json" 'if command -v jq >/dev/null && [ -f /opt/x0tta6bl4-mesh/state/runtime-state.json ]; then jq "{generated_at,mode,reason,recommended_action,hot_path_summary,probes:{listener_443_ok:.probes.listener_443_ok,xui_service_ok:.probes.xui_service_ok,warp_ok:.probes.warp_ok,ghost_ready:.probes.ghost_ready,subscription_health_status:.probes.subscription_health_status,transport_summary:.probes.transport_summary}}" /opt/x0tta6bl4-mesh/state/runtime-state.json; else sed -E "s/(uuid|password|secret|token|privateKey|publicKey|email)[^,}]*/REDACTED/Ig" /opt/x0tta6bl4-mesh/state/runtime-state.json 2>/dev/null || true; fi'
run_nl "mesh/script-hashes.txt" 'find /opt/x0tta6bl4-mesh/scripts -maxdepth 1 -type f 2>/dev/null | sort | xargs -r sha256sum'
run_nl "mesh/script-metadata.txt" 'find /opt/x0tta6bl4-mesh/scripts -maxdepth 1 -type f 2>/dev/null | sort | xargs -r stat -c "%n	size=%s	mtime=%y"'
run_nl "mesh/state-metadata.txt" 'find /opt/x0tta6bl4-mesh/state -maxdepth 1 -type f 2>/dev/null | sort | xargs -r stat -c "%n	size=%s	mtime=%y"'

run_nl "ghost-access/script-hashes.txt" 'find /opt/ghost-access-bot/current/scripts -maxdepth 1 -type f 2>/dev/null | sort | xargs -r sha256sum; [ -f /opt/ghost-access-bot/current/telegram_bot_simple.py ] && sha256sum /opt/ghost-access-bot/current/telegram_bot_simple.py'
run_nl "ghost-access/script-metadata.txt" 'find /opt/ghost-access-bot/current/scripts -maxdepth 1 -type f 2>/dev/null | sort | xargs -r stat -c "%n	size=%s	mtime=%y"; [ -f /opt/ghost-access-bot/current/telegram_bot_simple.py ] && stat -c "%n	size=%s	mtime=%y" /opt/ghost-access-bot/current/telegram_bot_simple.py'
run_nl "ghost-access/release-pointers.txt" 'readlink -f /opt/ghost-access-bot/current 2>/dev/null || true; printf "phase1_current="; cat /opt/ghost-access-bot/shared/.phase1_current_release 2>/dev/null || true; printf "\nphase1_previous="; cat /opt/ghost-access-bot/shared/.phase1_previous_release 2>/dev/null || true; printf "\nreleases_tail\n"; ls -ld /opt/ghost-access-bot/releases/* 2>/dev/null | tail -20 || true'

run_nl "ghost-vpn/file-hashes.txt" 'for f in /mnt/projects/src/network/ghost_vpn_server.py /mnt/projects/src/network/ghost_vpn_client.py /mnt/projects/src/network/ghost_vpn_protocol.py /mnt/projects/scripts/ghost_tcp_bridge.py /etc/ghost-access/nl-beta-2443.json; do [ -e "$f" ] && sha256sum "$f" && stat -c "%n size=%s mtime=%y" "$f"; done'

run_nl "provider/current-signals.txt" 'printf "BOOT_HISTORY\n"; journalctl --list-boots --no-pager | tail -10; printf "\nPROVIDER_SHUTDOWN_LINES\n"; journalctl -b -1 --no-pager 2>/dev/null | grep -Ei "guest-shutdown|hypervisor initiated shutdown|System is powering down|systemd-shutdown|poweroff|shutdown|panic|Out of memory" | tail -80 || true; printf "\nCURRENT_CPU_STEAL\n"; if command -v mpstat >/dev/null; then mpstat 1 3; else echo "mpstat unavailable"; fi; printf "\nCURRENT_IOSTAT\n"; if command -v iostat >/dev/null; then iostat -xz 1 2; else echo "iostat unavailable"; fi'
run_nl "provider/current-boot-integrity.txt" 'journalctl -b 0 --no-pager 2>/dev/null | grep -Ei "uncleanly shut down|corrupted or uncleanly|recovering journal|journal recovery|EXT4-fs|fsck|orphan" | head -100 || true'
run_nl "provider/previous-boot-gap-indicators.txt" 'journalctl -b -1 --no-pager -n 400 2>/dev/null | grep -Ei "guest-shutdown|hypervisor initiated shutdown|System is powering down|systemd-shutdown|poweroff|shutdown|panic|Out of memory|oom-killer|watchdog|hung daemon|Long readout|hogged CPU|I/O error|blocked for more|soft lockup|hard LOCKUP|timed out" | tail -160 || true'
run_nl "resources/current.txt" 'free -h; df -h /; cat /proc/loadavg; uptime'

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

cat > "$OUT_DIR/README.md" <<EOF
# Sanitized NL Server Profile

timestamp_utc: $STAMP
ssh_target: $SSH_TARGET

This profile is collected from NL using read-only commands only.
It intentionally stores summaries, metadata, and hashes instead of secrets or
full runtime databases.

Primary production truth on NL:

- x-ui service: systemd/relevant-unit-definitions.sanitized.txt
- x-ui inbounds: xui/inbounds.tsv
- x-ui config shape: xui/config-summary.json
- mesh runtime state: mesh/runtime-state-summary.json
- ghost access script hashes: ghost-access/script-hashes.txt
- ghost VPN file hashes: ghost-vpn/file-hashes.txt
- provider signals: provider/current-signals.txt

Do not treat local x0tta6bl4-xray-vps/configs/server-config.json as production
truth for NL. Real NL Xray is managed by x-ui.service.
EOF

ln -sfn "$OUT_DIR" "$OUT_BASE/latest"
echo "$OUT_DIR"
