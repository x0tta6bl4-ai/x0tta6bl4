#!/usr/bin/env bash
set -euo pipefail

# Reliability/DR drill helper for staging stack.
# Focus: fast validation of health, metrics, and degraded-dependency headers.

COMPOSE_FILE="${COMPOSE_FILE:-staging/docker-compose.quick.yml}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
REPORT_DIR="${REPORT_DIR:-/tmp}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_FILE="${REPORT_DIR}/x0tta6bl4-reliability-drill-${TIMESTAMP}.log"

mkdir -p "${REPORT_DIR}"

log() {
  printf '%s\n' "$*" | tee -a "${REPORT_FILE}"
}

run_cmd() {
  local description="$1"
  shift
  log ""
  log "## ${description}"
  if "$@" >>"${REPORT_FILE}" 2>&1; then
    log "PASS: ${description}"
    return 0
  fi
  log "FAIL: ${description}"
  return 1
}

log "# x0tta6bl4 Reliability Drill"
log "timestamp_utc=${TIMESTAMP}"
log "compose_file=${COMPOSE_FILE}"
log "api_base_url=${API_BASE_URL}"
log "report_file=${REPORT_FILE}"

failure=0

run_cmd "docker compose status" docker compose -f "${COMPOSE_FILE}" ps || failure=1
run_cmd "health endpoint returns 200" curl -fsS "${API_BASE_URL}/health" || failure=1
run_cmd "metrics endpoint returns payload" curl -fsS "${API_BASE_URL}/metrics" || failure=1

log ""
log "## degraded header probe"
HEADER_OUTPUT="$(curl -sSI "${API_BASE_URL}/health" | tr -d '\r' || true)"
if printf '%s\n' "${HEADER_OUTPUT}" | grep -qi '^X-Degraded-Dependencies:'; then
  log "INFO: degraded dependency header present on /health"
  printf '%s\n' "${HEADER_OUTPUT}" >>"${REPORT_FILE}"
else
  log "INFO: degraded dependency header absent on /health (normal when no degraded deps)"
fi

log ""
if [[ "${failure}" -eq 0 ]]; then
  log "RESULT: SUCCESS"
  exit 0
fi

log "RESULT: FAILURE"
exit 1
