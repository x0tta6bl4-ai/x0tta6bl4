#!/usr/bin/env bash
# =============================================================================
# ebpf/prod/benchmark-harness.sh — structured eBPF build + optional PPS benchmark
#
# TWO MODES — they are deliberately separated:
#
#   Plan / compile mode (default, no root required):
#     - verifies kernel >= 6.1 and BTF presence
#     - builds the CO-RE loader (go build)
#     - prints planned benchmark steps without executing them
#     - exits 0 — suitable for CI and pre-flight checks
#     Output: "PLAN-ONLY — no traffic generated, no throughput claimed"
#
#   Live benchmark mode (RUN_BENCH=1, requires root + pktgen):
#     - attaches XDP program via verify-local.sh --live-attach
#     - configures pktgen and runs for DURATION seconds
#     - captures counters and derives measured_pps
#     - writes results/benchmark-<timestamp>.json
#     - prints PASS/FAIL against TARGET_PPS
#     Output: "BENCHMARK-RAN — measured_pps = <N>"
#     IMPORTANT: throughput figures are only valid when this path executes.
#
# Usage:
#   ebpf/prod/benchmark-harness.sh [--iface IFACE] [--duration SECS]
#                                   [--target-pps N] [--packet-size BYTES]
#                                   [--results-dir DIR] [--help]
#
#   RUN_BENCH=1 sudo -E ebpf/prod/benchmark-harness.sh --iface eth0
#
# Environment variables (all optional):
#   RUN_BENCH=1          enable live benchmark (default: 0)
#   IFACE=eth0           network interface (default: eth0)
#   DURATION=30          benchmark duration in seconds (default: 30)
#   TARGET_PPS=5000000   minimum acceptable pps (default: 5,000,000)
#   PACKET_SIZE=64       packet size in bytes (default: 64)
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GO_CACHE_DIR="${ROOT_DIR}/.tmp/go-build"
LOADER_BIN="${ROOT_DIR}/ebpf/prod/loader"

IFACE="${IFACE:-eth0}"
DURATION="${DURATION:-30}"
TARGET_PPS="${TARGET_PPS:-5000000}"
PACKET_SIZE="${PACKET_SIZE:-64}"
RUN_BENCH="${RUN_BENCH:-0}"
RESULTS_DIR="${RESULTS_DIR:-${ROOT_DIR}/ebpf/prod/results}"

usage() {
  sed -n '2,28p' "$0" | sed 's/^# \?//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iface)        IFACE="$2";        shift 2 ;;
    --duration)     DURATION="$2";     shift 2 ;;
    --target-pps)   TARGET_PPS="$2";   shift 2 ;;
    --packet-size)  PACKET_SIZE="$2";  shift 2 ;;
    --results-dir)  RESULTS_DIR="$2";  shift 2 ;;
    -h|--help)      usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

TS="$(date -u '+%Y%m%dT%H%M%SZ')"

# ── colours ───────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  GRN='\033[0;32m'; YLW='\033[0;33m'; RED='\033[0;31m'; CYN='\033[0;36m'; RST='\033[0m'
else
  GRN=''; YLW=''; RED=''; CYN=''; RST=''
fi

echo ""
echo "========================================================="
echo "  eBPF Benchmark Harness — ${TS}"
echo "  interface:   ${IFACE}"
echo "  duration:    ${DURATION}s"
echo "  target_pps:  ${TARGET_PPS}"
echo "  packet_size: ${PACKET_SIZE}B"
echo "  mode:        $([[ "${RUN_BENCH}" -eq 1 ]] && echo "LIVE BENCHMARK" || echo "PLAN-ONLY")"
echo "========================================================="
echo ""

# ── phase 1: pre-flight (always runs) ─────────────────────────────────────────
echo -e "${CYN}[1/4] Pre-flight: kernel and BTF${RST}"

python3 - <<'PY'
import pathlib, platform, re, sys
m = re.match(r"(\d+)\.(\d+)", platform.release())
if not m:
    print(f"  FAIL  unable to parse kernel release: {platform.release()}")
    sys.exit(1)
