#!/usr/bin/env bash
set -euo pipefail

# Pre-merge quality gate for critical MaaS/API paths.
# Usage:
#   scripts/golden_smoke_premerge.sh quick
#   scripts/golden_smoke_premerge.sh full

PROFILE="${1:-quick}"
if [[ "${PROFILE}" != "quick" && "${PROFILE}" != "full" ]]; then
  echo "Usage: $0 [quick|full]"
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS:-1800}"
ALEMBIC_TIMEOUT_SECONDS="${ALEMBIC_TIMEOUT_SECONDS:-300}"

PASS_COUNT=0
FAIL_COUNT=0

run_step() {
  local name="$1"
  shift
  echo
  echo "==> ${name}"
  if "$@"; then
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "    [PASS] ${name}"
  else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "    [FAIL] ${name}"
  fi
}

DB_PATH="/tmp/maas_golden_smoke_${PROFILE}_$$.db"
DB_URL="sqlite:///${DB_PATH}"
cleanup() {
  rm -f "${DB_PATH}" "${DB_PATH}-journal"
}
trap cleanup EXIT

echo "Running golden smoke profile: ${PROFILE}"
echo "Workspace: ${ROOT_DIR}"
echo "Temp DB: ${DB_PATH}"

run_step \
  "Alembic bootstrap to head (clean SQLite DB)" \
  timeout "${ALEMBIC_TIMEOUT_SECONDS}s" \
  env DATABASE_URL="${DB_URL}" \
  alembic -c alembic.ini upgrade head

run_step \
  "Schema parity check (all ORM tables exist in DB)" \
  timeout "${ALEMBIC_TIMEOUT_SECONDS}s" \
  env DATABASE_URL="${DB_URL}" \
  python3 -c "from sqlalchemy import inspect; from src.database import Base, engine; actual=set(inspect(engine).get_table_names()); expected=set(Base.metadata.tables.keys()); missing=sorted(expected-actual); print('missing_tables=', missing); raise SystemExit(1 if missing else 0)"

run_step \
  "Requirements lock sync check" \
  timeout "60s" \
  python3 scripts/check_requirements_lock_sync.py requirements.txt requirements.lock

if [[ "${PROFILE}" == "quick" ]]; then
  TESTS=(
    "tests/unit/api/test_maas_modules.py -k Marketplace"
    "tests/core/test_connection_retry.py"
    "tests/core/test_redis_sentinel.py"
    "tests/test_resilience_advanced.py"
    "tests/unit/api/test_vpn_security_unit.py"
    "tests/api/test_maas_telemetry.py"
    "tests/api/test_maas_nodes.py -k heartbeat"
    "tests/api/test_vpn_api.py"
  )
else
  TESTS=(
    "tests/unit/api/test_maas_modules.py -k Marketplace"
    "tests/core/test_connection_retry.py"
    "tests/core/test_graceful_shutdown.py"
    "tests/core/test_redis_sentinel.py"
    "tests/test_resilience_advanced.py"
    "tests/unit/api/test_maas_security_unit.py"
    "tests/unit/api/test_vpn_security_unit.py"
    "tests/api/test_maas_mesh_endpoints.py"
    "tests/api/test_maas_playbooks.py"
    "tests/api/test_maas_marketplace.py"
    "tests/api/test_maas_escrow.py"
    "tests/api/test_maas_governance.py"
    "tests/api/test_maas_governance_edge.py"
    "tests/api/test_maas_auth.py"
    "tests/api/test_maas_analytics.py"
    "tests/api/test_maas_telemetry.py"
    "tests/api/test_maas_nodes.py -k heartbeat"
    "tests/api/test_vpn_api.py"
    "tests/test_mesh_fl_integration.py"
  )
fi

for spec in "${TESTS[@]}"; do
  run_step \
    "pytest ${spec}" \
    timeout "${PYTEST_TIMEOUT_SECONDS}s" \
    bash -lc "cd '${ROOT_DIR}' && pytest -q ${spec} --no-cov"
done

echo
echo "==== Golden Smoke Summary ===="
echo "profile: ${PROFILE}"
echo "pass:    ${PASS_COUNT}"
echo "fail:    ${FAIL_COUNT}"

if [[ "${FAIL_COUNT}" -gt 0 ]]; then
  echo "Golden smoke failed."
  exit 1
fi

echo "Golden smoke passed."
