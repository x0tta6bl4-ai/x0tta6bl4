#!/usr/bin/env bash
# Uses the selected environment; never installs packages or operates live backends.
set -euo pipefail
cd "$(dirname "$0")/../.."
python_bin="${PYTHON:-python3}"
"$python_bin" -m pytest --confcutdir=tests/unit/self_healing \
  tests/unit/self_healing/test_recovery_actions.py \
  tests/unit/self_healing/test_recovery_actions_unit.py \
  tests/unit/self_healing/test_recovery_actions_more.py \
  tests/unit/self_healing/test_recovery_execution_contract.py \
  -q -o addopts= --tb=short
"$python_bin" -m pytest --confcutdir=tests/integration \
  tests/integration/test_recovery_actions.py -q -o addopts= --tb=short
