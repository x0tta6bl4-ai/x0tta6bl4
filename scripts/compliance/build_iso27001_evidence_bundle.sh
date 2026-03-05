#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SHA="$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"
OUT_DIR="${ROOT_DIR}/evidence/iso27001/${STAMP}_${SHA}"
LOG_DIR="${OUT_DIR}/logs"
CMD_DIR="${OUT_DIR}/command_outputs"
WITH_SMOKE="${WITH_SMOKE:-false}"

mkdir -p "${LOG_DIR}" "${CMD_DIR}"

run_check() {
  local name="$1"
  shift
  local logfile="${CMD_DIR}/${name}.log"
  local start_ts end_ts rc

  start_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  {
    echo "start=${start_ts}"
    echo "cwd=${ROOT_DIR}"
    echo "cmd=$*"
    echo
    (cd "${ROOT_DIR}" && "$@")
  } >"${logfile}" 2>&1
  rc=$?
  end_ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  {
    echo "- id: ${name}"
    echo "  cmd: $*"
    echo "  rc: ${rc}"
    echo "  started_at_utc: ${start_ts}"
    echo "  ended_at_utc: ${end_ts}"
    echo "  log: command_outputs/${name}.log"
  } >>"${LOG_DIR}/checks.yml"
}

copy_if_exists() {
  local rel="$1"
  local src="${ROOT_DIR}/${rel}"
  if [[ -f "${src}" ]]; then
    mkdir -p "${OUT_DIR}/$(dirname "${rel}")"
    cp "${src}" "${OUT_DIR}/${rel}"
  fi
}

write_manifest() {
  cat >"${OUT_DIR}/MANIFEST.md" <<EOF
# ISO/IEC 27001 Evidence Bundle

- generated_at_utc: ${STAMP}
- commit_sha_short: ${SHA}
- repository_root: ${ROOT_DIR}
- with_smoke: ${WITH_SMOKE}

## Included documents

- docs/compliance/README.md
- docs/compliance/ISO_IEC_27001_2025_READINESS.md
- docs/compliance/ISO_27001_2025_SOA.md
- docs/compliance/ISO_27001_2025_EVIDENCE_INDEX.md
- docs/compliance/ISO_27001_2025_RISK_TREATMENT_PLAN.md
- docs/02-security/ci-security-gates-policy.md
- docs/operations/GOLDEN_SMOKE_PREMERGE.md
- docs/operations/MIGRATION_POLICY.md
- docs/operations/db-migration-rollback-runbook.md
- docs/team/INCIDENT_RESPONSE_PLAN.md
- docs/runbooks/INCIDENT_RESPONSE.md
- plans/MASTER_100_READINESS_TODOS_2026-02-26.md
- docs/STATUS.md
- STATUS_REALITY.md

## Command outputs

See \`logs/checks.yml\` and files under \`command_outputs/\`.
EOF
}

main() {
  write_manifest

  # Core readiness docs
  copy_if_exists "docs/compliance/README.md"
  copy_if_exists "docs/compliance/ISO_IEC_27001_2025_READINESS.md"
  copy_if_exists "docs/compliance/ISO_27001_2025_SOA.md"
  copy_if_exists "docs/compliance/ISO_27001_2025_EVIDENCE_INDEX.md"
  copy_if_exists "docs/compliance/ISO_27001_2025_RISK_TREATMENT_PLAN.md"

  # Supporting evidence docs
  copy_if_exists "docs/02-security/ci-security-gates-policy.md"
  copy_if_exists "docs/operations/GOLDEN_SMOKE_PREMERGE.md"
  copy_if_exists "docs/operations/MIGRATION_POLICY.md"
  copy_if_exists "docs/operations/db-migration-rollback-runbook.md"
  copy_if_exists "docs/team/INCIDENT_RESPONSE_PLAN.md"
  copy_if_exists "docs/runbooks/INCIDENT_RESPONSE.md"
  copy_if_exists "plans/MASTER_100_READINESS_TODOS_2026-02-26.md"
  copy_if_exists "docs/STATUS.md"
  copy_if_exists "STATUS_REALITY.md"

  # Repo metadata
  (
    cd "${ROOT_DIR}"
    git rev-parse HEAD >"${OUT_DIR}/GIT_COMMIT_SHA.txt"
    git status --short >"${OUT_DIR}/GIT_STATUS_SHORT.txt"
    git branch --show-current >"${OUT_DIR}/GIT_BRANCH.txt"
  )

  # Environment metadata
  {
    echo "generated_at_utc=${STAMP}"
    echo "python=$(python3 --version 2>&1 || true)"
    echo "bash=${BASH_VERSION}"
  } >"${OUT_DIR}/ENV_INFO.txt"

  # Command checks (non-fatal, captured in checks.yml)
  : >"${LOG_DIR}/checks.yml"
  run_check "validate_security_workflows" python3 scripts/validate_security_workflows.py || true
  run_check "check_env_security_defaults" python3 scripts/check_env_security_defaults.py || true
  run_check "check_migration_policy_depth3" python3 scripts/check_migration_policy.py --depth 3 || true
  run_check "check_db_bootstrap_chain_sqlite" python3 scripts/check_db_bootstrap_chain.py --validate-downgrade --downgrade-steps 1 || true

  if [[ "${WITH_SMOKE}" == "true" ]]; then
    run_check "golden_smoke_quick" bash scripts/golden_smoke_premerge.sh quick || true
  fi

  local archive="${OUT_DIR}.tar.gz"
  tar -czf "${archive}" -C "$(dirname "${OUT_DIR}")" "$(basename "${OUT_DIR}")"

  echo "${OUT_DIR}"
  echo "${archive}"
}

main "$@"
