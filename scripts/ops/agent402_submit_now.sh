#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if [[ ! -f .tmp/non-bounty/agent402_identity.secret.json ]]; then
  python3 scripts/ops/save_agent402_api_key.py
fi

python3 scripts/ops/agent402_register_services.py --submit
