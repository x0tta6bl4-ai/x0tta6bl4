#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"
TEMPLATE="${ROOT_DIR}/docs/team/coordination-landing.template.md"

fail() {
  printf 'coordination-contract: %s\n' "$1" >&2
  exit 1
}

require_line() {
  local file="$1"
  local needle="$2"
  grep -Fq "$needle" "$file" || fail "missing required text in ${file}: ${needle}"
}

forbid_line() {
  local file="$1"
  local needle="$2"
  if grep -Fq "$needle" "$file"; then
    fail "forbidden text present in ${file}: ${needle}"
  fi
}

[[ -f "${TEMPLATE}" ]] || fail "missing template: ${TEMPLATE}"
[[ -x ".githooks/pre-commit" ]] || fail "missing executable hook: .githooks/pre-commit"
[[ -x ".githooks/post-commit" ]] || fail "missing executable hook: .githooks/post-commit"
cmp -s "${TEMPLATE}" "COORDINATION.md" || fail \
  "COORDINATION.md drifted from landing template; run: bash scripts/agents/render_coordination_landing.sh"

require_line ".githooks/pre-commit" 'git rev-parse --git-path swarm_agent'
require_line ".githooks/pre-commit" 'scripts/agents/start_swarm_session.sh <agent-key>'
require_line ".githooks/pre-commit" 'check_swarm_ownership.py" --agent "${agent}"'
require_line ".githooks/pre-commit" 'swarm_coord.py" ensure-staged --agent "${agent}"'
require_line ".githooks/post-commit" 'git rev-parse --git-path swarm_agent'
require_line ".githooks/post-commit" 'git diff-tree --no-commit-id --name-only -r --diff-filter=ACMR HEAD'
require_line ".githooks/post-commit" 'swarm_coord.py" release --agent "${agent}" --paths'
require_line "docs/team/swarm_ownership.json" '"scripts/agents/check_coordination_contract.sh"'
require_line "docs/TEAM_RESPONSIBILITIES.md" '`scripts/agents/check_coordination_contract.sh`'

forbid_line "AGENTS.md" "verified attach on eth0"
forbid_line "AGENTS.md" "Expected: 17 VERIFIED HERE"

forbid_line "docs/05-operations/agent-sync-instructions.md" 'Use with `.paradox` (authoritative state)'
forbid_line "docs/05-operations/agent-sync-instructions.md" 'Read `.paradox` completely.'
forbid_line "docs/05-operations/agent-sync-protocol-4-agents.md" 'Primary state: `.paradox`'
forbid_line "docs/05-operations/agent-sync-protocol-4-agents.md" 'Chronological log: `.paradox.log`'

printf 'coordination-contract: ok\n'