major, minor = map(int, m.groups())
if (major, minor) < (6, 1):
    print(f"  FAIL  kernel {platform.release()} < 6.1 (unsupported)")
    sys.exit(1)
print(f"  PASS  kernel {platform.release()} >= 6.1")
btf = pathlib.Path("/sys/kernel/btf/vmlinux")
if not btf.exists():
    print("  FAIL  BTF missing at /sys/kernel/btf/vmlinux")
    sys.exit(1)
print(f"  PASS  BTF present at {btf}")
PY

# ── phase 2: build verification (always runs) ──────────────────────────────────
echo ""
echo -e "${CYN}[2/4] Build: CO-RE loader compilation${RST}"

if ! command -v go >/dev/null 2>&1; then
  echo "  SKIP  go not in PATH — cannot verify build"
else
  mkdir -p "${GO_CACHE_DIR}"
  BUILD_OUTPUT="$(
    cd "${ROOT_DIR}/ebpf/prod" && env GOCACHE="${GO_CACHE_DIR}" GOTOOLCHAIN=local go build ./... 2>&1
  )" && BUILD_RC=0 || BUILD_RC=$?
  if [[ "${BUILD_RC}" -eq 0 ]]; then
    echo "  PASS  module-aware go build ./ebpf/prod → exit 0"
  elif printf '%s' "${BUILD_OUTPUT}" | grep -q "requires go >="; then
    if [[ -x "${LOADER_BIN}" ]]; then
      echo "  SKIP  local Go toolchain cannot rebuild ebpf/prod source here; using existing loader binary"
      echo "  NOTE  rebuild path: ebpf/prod/build-in-docker.sh"
    else
      echo "  SKIP  local Go toolchain cannot rebuild ebpf/prod source here"
      echo "  NOTE  build loader with: ebpf/prod/build-in-docker.sh"
    fi
  else
    echo "  FAIL  go build ./ebpf/prod failed"
    printf '%s\n' "${BUILD_OUTPUT}" >&2
    exit 1
  fi

  # Verify CO-RE generation path is wired (dry-run only)
  if make -n -f "${ROOT_DIR}/ebpf/prod/Makefile.bpf" generate 2>/dev/null | grep -q "bpf2go"; then
    echo "  PASS  CO-RE make -n shows bpf2go in plan"
  else
    echo "  WARN  CO-RE make -n did not show bpf2go — check Makefile.bpf"
  fi
fi

# ── phase 3: plan or live benchmark ───────────────────────────────────────────
echo ""
if [[ "${RUN_BENCH}" -ne 1 ]]; then
  echo -e "${CYN}[3/4] Benchmark: PLAN-ONLY (RUN_BENCH not set)${RST}"
  cat <<'PLAN'
  Planned benchmark sequence — NOT EXECUTED:

    Step 1 — attach XDP program (requires root + real NIC):
      sudo -E ebpf/prod/verify-local.sh --iface <iface> --live-attach

    Step 2 — capture pre-benchmark counters:
      ip -s link show dev <iface>
      bpftool prog show

    Step 3 — run pktgen (requires root + modprobe pktgen):
      modprobe pktgen
      RUN_BENCH=1 sudo -E ebpf/prod/benchmark-harness.sh --iface <iface>

    Step 4 — read measured pps from results/benchmark-<timestamp>.json

  IMPORTANT: no throughput figure is valid until Step 3 completes and
  measured_pps appears in the JSON results file. Do not cite PPS numbers
  from this script unless RUN_BENCH=1 was used and the JSON was produced.
PLAN

  echo ""
  echo -e "${CYN}[4/4] Summary${RST}"
  echo -e "  ${YLW}PLAN-ONLY${RST}  no traffic generated; no throughput claimed"
  echo ""
  echo "  To run a live benchmark:"
  echo "    RUN_BENCH=1 sudo -E IFACE=eth0 ebpf/prod/benchmark-harness.sh"
  echo ""
  exit 0
fi

