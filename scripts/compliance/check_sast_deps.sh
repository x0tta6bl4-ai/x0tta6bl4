#!/usr/bin/env bash
# scripts/compliance/check_sast_deps.sh
#
# Full SAST + dependency audit for Python and JS.
# Exit codes:
#   0 — all checks passed (or only warnings)
#   1 — critical vulnerabilities or bandit HIGH findings
#
# Usage:
#   ./scripts/compliance/check_sast_deps.sh [--fail-on-warn]
#
# Options:
#   --fail-on-warn   Exit 1 on any warning (strict mode for CI gates)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPORT_DIR="${ROOT_DIR}/reports/sast"
FAIL_ON_WARN="${FAIL_ON_WARN:-false}"
EXIT_CODE=0

for arg in "$@"; do
  case "$arg" in
    --fail-on-warn) FAIL_ON_WARN=true ;;
  esac
done

mkdir -p "${REPORT_DIR}"

echo "========================================================"
echo "x0tta6bl4 SAST + Dependency Audit"
echo "Root: ${ROOT_DIR}"
echo "Reports: ${REPORT_DIR}"
echo "========================================================"

# ─────────────────────────────────────────────
# 1. Bandit — Python SAST
# ─────────────────────────────────────────────
echo ""
echo "── 1. Bandit (Python SAST) ──────────────────────────────"

if ! command -v bandit &>/dev/null; then
  echo "  [SKIP] bandit not installed (pip install bandit)"
