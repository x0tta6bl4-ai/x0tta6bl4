#!/usr/bin/env bash
# scripts/ops/verify_edge_node.sh — Lightweight verification for Edge Nodes
set -euo pipefail

grn='\033[0;32m'
red='\033[0;31m'
cyn='\033[0;36m'
rst='\033[0m'

IFACE=${1:-eth0}

echo -e "${cyn}=========================================================${rst}"
echo -e "${cyn}  x0tta6bl4 — Edge Node Verification${rst}"
echo -e "${cyn}  Host: $(hostname) | Date: $(date)${rst}"
echo -e "${cyn}=========================================================${rst}"

# 1. Kernel and Environment
if [[ $(uname -r | cut -d. -f1) -ge 6 ]]; then
    echo -e "  ${grn}PASS${rst}  Kernel version >= 6.1 ($(uname -r))"
else
    echo -e "  ${red}FAIL${rst}  Kernel version < 6.1 ($(uname -r))"
fi

if [[ -f /sys/kernel/btf/vmlinux ]]; then
    echo -e "  ${grn}PASS${rst}  BTF support present"
else
    echo -e "  ${red}FAIL${rst}  BTF support missing"
fi

if lsmod | grep -q sctp; then
    echo -e "  ${grn}PASS${rst}  SCTP module loaded"
else
    echo -e "  ${red}FAIL${rst}  SCTP module not found"
fi

# 2. Network Interface
if ip link show "${IFACE}" >/dev/null 2>&1; then
    echo -e "  ${grn}PASS${rst}  Interface ${IFACE} exists"
else
    echo -e "  ${red}FAIL${rst}  Interface ${IFACE} not found"
fi

# 3. x0tta6bl4 Datapath
if bpftool prog show name xdp_mesh_filter_prog >/dev/null 2>&1; then
    echo -e "  ${grn}LOADED${rst} XDP Program (xdp_mesh_filter_prog) in memory"
    if ip link show "${IFACE}" | grep -q xdp; then
        echo -e "  ${grn}ACTIVE${rst} XDP Program ATTACHED to ${IFACE}"
    else
        echo -e "  ${red}IDLE${rst}   XDP Program NOT ATTACHED to ${IFACE} (Safe mode)"
    fi
else
    echo -e "  ${red}MISSING${rst} XDP Program not found in kernel"
fi

# 4. Metrics Exporter
if curl -s localhost:9101/metrics | grep -q x0tta6bl4_xdp; then
    echo -e "  ${grn}RUNNING${rst} eBPF Prometheus Exporter (port 9101)"
    pps=$(curl -s localhost:9101/metrics | grep x0tta6bl4_xdp_pps | grep -v "#" | head -n1 | awk '{print $2}')
    echo -e "          Current PPS: ${pps:-0}"
else
    echo -e "  ${red}STOPPED${rst} eBPF Prometheus Exporter"
fi

# 5. VPN Integration
if ! nc -z 127.0.0.1 26969; then
    echo -e "  ${grn}PASS${rst}  Mesh port 26969 available (no conflict)"
else
    echo -e "  ${red}FAIL${rst}  Mesh port 26969 blocked/in use"
fi

if nc -z 127.0.0.1 628; then
    echo -e "  ${grn}PASS${rst}  VPN port 628 (x-ui) active"
else
    echo -e "  ${red}FAIL${rst}  VPN port 628 (x-ui) stopped"
fi

echo -e "${cyn}=========================================================${rst}"
