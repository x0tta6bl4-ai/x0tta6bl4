#!/usr/bin/env bash
set -euo pipefail

# Pre-merge quality gate for critical MaaS/API paths.
# Usage:
#   scripts/golden_smoke_premerge.sh quick
#   scripts/golden_smoke_premerge.sh full
#   scripts/golden_smoke_premerge.sh full-core
#   scripts/golden_smoke_premerge.sh full-heavy

PROFILE="${1:-quick}"
case "${PROFILE}" in
  quick|full|full-core|full-heavy) ;;
  *)
    echo "Usage: $0 [quick|full|full-core|full-heavy]"
    exit 2
    ;;
esac

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS:-1800}"
ALEMBIC_TIMEOUT_SECONDS="${ALEMBIC_TIMEOUT_SECONDS:-300}"
DB_BOOTSTRAP_REQUIRE_POSTGRES="${DB_BOOTSTRAP_REQUIRE_POSTGRES:-false}"
DB_BOOTSTRAP_VALIDATE_DOWNGRADE="${DB_BOOTSTRAP_VALIDATE_DOWNGRADE:-true}"
DB_BOOTSTRAP_DOWNGRADE_STEPS="${DB_BOOTSTRAP_DOWNGRADE_STEPS:-3}"
API_REPRO_ROUNDS="${API_REPRO_ROUNDS:-2}"
API_REPRO_TIMEOUT_SECONDS="${API_REPRO_TIMEOUT_SECONDS:-2400}"

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

echo "Running golden smoke profile: ${PROFILE}"
echo "Workspace: ${ROOT_DIR}"

DB_BOOTSTRAP_ARGS=(--timeout-seconds "${ALEMBIC_TIMEOUT_SECONDS}")
if [[ "${DB_BOOTSTRAP_REQUIRE_POSTGRES}" == "true" ]]; then
  DB_BOOTSTRAP_ARGS+=(--require-postgres)
fi
if [[ "${DB_BOOTSTRAP_VALIDATE_DOWNGRADE}" == "true" ]]; then
  DB_BOOTSTRAP_ARGS+=(--validate-downgrade --downgrade-steps "${DB_BOOTSTRAP_DOWNGRADE_STEPS}")
fi

run_step \
  "DB bootstrap chain (clean SQLite + optional PostgreSQL)" \
  timeout "${ALEMBIC_TIMEOUT_SECONDS}s" \
  env POSTGRES_BOOTSTRAP_DATABASE_URL="${POSTGRES_BOOTSTRAP_DATABASE_URL:-}" \
  python3 scripts/check_db_bootstrap_chain.py "${DB_BOOTSTRAP_ARGS[@]}"

run_step \
  "Requirements lock sync check" \
  timeout "60s" \
  python3 scripts/check_requirements_lock_sync.py requirements.txt requirements.lock

run_step \
  "API model compatibility check (backward/forward)" \
  timeout "120s" \
  python3 scripts/check_api_model_compat.py

run_step \
  "Env security defaults audit (secrets + production-safe flags)" \
  timeout "120s" \
  python3 scripts/check_env_security_defaults.py

run_step \
  "Migration policy audit (idempotent style + nullable transitions)" \
  timeout "120s" \
  python3 scripts/check_migration_policy.py --depth 3

run_step \
  "Pipeline stage contract (lint -> type -> unit -> integration + smoke)" \
  timeout "120s" \
  python3 scripts/check_pipeline_stage_contract.py

run_step \
  "API reproducibility check (critical suites x${API_REPRO_ROUNDS})" \
  timeout "${API_REPRO_TIMEOUT_SECONDS}s" \
  env API_REPRO_ROUNDS="${API_REPRO_ROUNDS}" PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS}" \
  bash scripts/check_api_reproducibility.sh

QUICK_TESTS=(
  "tests/unit/agents/test_maas_health_bot_unit.py"
  "tests/unit/api/test_maas_agent_mesh_unit.py"
  "tests/unit/api/test_maas_modules.py -k Marketplace"
  "tests/core/test_connection_retry.py"
  "tests/core/test_redis_sentinel.py"
  "tests/test_resilience_advanced.py"
  "tests/api/test_billing_api.py -k circuit_breaker_open"
  "tests/unit/api/test_vpn_security_unit.py"
  "tests/api/test_maas_billing.py -k find_mesh_id_for_node"
  "tests/api/test_maas_billing.py -k build_mapek"
  "tests/api/test_maas_marketplace.py -k global_multiplier"
  "tests/unit/api/test_maas_unit.py -k heartbeat_emits_mapek_event_stream"
  "tests/api/test_vpn_api.py"
)

FULL_CORE_TESTS=(
  "tests/unit/api/test_maas_modules.py -k Marketplace"
  "tests/core/test_connection_retry.py"
  "tests/core/test_graceful_shutdown.py"
  "tests/core/test_redis_sentinel.py"
  "tests/test_resilience_advanced.py"
  "tests/api/test_billing_api.py -k circuit_breaker_open"
  "tests/unit/api/test_maas_security_unit.py"
  "tests/unit/api/test_vpn_security_unit.py"
  "tests/api/test_maas_mesh_endpoints.py"
  "tests/api/test_maas_playbooks.py"
  "tests/api/test_maas_auth.py"
  "tests/api/test_maas_analytics.py"
  "tests/api/test_maas_billing.py -k find_mesh_id_for_node"
  "tests/api/test_maas_billing.py -k build_mapek"
  "tests/api/test_maas_marketplace.py -k global_multiplier"
  "tests/unit/api/test_maas_unit.py -k heartbeat_emits_mapek_event_stream"
  "tests/api/test_vpn_api.py"
  "tests/test_mesh_fl_integration.py"
)

FULL_HEAVY_TESTS=(
  "tests/api/test_maas_marketplace.py"
  "tests/api/test_maas_escrow.py"
  "tests/api/test_maas_governance.py"
  "tests/api/test_maas_governance_edge.py"
)

case "${PROFILE}" in
  quick)
    TESTS=("${QUICK_TESTS[@]}")
    ;;
  full-core)
    TESTS=("${FULL_CORE_TESTS[@]}")
    ;;
  full-heavy)
    TESTS=("${FULL_HEAVY_TESTS[@]}")
    ;;
  full)
    TESTS=("${FULL_CORE_TESTS[@]}" "${FULL_HEAVY_TESTS[@]}")
    ;;
esac

for spec in "${TESTS[@]}"; do
  echo "==> pytest ${spec}"
  timeout "${PYTEST_TIMEOUT_SECONDS}s" \
    bash -lc "cd '${ROOT_DIR}' && pytest -q ${spec} --no-cov" || { echo "    [FAIL] pytest ${spec}"; FAIL_COUNT=$((FAIL_COUNT+1)); continue; }
  echo "    [PASS] pytest ${spec}"
  PASS_COUNT=$((PASS_COUNT+1))
done

echo
echo "==== Golden Smoke Summary ===="
echo "profile: ${PROFILE}"
echo "pass:    ${PASS_COUNT}"
echo "fail:    ${FAIL_COUNT}"

if [ "${FAIL_COUNT}" -gt 0 ]; then
  exit 1
fi

if [[ "${FAIL_COUNT}" -gt 0 ]]; then
  echo "Golden smoke failed."
  exit 1
fi

echo "Golden smoke passed."
