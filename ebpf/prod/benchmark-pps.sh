#!/usr/bin/env bash
set -euo pipefail

IFACE="${IFACE:-eth0}"
DURATION="${DURATION:-30}"
PACKET_SIZE="${PACKET_SIZE:-64}"
TARGET_PPS="${TARGET_PPS:-5000000}"
RUN_BENCH="${RUN_BENCH:-0}"

cat <<EOF
eBPF PPS benchmark harness
interface: ${IFACE}
duration: ${DURATION}s
packet_size: ${PACKET_SIZE}B
target_pps: ${TARGET_PPS}
mode: $([[ "${RUN_BENCH}" -eq 1 ]] && echo run || echo plan-only)
EOF

if [[ "${RUN_BENCH}" -ne 1 ]]; then
  cat <<'EOF'
Planned benchmark path (not executed):
  1. Attach the XDP program with:
     ebpf/prod/verify-local.sh --iface <iface> --live-attach
  2. Generate traffic with Linux pktgen:
     modprobe pktgen
     ./ebpf/prod/benchmark-pps.sh RUN_BENCH=1 IFACE=<iface>
  3. Capture before/after counters:
     bpftool prog show
     ip -s link show dev <iface>
  4. Compare measured pps against the 5M target.
EOF
  exit 0
fi

if [[ "${EUID}" -ne 0 ]]; then
  echo "RUN_BENCH=1 requires root because pktgen writes under /proc/net/pktgen" >&2
  exit 1
fi

[[ -d /proc/net/pktgen ]] || {
  echo "pktgen is unavailable; load it with 'modprobe pktgen'" >&2
  exit 1
}

PGDEV="/proc/net/pktgen/${IFACE}"
[[ -w /proc/net/pktgen/kpktgend_0 ]] || {
  echo "pktgen control files are not writable" >&2
  exit 1
}

echo "rem_device_all" > /proc/net/pktgen/kpktgend_0
echo "add_device ${IFACE}" > /proc/net/pktgen/kpktgend_0
echo "clone_skb 0" > "${PGDEV}"
echo "pkt_size ${PACKET_SIZE}" > "${PGDEV}"
echo "count 0" > "${PGDEV}"
echo "delay 0" > "${PGDEV}"
echo "queue_map_min 0" > "${PGDEV}"
echo "queue_map_max 0" > "${PGDEV}"
echo "start" > /proc/net/pktgen/pgctrl
sleep "${DURATION}"
echo "stop" > /proc/net/pktgen/pgctrl
cat "${PGDEV}"
