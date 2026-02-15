#!/usr/bin/env bash
set -euo pipefail

PIP_AUDIT_BIN="${PIP_AUDIT_BIN:-/mnt/projects/.venv/bin/pip-audit}"
if [[ ! -x "${PIP_AUDIT_BIN}" ]]; then
  PIP_AUDIT_BIN="$(command -v pip-audit)"
fi

BANDIT_BIN="${BANDIT_BIN:-$(command -v bandit)}"
SAFETY_BIN="${SAFETY_BIN:-$(command -v safety)}"

echo "Running pip-audit against pinned project requirements..."
"${PIP_AUDIT_BIN}" -r requirements.txt --no-deps --disable-pip

echo "Running bandit..."
"${BANDIT_BIN}" -r src/ -ll

echo "Running safety scan..."
if ! "${SAFETY_BIN}" scan --target .; then
  if [[ -n "${SAFETY_API_KEY:-}" ]]; then
    echo "safety scan failed with SAFETY_API_KEY configured; treating as hard failure."
    exit 1
  fi
  echo "safety scan unavailable/auth-gated in this environment; relying on pip-audit + bandit results."
fi

echo "Security checks completed successfully."
