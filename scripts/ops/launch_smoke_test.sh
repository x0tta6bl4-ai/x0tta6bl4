#!/usr/bin/env bash
# scripts/ops/launch_smoke_test.sh — External verification before public launch
set -euo pipefail

TARGET_IP="89.125.1.107"
grn='\033[0;32m'
red='\033[0;31m'
rst='\033[0m'

echo "🚀 Starting Production Launch Smoke Test for x0tta6bl4 v1.1"
echo "Target Host: ${TARGET_IP}"
echo "---------------------------------------------------------"

check_service() {
    local name=$1
    local port=$2
    if nc -zv -w 5 "${TARGET_IP}" "${port}" 2>&1 | grep -q "succeeded"; then
        echo -e "  [${grn}PASS${rst}] ${name} (Port ${port}) is reachable"
    else
        echo -e "  [${red}FAIL${rst}] ${name} (Port ${port}) is UNREACHABLE"
        return 1
    fi
}

check_http() {
    local name=$1
    local url=$2
    local expected_code=$3
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "${url}")
    if [ "${status_code}" -eq "${expected_code}" ]; then
        echo -e "  [${grn}PASS${rst}] ${name} (${url}) returned ${status_code}"
    else
        echo -e "  [${red}FAIL${rst}] ${name} (${url}) returned ${status_code} (expected ${expected_code})"
        return 1
    fi
}

# 1. Connectivity Checks
check_service "SSH" 22
check_service "VPN Control (x-ui)" 628
check_service "Prometheus" 9091
check_service "Grafana" 3000

# 2. Functional Checks
check_http "Public Landing Page" "http://${TARGET_IP}" 200
check_http "Open5GS AMF Metrics" "http://${TARGET_IP}:9091/api/v1/targets" 200

# 3. eBPF Metrics Verification
echo -n "  Checking live eBPF signal... "
if curl -s "http://${TARGET_IP}:9101/metrics" | grep -q "x0tta6bl4_xdp_pps"; then
    pps=$(curl -s "http://${TARGET_IP}:9101/metrics" | grep "x0tta6bl4_xdp_pps" | grep -v "#" | head -n1 | awk '{print $2}')
    echo -e "[${grn}OK${rst}] Signal detected. Current PPS: ${pps}"
else
    echo -e "[${red}MISSING${rst}] No eBPF metrics found on port 9101"
fi

echo "---------------------------------------------------------"
echo "✅ Smoke test completed."