# ── live benchmark path ────────────────────────────────────────────────────────
echo -e "${CYN}[3/4] Benchmark: LIVE (RUN_BENCH=1)${RST}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "  FAIL  live benchmark requires root (EUID=${EUID})" >&2
  echo "        run: RUN_BENCH=1 sudo -E IFACE=${IFACE} $0" >&2
  exit 1
fi

if [[ ! -d /proc/net/pktgen ]]; then
  echo "  FAIL  pktgen not loaded — run: modprobe pktgen" >&2
  exit 1
fi

if [[ ! -w /proc/net/pktgen/kpktgend_0 ]]; then
  echo "  FAIL  pktgen control file not writable" >&2
  exit 1
fi

# Attach XDP program
echo "  [attach] loading XDP via verify-local.sh --live-attach ..."
"${ROOT_DIR}/ebpf/prod/verify-local.sh" --iface "${IFACE}" --live-attach

# Capture pre-benchmark counters
RX_BEFORE=$(ip -s link show dev "${IFACE}" 2>/dev/null \
  | awk '/RX:/{getline; print $1}' || echo 0)

# Run pktgen
PGDEV="/proc/net/pktgen/${IFACE}"
echo "rem_device_all" > /proc/net/pktgen/kpktgend_0
echo "add_device ${IFACE}" > /proc/net/pktgen/kpktgend_0
echo "clone_skb 0"       > "${PGDEV}"
echo "pkt_size ${PACKET_SIZE}" > "${PGDEV}"
echo "count 0"           > "${PGDEV}"
echo "delay 0"           > "${PGDEV}"
echo "queue_map_min 0"   > "${PGDEV}"
echo "queue_map_max 0"   > "${PGDEV}"
echo ""
echo "  [pktgen] generating traffic for ${DURATION}s ..."
echo "start" > /proc/net/pktgen/pgctrl
sleep "${DURATION}"
echo "stop" > /proc/net/pktgen/pgctrl

# Capture post-benchmark counters
RX_AFTER=$(ip -s link show dev "${IFACE}" 2>/dev/null \
  | awk '/RX:/{getline; print $1}' || echo 0)
MEASURED_PPS=$(( (RX_AFTER - RX_BEFORE) / DURATION ))

# Read pktgen result for output
PKTGEN_RESULT=$(cat "${PGDEV}" 2>/dev/null || echo "(pktgen result unavailable)")

# Write results JSON
mkdir -p "${RESULTS_DIR}"
RESULT_FILE="${RESULTS_DIR}/benchmark-${TS}.json"
python3 - <<PY
import json
data = {
    "timestamp": "${TS}",
    "iface": "${IFACE}",
    "duration_s": ${DURATION},
    "packet_size_bytes": ${PACKET_SIZE},
    "target_pps": ${TARGET_PPS},
    "measured_pps": ${MEASURED_PPS},
    "pass": ${MEASURED_PPS} >= ${TARGET_PPS},
    "pktgen_raw": """${PKTGEN_RESULT}""",
    "note": "measured from ip -s link rx counter delta divided by duration"
}
with open("${RESULT_FILE}", "w") as f:
    json.dump(data, f, indent=2)
print(f"  [results] written to ${RESULT_FILE}")
PY

# ── phase 4: summary ──────────────────────────────────────────────────────────
echo ""
echo -e "${CYN}[4/4] Summary${RST}"
echo ""

if [[ "${MEASURED_PPS}" -ge "${TARGET_PPS}" ]]; then
  echo -e "  ${GRN}PASS${RST}  measured_pps=${MEASURED_PPS} >= target_pps=${TARGET_PPS}"
  echo ""
  echo "  BENCHMARK-RAN — throughput figure is valid for this run only."
  echo "  Results: ${RESULT_FILE}"
  echo ""
else
  echo -e "  ${RED}FAIL${RST}  measured_pps=${MEASURED_PPS} < target_pps=${TARGET_PPS}"
  echo ""
  echo "  BENCHMARK-RAN — throughput below target. Check XDP program and NIC."
  echo "  Results: ${RESULT_FILE}"
  echo ""
  exit 1
fi
