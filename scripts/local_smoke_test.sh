#!/usr/bin/env bash
set -euo pipefail

METRIC_NAME="${LOCAL_SMOKE_METRIC_NAME:-mesh_health_score}"
LISTENERS="${LOCAL_SMOKE_CHECK_LISTENERS:-0}"
HEALTH_SCORE="${LOCAL_SMOKE_HEALTH_SCORE:-20.0}"
WAIT_TIMEOUT="${LOCAL_SMOKE_WAIT_TIMEOUT:-60}"

NODE_A_URL="http://localhost:9190/metrics"
NODE_B_URL="http://localhost:9191/metrics"

pass() {
  printf '[PASS] %s\n' "$1"
}

fail() {
  printf '[FAIL] %s\n' "$1" >&2
  exit 1
}

info() {
  printf '[INFO] %s\n' "$1"
}

if [[ "${LISTENERS}" == "1" ]]; then
  info "Checking local listeners..."
  if ! command -v ss >/dev/null 2>&1; then
    fail "ss is required for listener checks but is not available"
  fi

  if ! ss -ltn 2>/dev/null | grep -q ':9090 '; then
    fail "Expected local listener on :9090 not found"
  fi
  pass "Local listener :9090 is present"

  if ! ss -ltn 2>/dev/null | grep -q ':9191 '; then
    fail "Expected local listener on :9191 not found"
  fi
  pass "Local listener :9191 is present"
else
  info "Skipping listener checks; set LOCAL_SMOKE_CHECK_LISTENERS=1 to enable"
fi

check_metrics() {
  local url="$1"
  local node="$2"
  info "Fetching metrics from ${url} (${node})..."
  local body
  body="$(mktemp)"
  trap 'rm -f "${body}"' EXIT

  local http_code
  if ! http_code="$(curl -sS -o "${body}" -w '%{http_code}' "${url}")"; then
    fail "curl request to ${url} failed"
  fi
  if [[ "${http_code}" != "200" ]]; then
    fail "Expected HTTP 200 from ${url}, got ${http_code}"
  fi
  pass "${node}: metrics endpoint returned HTTP ${http_code}"

  if ! grep -Fq "${METRIC_NAME}" "${body}"; then
    fail "${node}: metric ${METRIC_NAME} not found in ${url}"
  fi
  pass "${node}: metric ${METRIC_NAME} is present"

  local health_score
  health_score="$(grep -E "^${METRIC_NAME}[[:space:]]+" "${body}" | tail -n1 | awk '{print $2}')" || true
  if [[ -z "${health_score}" ]]; then
    fail "${node}: unable to read ${METRIC_NAME} value"
  fi
  if [[ "${health_score}" != "${HEALTH_SCORE}" ]]; then
    fail "${node}: expected ${METRIC_NAME}=${HEALTH_SCORE}, got ${health_score}"
  fi
  pass "${node}: ${METRIC_NAME}=${health_score}"

  local established
  established="$(grep -E "^mesh_established_sessions[[:space:]]+" "${body}" | tail -n1 | awk '{print $2}')" || true
  if [[ -z "${established}" ]]; then
    fail "${node}: unable to read mesh_established_sessions value"
  fi
  if [[ "${established}" != "0" ]]; then
    fail "${node}: expected mesh_established_sessions=0, got ${established}"
  fi
  pass "${node}: mesh_established_sessions=${established}"
}

wait_for_url() {
  local url="$1"
  local deadline
  deadline="$(($(date +%s) + WAIT_TIMEOUT))"
  info "Waiting up to ${WAIT_TIMEOUT}s for ${url}..."
  while true; do
    if curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "${url}" 2>/dev/null | grep -q '^200$'; then
      pass "${url} is responsive"
      return 0
    fi
    if [[ "$(date +%s)" -ge "${deadline}" ]]; then
      fail "Timed out waiting for ${url} after ${WAIT_TIMEOUT}s"
    fi
    sleep 2
  done
}

wait_for_url "${NODE_A_URL}"
wait_for_url "${NODE_B_URL}"

check_metrics "${NODE_A_URL}" "mesh-node"
check_metrics "${NODE_B_URL}" "mesh-node-2"

info "All local smoke checks passed"
