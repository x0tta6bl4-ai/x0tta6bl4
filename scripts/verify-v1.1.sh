#!/usr/bin/env bash
# =============================================================================
# scripts/verify-v1.1.sh — v1.1 operator verification entrypoint
#
# Orchestrates all safe local checks and prints a three-bucket summary:
#   VERIFIED HERE         — ran and passed in this environment right now
#   VERIFIED VIA SCRIPT/CI — script exists, reproducible, not executed here
#   NOT VERIFIED YET      — blocked by hardware / credentials / environment
#
# Usage:
#   ./scripts/verify-v1.1.sh [--fast] [--json] [--help]
#
#   --fast   skip Python unit tests (they can take ~60 s)
#   --json   print final summary as JSON to stdout in addition to terminal
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

FAST=0
JSON=0
VERIFY_AGENT_NAME="${VERIFY_AGENT_NAME:-${AGENT_NAME:-lead-coordinator}}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast) FAST=1; shift ;;
    --json) JSON=1; shift ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ── terminal colours (disabled if not a tty) ──────────────────────────────────
if [[ -t 1 ]]; then
  GRN='\033[0;32m'; YLW='\033[0;33m'; RED='\033[0;31m'; CYN='\033[0;36m'; RST='\033[0m'
else
  GRN=''; YLW=''; RED=''; CYN=''; RST=''
fi

# ── result tracking ───────────────────────────────────────────────────────────
declare -a VERIFIED_HERE=()
declare -a VERIFIED_VIA_CI=()
declare -a NOT_VERIFIED=()
declare -a FAILED=()

pass()  { VERIFIED_HERE+=("$1");   echo -e "  ${GRN}PASS${RST}  $1"; }
ci()    { VERIFIED_VIA_CI+=("$1"); echo -e "  ${YLW}CI  ${RST}  $1"; }
skip()  { NOT_VERIFIED+=("$1");    echo -e "  ${CYN}SKIP${RST}  $1"; }
fail()  { FAILED+=("$1");          echo -e "  ${RED}FAIL${RST}  $1"; }

run_check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then
    pass "${label}"
  else
    fail "${label}"
  fi
}

run_helm_lint_check() {
  local chart="$1"
  local output
  if output="$(helm lint "${chart}" --quiet 2>&1)"; then
    pass "helm lint ${chart}"
    return 0
  fi
  if printf '%s' "${output}" | grep -q "snap-confine is packaged without necessary permissions"; then
    skip "helm lint ${chart} — local helm is snap-confined; use charts/render-in-docker.sh"
    return 0
  fi
  fail "helm lint ${chart}"
}

run_ebpf_build_check() {
  local output
  mkdir -p "${ROOT_DIR}/.tmp/go-build"
  if output="$(
    cd "${ROOT_DIR}/ebpf/prod" && env GOCACHE="${ROOT_DIR}/.tmp/go-build" GOTOOLCHAIN=local go build ./... 2>&1
  )"; then
    pass "go build ./ebpf/prod (module-aware)"
    return 0
  fi
  if printf '%s' "${output}" | grep -q "requires go >="; then
    skip "go build ./ebpf/prod — local Go toolchain is older than ebpf/prod module requirement"
    if [[ -f "${ROOT_DIR}/ebpf/prod/build-in-docker.sh" ]]; then
      ci "ebpf/prod containerized build (ebpf/prod/build-in-docker.sh)"
    fi
    return 0
  fi
  fail "go build ./ebpf/prod (module-aware)"
}

run_benchmark_harness_check() {
  local output
  if output="$(bash "${ROOT_DIR}/ebpf/prod/benchmark-harness.sh" 2>&1)"; then
    pass "ebpf/prod/benchmark-harness.sh plan-only"
    return 0
  fi
  if printf '%s' "${output}" | grep -q "local Go toolchain cannot rebuild ebpf/prod source here"; then
    skip "ebpf/prod/benchmark-harness.sh plan-only — local source rebuild blocked by Go toolchain"
    if [[ -f "${ROOT_DIR}/ebpf/prod/build-in-docker.sh" ]]; then
      ci "ebpf/prod benchmark preflight with containerized build path"
    fi
    return 0
  fi
  fail "ebpf/prod/benchmark-harness.sh plan-only"
}

