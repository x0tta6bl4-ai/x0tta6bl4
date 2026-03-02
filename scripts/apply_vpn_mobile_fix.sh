#!/usr/bin/env bash
set -euo pipefail

SERVER_IP="${1:-89.125.1.107}"
SSH_USER="${2:-root}"
SSH_PORT="${SSH_PORT:-22}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-20}"

log() { printf "[vpn-mobile-fix] %s\n" "$*"; }
err() { printf "[vpn-mobile-fix] ERROR: %s\n" "$*" >&2; }

if [[ -n "${SSH_PASS:-}" ]]; then
  SSH_CMD=(sshpass -p "$SSH_PASS" ssh -T -o RequestTTY=no -o StrictHostKeyChecking=no -o ConnectTimeout="$CONNECT_TIMEOUT" -p "$SSH_PORT")
  SCP_CMD=(sshpass -p "$SSH_PASS" scp -o StrictHostKeyChecking=no -P "$SSH_PORT")
else
  SSH_CMD=(ssh -T -o RequestTTY=no -o StrictHostKeyChecking=no -o ConnectTimeout="$CONNECT_TIMEOUT" -p "$SSH_PORT")
  SCP_CMD=(scp -o StrictHostKeyChecking=no -P "$SSH_PORT")
fi

remote() {
  "${SSH_CMD[@]}" "${SSH_USER}@${SERVER_IP}" "$@"
}

REMOTE_SCRIPT="$(mktemp)"
cleanup() {
  rm -f "$REMOTE_SCRIPT"
}
trap cleanup EXIT

cat > "$REMOTE_SCRIPT" <<'REMOTE_EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "[remote] Starting VPN mobile fix on $(hostname) at $(date -u '+%Y-%m-%d %H:%M:%SZ')"

BACKUP_DIR="/root/vpn-mobile-fix-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

for cfg in /usr/local/x-ui/bin/config.json /usr/local/etc/xray/config.json; do
  if [[ -f "$cfg" ]]; then
    cp -a "$cfg" "$BACKUP_DIR/$(basename "$cfg").bak"
  fi
done

if [[ -f /etc/sysctl.d/99-vpn-mobile-latency.conf ]]; then
  cp -a /etc/sysctl.d/99-vpn-mobile-latency.conf "$BACKUP_DIR/99-vpn-mobile-latency.conf.bak"
fi

if command -v iptables-save >/dev/null 2>&1; then
  iptables-save > "$BACKUP_DIR/iptables.v4.before" || true
fi

python3 <<'PY'
import copy
import json
import os

paths = ["/usr/local/x-ui/bin/config.json", "/usr/local/etc/xray/config.json"]
changed_any = False

for path in paths:
    if not os.path.isfile(path):
        continue

    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception as exc:
        print(f"[remote] WARN: failed to parse {path}: {exc}")
        continue

    cfg_changed = False
    inbounds = cfg.get("inbounds", [])
    reality_source = None
    has_443 = False

    for inbound in inbounds:
        stream = inbound.get("streamSettings")
        if isinstance(stream, dict):
            if stream.get("network") == "tcp":
                sockopt = stream.setdefault("sockopt", {})
                if sockopt.get("tcpFastOpen") is not True:
                    sockopt["tcpFastOpen"] = True
                    cfg_changed = True
                if sockopt.get("tcpMptcp") is not False:
                    sockopt["tcpMptcp"] = False
                    cfg_changed = True

            if inbound.get("protocol") == "vless" and stream.get("security") == "reality":
                if reality_source is None:
                    reality_source = inbound
                if inbound.get("port") == 443:
                    has_443 = True

    if not has_443 and reality_source is not None:
        clone = copy.deepcopy(reality_source)
        clone["port"] = 443
        base_tag = clone.get("tag") or "vless-reality"
        clone["tag"] = f"{base_tag}-mobile443"
        inbounds.insert(0, clone)
        cfg_changed = True
        print(f"[remote] Added Reality inbound on 443 in {path}")

    if cfg_changed:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        changed_any = True
        print(f"[remote] Updated {path}")
    else:
        print(f"[remote] No config changes needed for {path}")

print(f"[remote] Config changed: {'yes' if changed_any else 'no'}")
PY

if [[ -f /usr/local/x-ui/bin/config.json ]] && [[ -d /usr/local/etc/xray ]]; then
  cp -a /usr/local/x-ui/bin/config.json /usr/local/etc/xray/config.json || true
fi

cat > /etc/sysctl.d/99-vpn-mobile-latency.conf <<'SYSCTL_EOF'
# Mobile-focused VPN latency tuning
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_mtu_probing = 1
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.ipv4.tcp_rmem = 4096 87380 33554432
net.ipv4.tcp_wmem = 4096 65536 33554432
net.core.netdev_max_backlog = 16384
net.ipv4.udp_rmem_min = 8192
net.ipv4.udp_wmem_min = 8192
SYSCTL_EOF

sysctl --system >/dev/null 2>&1 || true

add_mss_rule() {
  local chain="$1"
  if iptables -t mangle -C "$chain" -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu 2>/dev/null; then
    return 0
  fi
  iptables -t mangle -A "$chain" -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu || true
}

add_mss_rule POSTROUTING
add_mss_rule FORWARD

if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save >/dev/null 2>&1 || true
elif [[ -d /etc/iptables ]] && command -v iptables-save >/dev/null 2>&1; then
  iptables-save > /etc/iptables/rules.v4 || true
fi

if systemctl is-active --quiet x-ui; then
  systemctl restart x-ui
fi

if systemctl is-active --quiet xray; then
  systemctl restart xray
fi

sleep 2

echo "[remote] Validation:"
sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null | sed 's/^/[remote] tcp_congestion_control=/'
sysctl -n net.core.default_qdisc 2>/dev/null | sed 's/^/[remote] default_qdisc=/'
sysctl -n net.ipv4.tcp_mtu_probing 2>/dev/null | sed 's/^/[remote] tcp_mtu_probing=/'

ss -ltnp 2>/dev/null | grep -E ':(443|39829|628)\b' | sed 's/^/[remote] /' || true

python3 <<'PY'
import json
import os

for path in ("/usr/local/x-ui/bin/config.json", "/usr/local/etc/xray/config.json"):
    if not os.path.isfile(path):
        continue
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception:
        continue
    inbounds = cfg.get("inbounds", [])
    reality_443 = [
        i for i in inbounds
        if i.get("protocol") == "vless"
        and i.get("port") == 443
        and isinstance(i.get("streamSettings"), dict)
        and i["streamSettings"].get("security") == "reality"
    ]
    print(f"[remote] {path}: reality_443_count={len(reality_443)}")
PY

echo "[remote] Backup dir: $BACKUP_DIR"
echo "[remote] Done"
REMOTE_EOF

chmod +x "$REMOTE_SCRIPT"

log "Checking SSH access to ${SSH_USER}@${SERVER_IP}:${SSH_PORT}"
remote "echo '[remote] SSH OK'" >/dev/null

log "Uploading remote fixer"
"${SCP_CMD[@]}" "$REMOTE_SCRIPT" "${SSH_USER}@${SERVER_IP}:/tmp/apply_vpn_mobile_fix.remote.sh" >/dev/null

log "Applying VPN mobile fix on server"
remote "bash /tmp/apply_vpn_mobile_fix.remote.sh"

log "VPN mobile fix completed on ${SERVER_IP}"
