#!/usr/bin/env bash
set -euo pipefail

log() { printf "\033[1;32m[+]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[!]\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m[-]\033[0m %s\n" "$*"; }

# Require root
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  err "Run as root"; exit 1
fi

PORT="39829"
ASSET_DIR="/usr/local/share/xray"
CFG_DIR="/usr/local/etc/xray"
CFG="$CFG_DIR/config.json"
BACKUP_DIR="/root/xray_backup_$(date +%Y%m%d_%H%M%S)"

log "Stopping and removing old Xray (if any)"
systemctl stop xray 2>/dev/null || true
systemctl disable xray 2>/dev/null || true

mkdir -p "$BACKUP_DIR" || true
if [ -d "$CFG_DIR" ]; then
  cp -r "$CFG_DIR"/* "$BACKUP_DIR"/ 2>/dev/null || true
fi

rm -f /usr/local/bin/xray || true
rm -rf "$CFG_DIR" || true
rm -rf /var/log/xray || true
rm -f /etc/systemd/system/xray.service || true
rm -rf /etc/systemd/system/xray.service.d || true
systemctl daemon-reload || true

log "Installing latest Xray via official script"
apt-get update -y >/dev/null 2>&1 || true
apt-get install -y curl jq >/dev/null 2>&1 || true
bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

log "Installed version:"; xray version || true

log "Generating Reality keypair and client UUIDs"
KEYS="$(xray x25519)"
PRIVATE_KEY="$(printf '%s\n' "$KEYS" | awk -F': ' '/Private key/{print $2}')"
PUBLIC_KEY="$(printf '%s\n' "$KEYS" | awk -F': ' '/Public key/{print $2}')"
UUID_DESKTOP="$(xray uuid)"
UUID_MOBILE="$(xray uuid)"

log "Writing config to $CFG"
install -d -m 0755 "$CFG_DIR" /var/log/xray "$ASSET_DIR"

cat > "$CFG" <<EOF
{
  "log": {
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log",
    "loglevel": "warning",
    "dnsLog": false
  },
  "dns": {
    "servers": [
      { "address": "https://dns.adguard.com/dns-query" },
      "https://1.1.1.1/dns-query",
      "https://dns.google/dns-query"
    ],
    "queryStrategy": "UseIPv4"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": $PORT,
      "protocol": "vless",
      "tag": "inbound-$PORT",
      "settings": {
        "clients": [
          { "id": "$UUID_DESKTOP", "flow": "xtls-rprx-vision", "email": "x0tta6bl4_desktop" },
          { "id": "$UUID_MOBILE",  "flow": "xtls-rprx-vision", "email": "x0tta6bl4_mobile" }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "fingerprint": "chrome",
          "dest": "www.google.com:443",
          "serverNames": [
            "www.google.com","google.com","www.youtube.com",
            "fonts.googleapis.com","fonts.gstatic.com","ajax.googleapis.com",
            "www.gstatic.com","accounts.google.com","clients4.google.com"
          ],
          "privateKey": "$PRIVATE_KEY",
          "publicKey": "$PUBLIC_KEY",
          "shortIds": ["6b","97","a1","b2","c3","d4"],
          "spiderX": "/watch?v=dQw4w9WgXcQ",
          "spiderY": "/s/player/",
          "maxTimediff": 300
        },
        "tcpSettings": { "header": { "type": "none" }, "acceptProxyProtocol": false }
      },
      "sniffing": { "enabled": false }
    }
  ],
  "outbounds": [
    { "protocol": "freedom",  "tag": "direct" },
    { "protocol": "blackhole", "tag": "blocked" }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      { "type": "field", "protocol": ["bittorrent"], "outboundTag": "blocked" },
      { "type": "field", "outboundTag": "blocked", "domainKeyword": ["ad","ads","doubleclick","googlesyndication"] },
      { "type": "field", "ip": ["geoip:private"], "outboundTag": "blocked" }
    ]
  },
  "stats": {},
  "policy": { "levels": { "0": { "statsUserUplink": true, "statsUserDownlink": true } }, "system": { "statsInboundUplink": true, "statsInboundDownlink": true } }
}
EOF

log "Creating systemd drop-in for assets path"
install -d -m 0755 /etc/systemd/system/xray.service.d
cat > /etc/systemd/system/xray.service.d/override.conf <<EOF
[Service]
Environment=XRAY_LOCATION_ASSET=$ASSET_DIR
EOF

log "Enabling time sync"
if command -v timedatectl >/dev/null 2>&1; then
  timedatectl set-ntp true || true
fi

log "Validating config"
XRAY_LOCATION_ASSET="$ASSET_DIR" xray run -test -c "$CFG"

log "Enabling and starting Xray"
systemctl daemon-reload
systemctl enable xray
systemctl restart xray
sleep 1

log "Listener check"
ss -ltnp | awk -v p=":"$PORT" '$4 ~ p {print}' || true

log "Saving keys and links to /root"
{
  echo "Private Key: $PRIVATE_KEY"
  echo "Public  Key: $PUBLIC_KEY"
  echo "UUID Desktop: $UUID_DESKTOP"
  echo "UUID Mobile : $UUID_MOBILE"
} > /root/xray_keys.txt

{
  echo "vless://$UUID_DESKTOP@$(hostname -I | awk '{print $1}'):$PORT?type=tcp&encryption=none&security=reality&pbk=$PUBLIC_KEY&fp=chrome&sni=www.google.com&sid=6b&spx=%2Fwatch%3Fv%3DdQw4w9WgXcQ&flow=xtls-rprx-vision#x0tta6bl4_NL_desktop"
  echo "vless://$UUID_MOBILE@$(hostname -I | awk '{print $1}'):$PORT?type=tcp&encryption=none&security=reality&pbk=$PUBLIC_KEY&fp=chrome&sni=www.google.com&sid=6b&spx=%2Fwatch%3Fv%3DdQw4w9WgXcQ&flow=xtls-rprx-vision#x0tta6bl4_NL_mobile"
} > /root/vless_links.txt

log "Done. Keys: /root/xray_keys.txt, Links: /root/vless_links.txt"