else
  BANDIT_REPORT="${REPORT_DIR}/bandit-report.json"
  set +e
  bandit -r "${ROOT_DIR}/src" \
    -lll -iii \
    -f json \
    -o "${BANDIT_REPORT}" \
    --exclude "${ROOT_DIR}/src/dao/contracts" \
    2>&1
  BANDIT_STATUS=$?
  set -e

  if [[ -f "${BANDIT_REPORT}" ]]; then
    HIGH_COUNT=$(python3 -c "
import json, sys
with open('${BANDIT_REPORT}') as f:
    d = json.load(f)
results = d.get('results', [])
high = sum(1 for r in results if r.get('issue_severity') == 'HIGH' and r.get('issue_confidence') == 'HIGH')
print(high)
" 2>/dev/null || echo "0")
    echo "  Bandit HIGH+HIGH findings: ${HIGH_COUNT}"
    echo "  Full report: ${BANDIT_REPORT}"

    if [[ "${HIGH_COUNT}" -gt 0 ]]; then
      echo "  [FAIL] ${HIGH_COUNT} HIGH severity + HIGH confidence findings"
      EXIT_CODE=1
    elif [[ "${BANDIT_STATUS}" -ne 0 ]]; then
      echo "  [WARN] Bandit returned ${BANDIT_STATUS} (medium/low findings present)"
      [[ "${FAIL_ON_WARN}" == "true" ]] && EXIT_CODE=1
    else
      echo "  [PASS] No HIGH+HIGH findings"
    fi
  else
    echo "  [SKIP] Bandit report not generated"
  fi
fi

# ─────────────────────────────────────────────
# 2. pip-audit — Python dependencies
# ─────────────────────────────────────────────
echo ""
echo "── 2. pip-audit (Python deps) ──────────────────────────"

LOCK_FILE="${ROOT_DIR}/requirements.lock"
if [[ ! -f "${LOCK_FILE}" ]]; then
  echo "  [WARN] requirements.lock not found — falling back to requirements.txt"
  LOCK_FILE="${ROOT_DIR}/requirements.txt"
fi

if ! command -v pip-audit &>/dev/null; then
  echo "  [SKIP] pip-audit not installed (pip install pip-audit)"
else
  PIP_AUDIT_REPORT="${REPORT_DIR}/pip-audit-report.json"
  set +e
  pip-audit \
    -r "${LOCK_FILE}" \
    --no-deps \
    --disable-pip \
    -f json \
    -o "${PIP_AUDIT_REPORT}" \
    2>&1
  PIP_AUDIT_STATUS=$?
  set -e

  if [[ "${PIP_AUDIT_STATUS}" -eq 0 ]]; then
    echo "  [PASS] No known vulnerabilities in ${LOCK_FILE}"
  else
    VULN_COUNT=$(python3 -c "
import json
with open('${PIP_AUDIT_REPORT}') as f:
    d = json.load(f)
print(sum(len(p.get('vulns', [])) for p in d.get('dependencies', [])))
" 2>/dev/null || echo "?")
    echo "  [FAIL] ${VULN_COUNT} vulnerabilities found — see ${PIP_AUDIT_REPORT}"
    EXIT_CODE=1
  fi
fi

# ─────────────────────────────────────────────
# 3. safety — Python CVE database (secondary)
# ─────────────────────────────────────────────
echo ""
echo "── 3. safety (Python CVE) ──────────────────────────────"

if ! command -v safety &>/dev/null; then
  echo "  [SKIP] safety not installed (pip install safety)"
else
  SAFETY_REPORT="${REPORT_DIR}/safety-report.json"
  set +e
  safety check \
    -r "${ROOT_DIR}/requirements.txt" \
    --output json \
    > "${SAFETY_REPORT}" \
    2>&1
  SAFETY_STATUS=$?
  set -e

  if [[ "${SAFETY_STATUS}" -eq 0 ]]; then
    echo "  [PASS] No vulnerabilities from safety"
  else
    echo "  [WARN] safety found issues — see ${SAFETY_REPORT}"
    [[ "${FAIL_ON_WARN}" == "true" ]] && EXIT_CODE=1
  fi
fi

# ─────────────────────────────────────────────
# 4. npm audit — JavaScript / Solidity deps
# ─────────────────────────────────────────────
echo ""
echo "── 4. npm audit (JavaScript deps) ──────────────────────"

JS_DIRS=(
  "${ROOT_DIR}/src/dao/contracts"
)

if ! command -v npm &>/dev/null; then
  echo "  [SKIP] npm not installed"
else
  for JS_DIR in "${JS_DIRS[@]}"; do
    if [[ ! -f "${JS_DIR}/package-lock.json" && ! -f "${JS_DIR}/package.json" ]]; then
      echo "  [SKIP] No package.json in ${JS_DIR}"
      continue
    fi

    echo "  Auditing: ${JS_DIR}"
    NPM_REPORT="${REPORT_DIR}/npm-audit-$(basename "${JS_DIR}").json"
    set +e
    (cd "${JS_DIR}" && npm audit --json > "${NPM_REPORT}" 2>&1)
    NPM_STATUS=$?
    set -e

    if [[ -f "${NPM_REPORT}" ]]; then
      CRITICAL=$(python3 -c "
import json
with open('${NPM_REPORT}') as f:
    d = json.load(f)
meta = d.get('metadata', {}).get('vulnerabilities', {})
print(meta.get('critical', 0) + meta.get('high', 0))
" 2>/dev/null || echo "?")
      echo "  Critical/High vulnerabilities: ${CRITICAL}"
      if [[ "${CRITICAL}" != "0" && "${CRITICAL}" != "?" ]]; then
        echo "  [FAIL] Critical/High npm vulnerabilities in ${JS_DIR}"
        EXIT_CODE=1
      else
        echo "  [PASS] No critical/high vulnerabilities"
      fi
    fi
  done
fi

# ─────────────────────────────────────────────
# 5. Summary
# ─────────────────────────────────────────────
echo ""
echo "========================================================"
if [[ "${EXIT_CODE}" -eq 0 ]]; then
  echo "RESULT: PASS — All SAST/dep checks passed"
else
  echo "RESULT: FAIL — See individual sections above"
fi
echo "Reports saved to: ${REPORT_DIR}"
echo "========================================================"

exit "${EXIT_CODE}"