# =============================================================================
echo ""
echo "========================================================="
echo "  x0tta6bl4 v1.1 — Verification Entrypoint"
echo "  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "========================================================="
echo ""

# ── read agent coordination state if available ────────────────────────────────
if [[ -f "${ROOT_DIR}/.agent-coord/state.json" ]]; then
  NOT_YET=$(python3 -c "
import json
s = json.load(open('${ROOT_DIR}/.agent-coord/state.json'))
items = s.get('global_not_verified_yet', [])
print(f'  [{len(items)} items still NOT VERIFIED YET — see .agent-coord/state.json]')
" 2>/dev/null || true)
  echo -e "${CYN}[coord] Agent state found.${RST} ${NOT_YET}"
  echo ""
fi

# ── 1. YAML / config syntax ───────────────────────────────────────────────────
echo -e "${CYN}[1/9] YAML and config syntax${RST}"

run_check "gitlab-ci.yml parses" \
  python3 -c 'import yaml; yaml.safe_load(open(".gitlab-ci.yml")); print("ok")'

run_check "security/sbom/gitlab-ci-sbom.yml parses" \
  python3 -c 'import yaml; yaml.safe_load(open("security/sbom/gitlab-ci-sbom.yml")); print("ok")'

run_check "charts/multi-tenant/values-enterprise.yaml parses" \
  python3 -c 'import yaml; yaml.safe_load(open("charts/multi-tenant/values-enterprise.yaml")); print("ok")'

run_check "charts/x0tta6bl4-commercial/values-enterprise.yaml parses" \
  python3 -c 'import yaml; yaml.safe_load(open("charts/x0tta6bl4-commercial/values-enterprise.yaml")); print("ok")'

# ── 2. Helm lint ──────────────────────────────────────────────────────────────
echo ""
echo -e "${CYN}[2/9] Helm chart lint${RST}"

if command -v helm >/dev/null 2>&1; then
  for chart in charts/api-gateway charts/observability charts/x0tta6bl4-commercial; do
    if [[ -d "${chart}" ]]; then
      run_helm_lint_check "${chart}"
    fi
  done
else
  skip "helm lint — helm not in PATH; use charts/render-in-docker.sh"
fi

# ── 3. eBPF loader build ──────────────────────────────────────────────────────
echo ""
echo -e "${CYN}[3/9] eBPF loader build${RST}"

if command -v go >/dev/null 2>&1; then
  run_ebpf_build_check

  run_check "CO-RE generation path wired (make -n)" \
    bash -c 'make -n -f ebpf/prod/Makefile.bpf generate 2>&1 | grep -q "bpf2go"'
else
  skip "go build ./ebpf/prod — go not in PATH"
  skip "CO-RE generation path — go not in PATH"
fi

# ── 4. Kernel and BTF ─────────────────────────────────────────────────────────
echo ""
echo -e "${CYN}[4/9] Kernel and BTF availability${RST}"

python3 - <<'PY' 2>/dev/null && pass "kernel >= 6.1" || fail "kernel >= 6.1"
import platform, re, sys
m = re.match(r"(\d+)\.(\d+)", platform.release())
if not m: sys.exit(1)
maj, min_ = map(int, m.groups())
sys.exit(0 if (maj, min_) >= (6, 1) else 1)
PY

if [[ -f /sys/kernel/btf/vmlinux ]]; then
  pass "BTF present at /sys/kernel/btf/vmlinux"
else
  fail "BTF not present at /sys/kernel/btf/vmlinux"
fi

# ── 5. Python unit tests ──────────────────────────────────────────────────────
echo ""
echo -e "${CYN}[5/9] Python unit tests${RST}"

if [[ "${FAST}" -eq 1 ]]; then
  skip "Python unit tests (skipped with --fast)"
else
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import pytest' 2>/dev/null; then
    # Run once; capture output; derive pass/fail and count from the same run
    PYTEST_OUT=$(python3 -m pytest \
        tests/unit/dao/test_governance.py \
        tests/unit/scripts/test_validate_enterprise_workflows_unit.py \
        tests/unit/mesh/test_telemetry_collector_unit.py \
        tests/benchmarks/test_api_memory_profile.py \
        --no-cov -q --tb=no 2>&1) && PYTEST_EXIT=0 || PYTEST_EXIT=$?
    COUNT=$(echo "${PYTEST_OUT}" | grep -oE "[0-9]+ passed" | head -1)
    if [[ "${PYTEST_EXIT}" -eq 0 ]] && [[ -n "${COUNT}" ]]; then
      pass "Python unit tests (${COUNT})"
    else
      fail "Python unit tests"
    fi
  else
    skip "Python unit tests — pytest not available"
  fi
fi

# ── 6. Coordination contract sanity ───────────────────────────────────────────
echo ""
echo -e "${CYN}[6/9] Coordination contract sanity${RST}"

run_check "coordination docs do not drift to manual status-board mode" \
  bash scripts/agents/check_coordination_contract.sh

# ── 7. SOC2 playbook sanity ───────────────────────────────────────────────────
echo ""
echo -e "${CYN}[7/9] SOC2 / compliance artifacts${RST}"

run_check "compliance/soc2/playbook.md contains SEV-1 definition" \
  grep -q "SEV-1" compliance/soc2/playbook.md

run_check "compliance/soc2/evidence-matrix.md exists" \
  test -f compliance/soc2/evidence-matrix.md

run_check "docs/verification/v1.1-hardening-status.md exists" \
  test -f docs/verification/v1.1-hardening-status.md

run_check "docs/verification/operator-live-validation-checklist.md exists" \
  test -f docs/verification/operator-live-validation-checklist.md

run_benchmark_harness_check

# ── 8. Docker available for containerised paths ───────────────────────────────
echo ""
echo -e "${CYN}[8/9] Container runtime (Docker)${RST}"

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  DOCKER_VER=$(docker --version 2>/dev/null | head -1)
  pass "Docker daemon reachable (${DOCKER_VER})"
  # These paths exist and are runnable but not executed here
  ci  "SBOM generation (security/sbom/run-local-sbom-check.sh full --tool-mode docker)"
  ci  "Cosign mock signing (security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker)"
  ci  "Helm render containerised (charts/render-in-docker.sh)"
else
  skip "Docker daemon not reachable — containerised paths unavailable"
fi

# ── 9. Environment-blocked checks ─────────────────────────────────────────────
echo ""
echo -e "${CYN}[9/9] Checks blocked by environment${RST}"

skip "Live XDP attach — requires root + real NIC (sudo ebpf/prod/verify-local.sh --live-attach)"
skip "PPS benchmark >5M — requires root + pktgen (RUN_BENCH=1 IFACE=eth0 ebpf/prod/benchmark-harness.sh)"
skip "Rekor transparency-log upload — requires SIGSTORE_ID_TOKEN (CI only)"
skip "5G UPF live validation — requires UERANSIM hardware/simulation cluster"
skip "LoRa field range test — requires SX1303 hardware"
skip "DP-SGD real noise validation — requires lab setup"
skip "Playwright E2E — requires running stack"
skip "k6 load test — requires running API endpoint"

# =============================================================================
# FINAL SUMMARY
# =============================================================================
echo ""
echo "========================================================="
echo "  SUMMARY"
echo "========================================================="
echo ""

if [[ ${#VERIFIED_HERE[@]} -gt 0 ]]; then
  echo -e "${GRN}VERIFIED HERE (${#VERIFIED_HERE[@]})${RST}"
  for item in "${VERIFIED_HERE[@]}"; do echo "  + ${item}"; done
  echo ""
fi

if [[ ${#VERIFIED_VIA_CI[@]} -gt 0 ]]; then
  echo -e "${YLW}VERIFIED VIA SCRIPT/CI (${#VERIFIED_VIA_CI[@]})${RST}"
  for item in "${VERIFIED_VIA_CI[@]}"; do echo "  ~ ${item}"; done
  echo ""
fi

if [[ ${#NOT_VERIFIED[@]} -gt 0 ]]; then
  echo -e "${CYN}NOT VERIFIED YET (${#NOT_VERIFIED[@]})${RST}"
  for item in "${NOT_VERIFIED[@]}"; do echo "  - ${item}"; done
  echo ""
fi

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo -e "${RED}FAILED (${#FAILED[@]})${RST}"
  for item in "${FAILED[@]}"; do echo "  ! ${item}"; done
  echo ""
fi

# Compact table
printf "  %-28s %s\n" "VERIFIED HERE:"         "${#VERIFIED_HERE[@]} checks passed in this environment"
printf "  %-28s %s\n" "VERIFIED VIA SCRIPT/CI:" "${#VERIFIED_VIA_CI[@]} reproducible scripts (not run here)"
printf "  %-28s %s\n" "NOT VERIFIED YET:"       "${#NOT_VERIFIED[@]} blocked by hardware / credentials"
if [[ ${#FAILED[@]} -gt 0 ]]; then
  printf "  %-28s %s\n" "FAILED:" "${#FAILED[@]} checks — fix before claiming verification"
fi
echo ""
echo -e "${RED}Do not claim as publicly verified:${RST}"
echo "  - PPS throughput: design target, not benchmarked"
echo "  - MTTR / uptime: derived from simulated self-healing, not production traffic"
echo "  - GNN accuracy: 94% is a training-set figure, not production measurement"
echo "  - Rekor inclusion: requires SIGSTORE_ID_TOKEN; CI only"
echo "  - 5G / LoRa / DP-SGD: simulated or hardware-blocked; not field-validated"
echo ""

# ── optional JSON output ──────────────────────────────────────────────────────
if [[ "${JSON}" -eq 1 ]]; then
  # Write arrays to temp files to avoid shell quoting issues in here-doc
  _TMP=$(mktemp -d)
  printf '%s\n' "${VERIFIED_HERE[@]+"${VERIFIED_HERE[@]}"}"  > "${_TMP}/vh.txt"
  printf '%s\n' "${VERIFIED_VIA_CI[@]+"${VERIFIED_VIA_CI[@]}"}" > "${_TMP}/vc.txt"
  printf '%s\n' "${NOT_VERIFIED[@]+"${NOT_VERIFIED[@]}"}"     > "${_TMP}/nv.txt"
  printf '%s\n' "${FAILED[@]+"${FAILED[@]}"}"                 > "${_TMP}/fa.txt"
  python3 - "${_TMP}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" <<'PY'
import json, sys, pathlib
d, ts = pathlib.Path(sys.argv[1]), sys.argv[2]
def read_list(path):
    lines = path.read_text().splitlines()
    return [l for l in lines if l.strip()]
data = {
    "timestamp":        ts,
    "verified_here":    read_list(d / "vh.txt"),
    "verified_via_ci":  read_list(d / "vc.txt"),
    "not_verified_yet": read_list(d / "nv.txt"),
    "failed":           read_list(d / "fa.txt"),
}
print(json.dumps(data, indent=2))
PY
  rm -rf "${_TMP}"
fi

# ── log result to agent coordination state ─────────────────────────────────────
if [[ -f "${ROOT_DIR}/scripts/agent-coord.sh" ]]; then
  bash "${ROOT_DIR}/scripts/agent-coord.sh" log "${VERIFY_AGENT_NAME}" "verify_run" \
    "{\"verified_here\": ${#VERIFIED_HERE[@]}, \"failed\": ${#FAILED[@]}, \"fast\": ${FAST}}" \
    2>/dev/null || true
fi

# exit non-zero if any check failed
[[ ${#FAILED[@]} -eq 0 ]] || exit 1
