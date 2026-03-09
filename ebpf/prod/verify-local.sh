#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GO_CACHE_DIR="${ROOT_DIR}/.tmp/go-build"
LOADER_BIN="${ROOT_DIR}/ebpf/prod/loader"
IFACE="${IFACE:-eth0}"
LIVE_ATTACH=0
RUN_STATUS=1

detect_arch_suffix() {
  case "$(uname -m)" in
    x86_64|amd64) echo "x86" ;;
    aarch64|arm64) echo "arm64" ;;
    *) echo "x86" ;;
  esac
}

ARCH_SUFFIX="$(detect_arch_suffix)"
OBJECT_FILE="${ROOT_DIR}/ebpf/prod/meshcore_${ARCH_SUFFIX}_bpfel.o"
GENERATED_GO="${ROOT_DIR}/ebpf/prod/meshcore_${ARCH_SUFFIX}_bpfel.go"

usage() {
  cat <<'EOF'
Usage:
  verify-local.sh [--iface IFACE] [--live-attach] [--no-status]

Default behavior is non-mutating verification:
  - checks kernel version
  - checks BTF presence
  - generates CO-RE objects with bpf2go
  - builds the prod loader
  - renders the Cilium policy and dumps status

Use --live-attach to load and attach the XDP program to a real interface.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iface)
      IFACE="$2"
      shift 2
      ;;
    --live-attach)
      LIVE_ATTACH=1
      shift
      ;;
    --no-status)
      RUN_STATUS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

require_tool() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing tool: $1" >&2
    exit 1
  }
}

require_tool go
require_tool make
require_tool python3

echo "[1/5] kernel and BTF checks"
python3 - <<'PY'
import pathlib
import platform
import re

release = platform.release()
match = re.match(r"(\d+)\.(\d+)", release)
if not match:
    raise SystemExit(f"unable to parse kernel release: {release}")
major, minor = map(int, match.groups())
if (major, minor) < (6, 1):
    raise SystemExit(f"kernel {release} is unsupported; require 6.1+")
btf = pathlib.Path("/sys/kernel/btf/vmlinux")
if not btf.exists():
    raise SystemExit("BTF missing at /sys/kernel/btf/vmlinux")
print(f"kernel-ok {release}")
print(f"btf-ok {btf}")
PY

echo "[2/5] CO-RE object generation"
# This step requires clang and the cilium/ebpf bpf2go toolchain.
# It modifies the working tree (generates .o and .go files).
# The make -n dry-run confirms the plan without executing; the real build runs in CI.
if command -v clang >/dev/null 2>&1; then
  GEN_OUTPUT="$(
    make -f "${ROOT_DIR}/ebpf/prod/Makefile.bpf" -C "${ROOT_DIR}/ebpf/prod" generate 2>&1
  )" && GEN_RC=0 || GEN_RC=$?
  if [[ "${GEN_RC}" -eq 0 ]]; then
    echo "  CO-RE generation ok"
  elif printf '%s' "${GEN_OUTPUT}" | grep -q "requires go >="; then
    if [[ -f "${OBJECT_FILE}" && -f "${GENERATED_GO}" ]]; then
      echo "  CO-RE generation skipped: local Go toolchain is older than bpf2go module requirement"
      echo "  using existing generated artifacts: $(basename "${GENERATED_GO}"), $(basename "${OBJECT_FILE}")"
      echo "  regenerate path: ${ROOT_DIR}/ebpf/prod/build-in-docker.sh plus Makefile.bpf"
    else
      echo "  FAIL: local CO-RE generation blocked and generated artifacts are missing" >&2
      echo "  NEXT: ${ROOT_DIR}/ebpf/prod/build-in-docker.sh" >&2
      exit 1
    fi
  else
    printf '%s\n' "${GEN_OUTPUT}" >&2
    exit 1
  fi
else
  echo "  clang not found — running make -n to verify plan only (generation skipped)"
  make -n -f "${ROOT_DIR}/ebpf/prod/Makefile.bpf" generate 2>&1 | grep -q "bpf2go" \
    && echo "  CO-RE plan ok: bpf2go present in Makefile.bpf" \
    || { echo "  FAIL: bpf2go not found in Makefile.bpf plan" >&2; exit 1; }
  echo "  NOTE: full CO-RE generation was not executed; CO-RE .o files may be stale"
fi

echo "[3/5] building loader"
mkdir -p "${GO_CACHE_DIR}"
BUILD_OUTPUT="$(
  cd "${ROOT_DIR}/ebpf/prod" && env GOCACHE="${GO_CACHE_DIR}" GOTOOLCHAIN=local go build -o "${LOADER_BIN}" . 2>&1
)" && BUILD_RC=0 || BUILD_RC=$?

if [[ "${BUILD_RC}" -eq 0 ]]; then
  echo "  source rebuild ok -> ${LOADER_BIN}"
elif printf '%s' "${BUILD_OUTPUT}" | grep -q "requires go >="; then
  if [[ -x "${LOADER_BIN}" ]]; then
    echo "  source rebuild skipped: local Go toolchain is older than ebpf/prod module requirement"
    echo "  using existing loader binary: ${LOADER_BIN}"
    echo "  rebuild path: ${ROOT_DIR}/ebpf/prod/build-in-docker.sh"
  else
    echo "  FAIL: local Go toolchain cannot rebuild ebpf/prod and no loader binary is present" >&2
    echo "  NEXT: ${ROOT_DIR}/ebpf/prod/build-in-docker.sh" >&2
    exit 1
  fi
else
  printf '%s\n' "${BUILD_OUTPUT}" >&2
  exit 1
fi

[[ -x "${LOADER_BIN}" ]] || {
  echo "loader binary missing or not executable: ${LOADER_BIN}" >&2
  exit 1
}

echo "[4/5] loader dry-run"
loader_args=(
  --iface "${IFACE}"
  --object "${OBJECT_FILE}"
  --cilium-policy "${ROOT_DIR}/ebpf/prod/cilium-networkpolicy.yaml"
)
if [[ "${RUN_STATUS}" -eq 1 ]]; then
  loader_args+=(--dump-status)
fi

if [[ "${LIVE_ATTACH}" -eq 1 ]]; then
  echo "[5/5] live attach requested"
  if [[ "${EUID}" -ne 0 ]]; then
    require_tool sudo
    sudo -n "${LOADER_BIN}" "${loader_args[@]}" --live-attach
  else
    "${LOADER_BIN}" "${loader_args[@]}" --live-attach
  fi
else
  echo "[5/5] verification-only mode"
  "${LOADER_BIN}" "${loader_args[@]}" --dry-run
fi

echo "[EXTRA] NIC performance check"
if command -v ethtool >/dev/null 2>&1; then
  DRIVER=$(ethtool -i "${IFACE}" 2>/dev/null | grep driver | awk '{print $2}') || DRIVER="unknown"
  echo "  interface: ${IFACE}"
  echo "  driver: ${DRIVER}"
  if [[ "${DRIVER}" == "r8169" ]]; then
    echo "  ⚠️  WARNING: Realtek r8169 detected. High-speed XDP (8.8M PPS) is NOT possible on this hardware."
    echo "  ℹ️  ADVICE: Use Intel (i40e/ixgbe) or Mellanox (mlx5_core) for production DePIN nodes."
  fi
fi

echo "local eBPF verification completed"
