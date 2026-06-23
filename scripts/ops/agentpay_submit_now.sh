#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if [[ -f .tmp/non-bounty/agentpay_identity.secret.json ]]; then
  python3 scripts/ops/agentpay_register_services.py
  exit 0
fi

read -r -p "AgentPay public contact email: " AGENTPAY_EMAIL
export AGENTPAY_EMAIL
python3 scripts/ops/agentpay_register_services.py
