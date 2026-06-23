#!/bin/bash
# Fail unless /root/xray-clients contains only currently distributable profiles.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CONFIG_FILE="${CONFIG_FILE:-/usr/local/etc/xray/config.json}"
CLIENT_DIR="${CLIENT_DIR:-/root/xray-clients}"

CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNINGS=0

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((++CHECKS_PASSED)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((++CHECKS_FAILED)); }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; ((++CHECKS_WARNINGS)); }

if [[ $EUID -ne 0 ]]; then
    log_fail "This script must be run as root"
    exit 1
fi

require_command() {
    local command_name="$1"
    if ! command -v "$command_name" &>/dev/null; then
        log_fail "Missing required command: $command_name"
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
    return 1
}

query_portchecker() {
    local host="$1"
    local ports_json="$2"

    jq -nc --arg host "$host" --argjson ports "$ports_json" '{host: $host, ports: $ports}' |
        curl -fsS --max-time 12 \
            --request POST \
            --header 'Content-Type: application/json' \
            --data-binary @- \
            https://portchecker.io/api/query 2>/dev/null
}

json_array_contains() {
    local json_array="$1"
    local value="$2"
    jq -e --arg value "$value" 'index($value) != null' <<< "$json_array" &>/dev/null
}

is_valid_reality_short_id() {
    local value="${1:-}"
    [[ "$value" =~ ^[0-9a-fA-F]*$ ]] || return 1
    (( ${#value} <= 16 )) || return 1
    (( ${#value} % 2 == 0 )) || return 1
}

is_supported_reality_fingerprint() {
    local value
    value="$(tr '[:upper:]' '[:lower:]' <<< "${1:-}")"
    case "$value" in
        chrome|firefox|safari|ios|android|edge|360|qq|random|randomized)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

require_command jq
require_command curl

log_info "Checking client distribution gate"

if [[ ! -f "$CONFIG_FILE" ]]; then
    log_fail "Server config missing: $CONFIG_FILE"
    exit 1
fi
if jq empty "$CONFIG_FILE" 2>/dev/null; then
    log_pass "Server config is valid JSON"
else
    log_fail "Server config is invalid JSON"
    exit 1
fi

if [[ ! -d "$CLIENT_DIR" ]]; then
    log_fail "Client directory missing: $CLIENT_DIR"
    exit 1
fi
log_pass "Client directory exists"

unexpected_dirs=0
while IFS= read -r -d '' dir; do
    log_fail "Directory exists inside active client distribution dir: $(basename "$dir")"
    ((unexpected_dirs+=1))
done < <(find "$CLIENT_DIR" -mindepth 1 -maxdepth 1 -type d -print0)
if [[ "$unexpected_dirs" -eq 0 ]]; then
    log_pass "No directories exist inside active client distribution dir"
fi

reality_port="$(jq -r '([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0].port // empty)' "$CONFIG_FILE")"
server_names_json="$(jq -c '([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0].streamSettings.realitySettings.serverNames // [])' "$CONFIG_FILE")"
server_public_key="$(jq -r '([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0].streamSettings.realitySettings.publicKey // empty)' "$CONFIG_FILE")"
short_ids_json="$(jq -c '([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0].streamSettings.realitySettings.shortIds // [])' "$CONFIG_FILE")"
client_ids_json="$(jq -c '(([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0].settings.clients // []) | map(.id))' "$CONFIG_FILE")"
server_flow="$(jq -r '([.inbounds[]? | select(.protocol == "vless" and .streamSettings.security == "reality")][0].settings.clients[0].flow // empty)' "$CONFIG_FILE")"

if [[ "$reality_port" != "443" ]]; then
    log_fail "Live Reality port is '$reality_port', expected 443"
else
    log_pass "Live Reality port is 443"
fi

if [[ -z "$server_public_key" || "$server_names_json" == "[]" || "$short_ids_json" == "[]" || "$client_ids_json" == "[]" ]]; then
    log_fail "Live Reality config is missing serverNames, publicKey, shortIds, or clients"
else
    log_pass "Live Reality config contains serverNames, publicKey, shortIds, and clients"
fi

while IFS= read -r -d '' file; do
    basename="$(basename "$file")"
    case "$basename" in
        README_STATUS.txt|vless-reality.json|vless-reality-*.json|vless-reality.qr.txt|vless-reality-*.qr.txt)
            ;;
        *)
            log_fail "Non-distributable file is active in $CLIENT_DIR: $basename"
            ;;
    esac
done < <(find "$CLIENT_DIR" -maxdepth 1 -type f -print0)

if find "$CLIENT_DIR" -maxdepth 1 -type f -print0 | xargs -0 -r grep -qiE '<html|403 Forbidden|Error: Forbidden'; then
    log_fail "Active client files contain HTML or HTTP error text"
else
    log_pass "Active client files contain no HTML or HTTP error text"
fi

profile_count=0
while IFS= read -r -d '' file; do
    ((++profile_count))
    basename="$(basename "$file")"

    if jq empty "$file" 2>/dev/null; then
        log_pass "$basename is valid JSON"
    else
        log_fail "$basename is invalid JSON"
        continue
    fi

    profile_port="$(jq -r '.port // empty' "$file")"
    profile_id="$(jq -r '.id // empty' "$file")"
    profile_tls="$(jq -r '.tls // empty' "$file")"
    profile_sni="$(jq -r '.sni // empty' "$file")"
    profile_pbk="$(jq -r '.pbk // empty' "$file")"
    profile_sid="$(jq -r '.sid // empty' "$file")"
    profile_flow="$(jq -r '.flow // empty' "$file")"
    profile_fp="$(jq -r '.fp // empty' "$file")"

    [[ "$profile_port" == "$reality_port" ]] && log_pass "$basename port matches live Reality port" || log_fail "$basename port does not match live Reality port"
    [[ "$profile_tls" == "reality" ]] && log_pass "$basename uses Reality TLS" || log_fail "$basename tls is not reality"
    json_array_contains "$server_names_json" "$profile_sni" && log_pass "$basename SNI matches live Reality serverNames" || log_fail "$basename SNI does not match live Reality serverNames"
    [[ "$profile_pbk" == "$server_public_key" ]] && log_pass "$basename public key matches live Reality config" || log_fail "$basename public key does not match live Reality config"
    is_valid_reality_short_id "$profile_sid" && log_pass "$basename shortId has valid Reality format" || log_fail "$basename shortId is not even-length hex up to 16 chars"
    json_array_contains "$short_ids_json" "$profile_sid" && log_pass "$basename shortId matches live Reality config" || log_fail "$basename shortId does not match live Reality config"
    is_supported_reality_fingerprint "$profile_fp" && log_pass "$basename uses supported Reality fingerprint" || log_fail "$basename has missing or unsupported Reality fingerprint"
    json_array_contains "$client_ids_json" "$profile_id" && log_pass "$basename UUID is present in live Reality clients" || log_fail "$basename UUID is not present in live Reality clients"
    if [[ -n "$server_flow" ]]; then
        [[ "$profile_flow" == "$server_flow" ]] && log_pass "$basename flow matches live Reality flow" || log_fail "$basename flow does not match live Reality flow"
    fi
done < <(find "$CLIENT_DIR" -maxdepth 1 -type f -name 'vless-reality*.json' -print0)

if [[ "$profile_count" -lt 1 ]]; then
    log_fail "No vless-reality*.json profiles found in $CLIENT_DIR"
fi

public_ip="$(detect_public_ipv4 || true)"
if [[ -z "$public_ip" ]]; then
    log_fail "Could not detect public IPv4 for external distribution check"
else
    log_pass "Public IPv4 detected"
    portchecker_response="$(query_portchecker "$public_ip" '[443]' || true)"
    if [[ -n "$portchecker_response" ]] && jq -e '.error == false and ([.check[] | select(.port == 443 and .status == true)] | length == 1)' <<< "$portchecker_response" &>/dev/null; then
        log_pass "Independent public TCP check confirms port 443 is reachable"
    else
        log_fail "Independent public TCP check did not confirm port 443 reachability"
    fi
fi

echo
echo "Distribution gate summary:"
echo "  Passed: $CHECKS_PASSED"
echo "  Failed: $CHECKS_FAILED"
echo "  Warnings: $CHECKS_WARNINGS"

if [[ "$CHECKS_FAILED" -eq 0 ]]; then
    log_pass "Client profiles are safe to distribute"
    exit 0
fi

log_fail "Client profiles are not safe to distribute"
exit 1
