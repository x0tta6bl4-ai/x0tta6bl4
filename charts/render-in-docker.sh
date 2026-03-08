#!/usr/bin/env bash
# =============================================================================
# charts/render-in-docker.sh — containerised Helm render for all charts
#
# Uses the official alpine/helm image so no local Helm install is required.
# Assertions fail the script if required Kubernetes resource kinds are absent.
#
# Usage:
#   charts/render-in-docker.sh [--charts <comma-list>] [--values <file>]
#                               [--runtime docker|podman] [--help]
#
# Examples:
#   charts/render-in-docker.sh
#   charts/render-in-docker.sh --charts api-gateway,observability
#   HELM_IMAGE=alpine/helm:3.15.0 charts/render-in-docker.sh
#
# Output:
#   charts/out/<chart-name>/rendered.yaml  — full template output
#   charts/out/<chart-name>/resources.txt  — extracted kind/name list
#   charts/out/render-summary.txt          — per-chart pass/fail summary
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

RUNTIME="${CONTAINER_RUNTIME:-docker}"
HELM_IMAGE="${HELM_IMAGE:-alpine/helm:3.14.4}"
OUTPUT_DIR="${ROOT_DIR}/charts/out"
SELECTED_CHARTS=""
EXTRA_VALUES=""

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \?//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --charts)  SELECTED_CHARTS="$2"; shift 2 ;;
    --values)  EXTRA_VALUES="$2";    shift 2 ;;
    --runtime) RUNTIME="$2";         shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ── pre-flight ────────────────────────────────────────────────────────────────
command -v "${RUNTIME}" >/dev/null 2>&1 || {
  echo "container runtime not found: ${RUNTIME}" >&2
  echo "install Docker or set CONTAINER_RUNTIME=podman" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "python3 required for assertion evaluation" >&2
  exit 1
}

mkdir -p "${OUTPUT_DIR}"

# ── chart registry ────────────────────────────────────────────────────────────
# Format: "chart-dir|required-kinds (comma-separated)"
declare -a CHART_REGISTRY=(
  "charts/api-gateway|Deployment,Service,Ingress,ConfigMap"
  "charts/x0tta6bl4-commercial|ClusterRole,ClusterRoleBinding"
  "charts/observability|PrometheusRule"
  "charts/multi-tenant|Namespace,NetworkPolicy,ResourceQuota,Role,RoleBinding"
)

if [[ -n "${SELECTED_CHARTS}" ]]; then
  declare -a FILTERED=()
  IFS=',' read -ra WANT <<< "${SELECTED_CHARTS}"
  for entry in "${CHART_REGISTRY[@]}"; do
    chart_dir="${entry%%|*}"
    chart_name="$(basename "${chart_dir}")"
    for w in "${WANT[@]}"; do
      if [[ "${chart_name}" == "${w}" ]]; then
        FILTERED+=("${entry}")
      fi
    done
  done
  CHART_REGISTRY=("${FILTERED[@]+"${FILTERED[@]}"}")
fi

# ── render function ───────────────────────────────────────────────────────────
PASS=0
FAIL=0
SUMMARY_FILE="${OUTPUT_DIR}/render-summary.txt"
: > "${SUMMARY_FILE}"

