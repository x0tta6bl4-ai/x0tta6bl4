#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

mkdir -p .githooks
chmod +x .githooks/pre-commit .githooks/post-commit
git config core.hooksPath .githooks
echo "[swarm] git hooks path set to .githooks"
echo "[swarm] export SWARM_AGENT=<agent-key> before committing"
echo "[swarm] optional: export SWARM_LEASE_TTL=1800"
echo "[swarm] pre-commit now auto-checks ownership and auto-leases staged files"
echo "[swarm] recommended: scripts/agents/start_swarm_session.sh <agent-key>"
