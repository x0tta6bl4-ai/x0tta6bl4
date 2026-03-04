#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

MESH_ID="${MESH_ID:-mesh-000d249803b2656f}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
DASHBOARD_URL="${DASHBOARD_URL:-http://maas.x0tta6bl4.io/dashboard/${MESH_ID}}"
ISO_EVIDENCE_SHA256="${ISO_EVIDENCE_SHA256:-fd1073472046788e430758ba1b9d644eab9bbcbce0155a987fd27fc3bf380d93}"
OBS_LOG="${OBS_LOG:-${ROOT_DIR}/docs/governance/proposals/UTRECHT_PILOT_OBSERVATION_LOG.md}"
OBS_ARTIFACT_DIR="${OBS_ARTIFACT_DIR:-${ROOT_DIR}/docs/governance/proposals/utrecht-observations}"

STAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STAMP_FILE="$(date -u +%Y%m%dT%H%M%SZ)"
DRILL_STDOUT_PATH="${OBS_ARTIFACT_DIR}/${STAMP_FILE}.drill.stdout.log"
DRILL_REPORT_COPY_PATH="${OBS_ARTIFACT_DIR}/${STAMP_FILE}.reliability.log"

mkdir -p "${OBS_ARTIFACT_DIR}"
mkdir -p "$(dirname "${OBS_LOG}")"

if [[ ! -f "${OBS_LOG}" ]]; then
  cat >"${OBS_LOG}" <<EOF
# Utrecht Pilot Observation Log

Mesh ID: \`${MESH_ID}\`  
Dashboard: \`${DASHBOARD_URL}\`  
ISO Evidence SHA256: \`${ISO_EVIDENCE_SHA256}\`

| Timestamp (UTC) | Drill Result | Drill RC | API Health | Report File | Notes |
|---|---|---:|---|---|---|
EOF
fi

set +e
DRILL_OUTPUT="$(bash "${ROOT_DIR}/scripts/ops/run_reliability_drill.sh" 2>&1)"
DRILL_RC=$?
set -e

printf '%s\n' "${DRILL_OUTPUT}" >"${DRILL_STDOUT_PATH}"

DRILL_RESULT="$(printf '%s\n' "${DRILL_OUTPUT}" | sed -n 's/^RESULT: //p' | tail -n 1)"
REPORT_FILE="$(printf '%s\n' "${DRILL_OUTPUT}" | sed -n 's/^report_file=//p' | tail -n 1)"

if [[ -z "${DRILL_RESULT}" ]]; then
  if [[ "${DRILL_RC}" -eq 0 ]]; then
    DRILL_RESULT="SUCCESS"
  else
    DRILL_RESULT="FAILURE"
  fi
fi

if [[ -n "${REPORT_FILE}" && -f "${REPORT_FILE}" ]]; then
  cp "${REPORT_FILE}" "${DRILL_REPORT_COPY_PATH}"
else
  DRILL_REPORT_COPY_PATH="n/a"
fi

if curl -fsS "${API_BASE_URL}/health" >/dev/null 2>&1; then
  API_HEALTH="reachable"
else
  API_HEALTH="unreachable"
fi

NOTES="stdout=$(basename "${DRILL_STDOUT_PATH}")"
if [[ "${DRILL_RC}" -ne 0 ]]; then
  NOTES="drill_failed_rc=${DRILL_RC}; ${NOTES}"
fi

printf '| %s | %s | %s | %s | `%s` | %s |\n' \
  "${STAMP_UTC}" \
  "${DRILL_RESULT}" \
  "${DRILL_RC}" \
  "${API_HEALTH}" \
  "${DRILL_REPORT_COPY_PATH}" \
  "${NOTES}" \
  >>"${OBS_LOG}"

printf '%s\n' "Observation recorded:"
printf '%s\n' "  timestamp_utc=${STAMP_UTC}"
printf '%s\n' "  mesh_id=${MESH_ID}"
printf '%s\n' "  drill_result=${DRILL_RESULT}"
printf '%s\n' "  drill_rc=${DRILL_RC}"
printf '%s\n' "  observation_log=${OBS_LOG}"
printf '%s\n' "  drill_stdout=${DRILL_STDOUT_PATH}"
printf '%s\n' "  drill_report_copy=${DRILL_REPORT_COPY_PATH}"

if [[ "${DRILL_RC}" -eq 0 ]]; then
  exit 0
fi

exit "${DRILL_RC}"