render_chart() {
  local chart_dir="$1"
  local required_kinds="$2"
  local chart_name
  chart_name="$(basename "${chart_dir}")"
  local out_dir="${OUTPUT_DIR}/${chart_name}"
  local rendered="${out_dir}/rendered.yaml"
  local resources="${out_dir}/resources.txt"

  mkdir -p "${out_dir}"
  echo ""
  echo "── ${chart_name} ──────────────────────────────────────────"

  if [[ ! -d "${ROOT_DIR}/${chart_dir}" ]]; then
    echo "  SKIP  chart directory not found: ${chart_dir}"
    echo "SKIP ${chart_name}: directory not found" >> "${SUMMARY_FILE}"
    return
  fi

  # Pull dependency charts if Chart.yaml declares them
  if grep -q '^dependencies:' "${ROOT_DIR}/${chart_dir}/Chart.yaml" 2>/dev/null; then
    echo "  [dep] running dependency build..."
    "${RUNTIME}" run --rm \
      -v "${ROOT_DIR}:/workspace" \
      -w "/workspace/${chart_dir}" \
      "${HELM_IMAGE}" \
      dependency build --skip-refresh 2>/dev/null \
      || echo "  [dep] dependency build had warnings (continuing)"
  fi

  # Compose values args
  local values_args=()
  for vf in "${ROOT_DIR}/${chart_dir}/values.yaml" \
             "${ROOT_DIR}/${chart_dir}/values-enterprise.yaml"; do
    [[ -f "${vf}" ]] && values_args+=("-f" "/workspace/${vf#${ROOT_DIR}/}")
  done
  [[ -n "${EXTRA_VALUES}" ]] && values_args+=("-f" "/workspace/${EXTRA_VALUES}")

  # Render
  if "${RUNTIME}" run --rm \
      -v "${ROOT_DIR}:/workspace" \
      "${HELM_IMAGE}" \
      template "test-release" "/workspace/${chart_dir}" \
      "${values_args[@]+"${values_args[@]}"}" \
      > "${rendered}" 2>&1; then
    echo "  Rendered chart written to ${rendered}"
  else
    echo "  FAIL  helm template exited non-zero" | tee -a "${SUMMARY_FILE}"
    FAIL=$((FAIL + 1))
    return
  fi

  # Extract resource inventory
  python3 - "${rendered}" "${resources}" <<'PY'
import sys, re
rendered_path, out_path = sys.argv[1], sys.argv[2]
pattern = re.compile(r'^kind:\s*(.+)|^  name:\s*(.+)', re.MULTILINE)
items = []
current_kind = None
with open(rendered_path) as f:
    for line in f:
        km = re.match(r'^kind:\s*(.+)', line)
        nm = re.match(r'^  name:\s*(.+)', line)
        if km:
            current_kind = km.group(1).strip()
        elif nm and current_kind:
            items.append(f"{current_kind}/{nm.group(1).strip()}")
            current_kind = None
with open(out_path, 'w') as f:
    f.write('\n'.join(sorted(set(items))) + '\n')
print(f"  Resources ({len(items)}):")
for item in sorted(set(items)):
    print(f"    {item}")
PY

  # Assertions: required kinds must appear
  local missing=()
  IFS=',' read -ra KINDS <<< "${required_kinds}"
  for kind in "${KINDS[@]}"; do
    if ! grep -q "^${kind}/" "${resources}" 2>/dev/null; then
      missing+=("${kind}")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "  FAIL  missing required kinds: ${missing[*]}"
    echo "FAIL ${chart_name}: missing kinds: ${missing[*]}" >> "${SUMMARY_FILE}"
    FAIL=$((FAIL + 1))
  else
    echo "  render-ok  all required kinds present"
    echo "PASS ${chart_name}" >> "${SUMMARY_FILE}"
    PASS=$((PASS + 1))
  fi

  # Multi-tenant isolation assertions (for multi-tenant chart only)
  if [[ "${chart_name}" == "multi-tenant" || "${chart_name}" == "x0tta6bl4-commercial" ]]; then
    echo "  [isolation] checking tenant isolation resources..."
    local isolation_ok=1
    for kind in NetworkPolicy ResourceQuota; do
      grep -q "^${kind}/" "${resources}" 2>/dev/null || isolation_ok=0
    done
    if [[ "${isolation_ok}" -eq 1 ]]; then
      echo "  [isolation] NetworkPolicy + ResourceQuota present — tenant isolation scaffold verified"
    else
      echo "  [isolation] WARNING: NetworkPolicy or ResourceQuota missing — tenant isolation not rendered"
    fi
  fi
}

# ── run all charts ────────────────────────────────────────────────────────────
echo ""
echo "Rendering ${#CHART_REGISTRY[@]} chart(s) using ${RUNTIME} (${HELM_IMAGE})"

for entry in "${CHART_REGISTRY[@]}"; do
  chart_dir="${entry%%|*}"
  required_kinds="${entry##*|}"
  render_chart "${chart_dir}" "${required_kinds}"
done

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo "========================================================="
echo "  Helm render summary"
echo "========================================================="
cat "${SUMMARY_FILE}"
echo ""
echo "Passed: ${PASS} | Failed: ${FAIL}"
echo ""
echo "NOTE: This verifies template syntax and resource presence only."
echo "      It does NOT verify runtime behaviour or cluster state."

[[ "${FAIL}" -eq 0 ]] || exit 1
