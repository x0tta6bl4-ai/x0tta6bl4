#!/bin/bash
# Generate distributable VLESS Reality client profiles from the live Xray config.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CONFIG_FILE="${CONFIG_FILE:-/usr/local/etc/xray/config.json}"
CLIENT_DIR="${CLIENT_DIR:-/root/xray-clients}"
DRY_RUN=false

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    cat << EOF
Usage: sudo bash scripts/generate-live-client-profiles.sh [--dry-run]

Generates only VLESS Reality profiles from the live Xray config.
Fallback profiles are not generated.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown argument: $arg"
            usage
            exit 1
            ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root"
    exit 1
fi

require_command() {
    local command_name="$1"
    if ! command -v "$command_name" &>/dev/null; then
        log_error "Missing required command: $command_name"
        exit 1
    fi
}

is_ipv4() {
    local value="${1:-}"
    [[ "$value" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
    local IFS=.
    read -r o1 o2 o3 o4 <<< "$value"
    for octet in "$o1" "$o2" "$o3" "$o4"; do
        [[ "$octet" =~ ^[0-9]+$ ]] || return 1
        ((octet >= 0 && octet <= 255)) || return 1
    done
}

is_valid_reality_short_id() {
    local value="${1:-}"
    [[ "$value" =~ ^[0-9a-fA-F]*$ ]] || return 1
    (( ${#value} <= 16 )) || return 1
    (( ${#value} % 2 == 0 )) || return 1
}

detect_public_ipv4() {
    local endpoint value
    for endpoint in \
        "https://api.ipify.org" \
        "https://ifconfig.co/ip" \
        "https://ifconfig.me/ip"; do
        value="$(curl -fsS -4 --max-time 8 "$endpoint" 2>/dev/null | tr -d '[:space:]' || true)"
        if is_ipv4 "$value"; then
            printf '%s\n' "$value"
            return 0
        fi
    done
    log_error "Could not detect a valid public IPv4 address"
    return 1
}

write_profile() {
    local output_file="$1"
    local profile_name="$2"
    local server_ip="$3"
    local port="$4"
    local client_id="$5"
    local flow="$6"
    local server_name="$7"
    local public_key="$8"
    local short_id="$9"

    jq -n \
        --arg ps "$profile_name" \
        --arg add "$server_ip" \
        --arg port "$port" \
        --arg id "$client_id" \
        --arg flow "$flow" \
        --arg server_name "$server_name" \
        --arg public_key "$public_key" \
        --arg short_id "$short_id" \
        '{
          v: "2",
          ps: $ps,
          add: $add,
          port: $port,
          id: $id,
          aid: "0",
          scy: "auto",
          net: "tcp",
          type: "none",
          host: $server_name,
          path: "",
          tls: "reality",
          sni: $server_name,
          fp: "chrome",
          pbk: $public_key,
          sid: $short_id,
          spx: "/",
          flow: $flow
        }' > "$output_file"
}

write_qr() {
    local json_file="$1"
    local qr_file="$2"

    if command -v qrencode &>/dev/null; then
        base64 -w 0 "$json_file" | qrencode -t ANSIUTF8 -o - > "$qr_file"
    fi
}

require_command jq
require_command curl

if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
    log_error "Config file is not valid JSON: $CONFIG_FILE"
    exit 1
fi

reality_inbound="$(jq -c '([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0]) // empty' "$CONFIG_FILE")"
if [[ -z "$reality_inbound" || "$reality_inbound" == "null" ]]; then
    log_error "No VLESS Reality inbound found in $CONFIG_FILE"
    exit 1
fi

port="$(jq -r '.port // empty' <<< "$reality_inbound")"
server_name="$(jq -r '.streamSettings.realitySettings.serverNames[0] // empty' <<< "$reality_inbound")"
public_key="$(jq -r '.streamSettings.realitySettings.publicKey // empty' <<< "$reality_inbound")"
short_id="$(jq -r '.streamSettings.realitySettings.shortIds[0] // empty' <<< "$reality_inbound")"
client_count="$(jq -r '(.settings.clients // []) | length' <<< "$reality_inbound")"

if [[ -z "$port" || -z "$server_name" || -z "$public_key" || -z "$short_id" ]]; then
    log_error "Reality inbound is missing port, serverName, publicKey, or shortId"
    exit 1
fi

if ! is_valid_reality_short_id "$short_id"; then
    log_error "Reality shortId must be even-length hex up to 16 chars"
    exit 1
fi

if [[ "$client_count" -lt 1 ]]; then
    log_error "Reality inbound has no clients"
    exit 1
fi

server_ip="$(detect_public_ipv4)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

log_info "Generating VLESS Reality profiles from live config"
log_info "Public IPv4 detected"
log_info "Reality port: $port"
log_info "Reality SNI: $server_name"
log_info "Reality client count: $client_count"

for ((i = 0; i < client_count; i++)); do
    client_id="$(jq -r --argjson i "$i" '.settings.clients[$i].id // empty' <<< "$reality_inbound")"
    flow="$(jq -r --argjson i "$i" '.settings.clients[$i].flow // "xtls-rprx-vision"' <<< "$reality_inbound")"

    if [[ -z "$client_id" ]]; then
        log_error "Reality client $((i + 1)) has no UUID"
        exit 1
    fi

    index="$(printf '%02d' $((i + 1)))"
    numbered_file="$work_dir/vless-reality-${index}.json"
    write_profile "$numbered_file" "x0tta6bl4-VLESS-Reality-${index}" "$server_ip" "$port" "$client_id" "$flow" "$server_name" "$public_key" "$short_id"
    write_qr "$numbered_file" "$work_dir/vless-reality-${index}.qr.txt"

    if [[ "$i" -eq 0 ]]; then
        default_file="$work_dir/vless-reality.json"
        write_profile "$default_file" "x0tta6bl4-VLESS-Reality" "$server_ip" "$port" "$client_id" "$flow" "$server_name" "$public_key" "$short_id"
        write_qr "$default_file" "$work_dir/vless-reality.qr.txt"
    fi
done

cat > "$work_dir/README_STATUS.txt" << EOF
Generated by generate-live-client-profiles.sh from:
$CONFIG_FILE

Distribution status:
- Distribute only vless-reality*.json profiles by default.
- Do not distribute ports 8443, 9443, 8388, or 8080 until external validation
  proves the exact public port reaches this Xray server.

Runtime facts:
- Public IPv4: $server_ip
- Reality port: $port
- Reality SNI: $server_name
- Reality client profiles: $client_count
EOF

find "$work_dir" -maxdepth 1 -type f -name '*.json' -print0 | xargs -0 -r -n1 jq empty

if [[ "$DRY_RUN" == "true" ]]; then
    log_success "Dry run generated $client_count numbered profiles in a temporary directory"
    exit 0
fi

mkdir -p "$CLIENT_DIR"

disabled_dir="$CLIENT_DIR/disabled-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$disabled_dir"
for stale_name in \
    vless-xhttp.json \
    vmess-ws.json \
    trojan.json \
    shadowsocks.txt \
    shadowsocks.json \
    trojan-reality.json \
    vless-splithttp.json; do
    if [[ -f "$CLIENT_DIR/$stale_name" ]]; then
        mv "$CLIENT_DIR/$stale_name" "$disabled_dir/"
    fi
done

if ! find "$disabled_dir" -mindepth 1 -print -quit | grep -q .; then
    rmdir "$disabled_dir"
else
    log_warn "Moved stale fallback profiles to $disabled_dir"
fi

rm -f "$CLIENT_DIR"/vless-reality*.json "$CLIENT_DIR"/vless-reality*.qr.txt "$CLIENT_DIR"/README_STATUS.txt
cp "$work_dir"/* "$CLIENT_DIR"/
find "$CLIENT_DIR" -maxdepth 1 -type f -exec chown root:root {} +
find "$CLIENT_DIR" -maxdepth 1 -type f -exec chmod 0644 {} +
find "$CLIENT_DIR" -maxdepth 1 -type d -exec chmod 0755 {} +

log_success "Generated live VLESS Reality profiles in $CLIENT_DIR"
log_success "Fallback profiles were not generated"
