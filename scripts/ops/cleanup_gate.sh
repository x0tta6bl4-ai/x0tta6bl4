#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-staging/docker-compose.quick.yml}"

echo "[cleanup-gate] using compose file: ${COMPOSE_FILE}"

echo "[cleanup-gate] step 1/6: docker compose ps"
docker compose -f "${COMPOSE_FILE}" ps

echo "[cleanup-gate] step 2/6: /health"
HEALTH_JSON="$(curl -fsS http://localhost:8000/health)"
echo "${HEALTH_JSON}" | python3 -m json.tool | sed -n '1,12p'

echo "[cleanup-gate] step 3/6: /metrics"
METRICS_HEAD="$(curl -fsS http://localhost:8000/metrics | head -n 30)"
if [[ -z "${METRICS_HEAD}" ]]; then
  echo "[cleanup-gate] ERROR: /metrics returned empty payload"
  exit 1
fi
if grep -q '"detail":"Not Found"' <<<"${METRICS_HEAD}"; then
  echo "[cleanup-gate] ERROR: /metrics returned 404 payload"
  exit 1
fi
echo "${METRICS_HEAD}"

echo "[cleanup-gate] step 4/6: make status"
make status

echo "[cleanup-gate] step 5/6: make test"
make test

echo "[cleanup-gate] step 6/6: make agent-cycle-dry"
make agent-cycle-dry

echo "[cleanup-gate] PASS"
