#!/usr/bin/env bash
set -euo pipefail

# Reproducibility check for historically flaky API suites.
# Runs a focused subset multiple times to catch nondeterministic failures.
#
# Env:
#   API_REPRO_ROUNDS            Number of rounds (default: 2)
#   PYTEST_TIMEOUT_SECONDS      Per-test timeout (default: 1800)
#   API_REPRO_ROOT_DIR          Project root override (optional)

ROOT_DIR="${API_REPRO_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROUNDS="${API_REPRO_ROUNDS:-2}"
PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS:-1800}"

if ! [[ "${ROUNDS}" =~ ^[0-9]+$ ]] || [[ "${ROUNDS}" -lt 1 ]]; then
  echo "[api-repro] API_REPRO_ROUNDS must be a positive integer (got: ${ROUNDS})"
  exit 2
fi

SPECS=(
  "tests/api/test_maas_nodes.py -k heartbeat"
  "tests/api/test_maas_telemetry.py"
  "tests/api/test_api_error_contract.py"
)

echo "[api-repro] root=${ROOT_DIR}"
echo "[api-repro] rounds=${ROUNDS}"
echo "[api-repro] per_test_timeout=${PYTEST_TIMEOUT_SECONDS}s"

for (( round = 1; round <= ROUNDS; round++ )); do
  echo "[api-repro] round=${round}/${ROUNDS}"
  for spec in "${SPECS[@]}"; do
    echo "[api-repro] pytest ${spec}"
    timeout "${PYTEST_TIMEOUT_SECONDS}s" \
      bash -lc "cd '${ROOT_DIR}' && pytest -q ${spec} --no-cov"
  done
done

echo "[api-repro] PASSED"
