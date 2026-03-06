#!/usr/bin/env bash
set -euo pipefail

ROOT="/mnt/projects"
EBPF_SOURCE="${ROOT}/edge/5g/ebpf/qos_enforcer.c"
ROOT_GO_MOD="${ROOT}/go.mod"
EBPF_GO_MOD="${ROOT}/edge/5g/ebpf/go.mod"

grn='\033[0;32m'
red='\033[0;31m'
nc='\033[0m'

echo "5G verification harness"
echo "Status: targeted adapter tests + static eBPF source checks"
echo

local_go="$(GOTOOLCHAIN=local go version | awk '{print $3}' | sed 's/^go//')"
root_go_req="$(sed -n 's/^go //p' "${ROOT_GO_MOD}" | head -1)"
ebpf_go_req="$(sed -n 's/^go //p' "${EBPF_GO_MOD}" | head -1)"

echo "Local Go toolchain: ${local_go}"
echo "Root module requires: ${root_go_req}"
echo "Nested edge/5g/ebpf module requires: ${ebpf_go_req}"
echo

if [[ ! -f "${EBPF_SOURCE}" ]]; then
  echo -e "${red}[FAIL]${nc} missing ${EBPF_SOURCE}"
  exit 1
fi
echo -e "${grn}[PASS]${nc} eBPF source present: ${EBPF_SOURCE}"

if ! grep -q 'slice_policy_map' "${EBPF_SOURCE}"; then
  echo -e "${red}[FAIL]${nc} slice_policy_map not found in ${EBPF_SOURCE}"
  exit 1
fi
echo -e "${grn}[PASS]${nc} slice_policy_map found"

if ! grep -q 'SEC("xdp")' "${EBPF_SOURCE}"; then
  echo -e "${red}[FAIL]${nc} SEC(\"xdp\") not found in ${EBPF_SOURCE}"
  exit 1
fi
echo -e "${grn}[PASS]${nc} XDP entrypoint found"

echo
echo "Running targeted 5G adapter tests..."
env -u GOSUMDB GOCACHE="${ROOT}/.tmp/go-build" \
  go test ./edge/5g -run 'Test(SliceManager|SimulatedUPF|Open5GS|RealEBPF)' -v

echo
if [ "$(printf '%s\n%s\n' "${local_go}" "${ebpf_go_req}" | sort -V | head -1)" != "${ebpf_go_req}" ]; then
  echo "[NOTE] edge/5g/ebpf is not promoted to VERIFIED HERE by this harness."
  echo "       local Go ${local_go} is older than nested module requirement ${ebpf_go_req}."
  echo "       use the dedicated ebpf verification/container path for live datapath work."
  echo
fi

echo -e "${grn}[PASS]${nc} 5G verification harness completed"
echo "This verifies local adapter contracts and static eBPF source shape only."
echo "It does not verify live Open5GS, live XDP attach, or throughput."
