#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../../" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-auto}"
shift || true

PROFILE="skills/x0tta6bl4-80-20-executor/references/agent_cycle_profiles_80_20.json"
AGENTS=""
MAX_PARALLEL=2
AGENT_TIMEOUT=900
AUTO_REASON=""

resolve_mode() {
  local changed
  local tracked=""
  local untracked=""
  local timed_out=0
  local rc=0

  tracked="$(timeout 8s git -C "$ROOT_DIR" diff --name-only -- src tests skills 2>/dev/null)" || rc=$?
  if [[ "$rc" -eq 124 ]]; then
    timed_out=1
  fi
  rc=0
  untracked="$(timeout 8s git -C "$ROOT_DIR" ls-files --others --exclude-standard -- src tests skills 2>/dev/null)" || rc=$?
  if [[ "$rc" -eq 124 ]]; then
    timed_out=1
  fi

  changed="$(printf "%s\n%s\n" "$tracked" "$untracked" | sed '/^$/d' | sort -u)"

  if [[ -z "${changed}" ]]; then
    if [[ "$timed_out" -eq 1 ]]; then
      MODE="focused"
      AUTO_REASON="git scan timed out, fallback to focused"
    else
      MODE="quick"
      AUTO_REASON="no tracked changes in src/tests/skills"
    fi
    return
  fi

  if match_changed "$changed" '^(src/network/|tests/network/|tests/unit/network/|src/libx0t/network/|src/network/batman/|src/mesh/|src/data_sync/|tests/unit/data_sync/)'; then
    MODE="full"
    AUTO_REASON="network/sync changes detected"
    return
  fi

  if match_changed "$changed" '^(src/api/maas|src/api/maas_|src/services/maas_|tests/api/test_maas_|tests/unit/api/test_maas_|tests/unit/services/test_maas_)'; then
    MODE="focused"
    AUTO_REASON="maas api/service changes detected"
    return
  fi

  if match_changed "$changed" '^(src/anti_censorship/|src/coordination/|tests/chaos/|tests/unit/anti_censorship/)'; then
    MODE="focused"
    AUTO_REASON="security/coordination changes detected"
    return
  fi

  MODE="quick"
  AUTO_REASON="default fast validation"
}

match_changed() {
  local haystack="$1"
  local pattern="$2"
  if command -v rg >/dev/null 2>&1; then
    echo "$haystack" | rg -q "$pattern"
  else
    echo "$haystack" | grep -Eq "$pattern"
  fi
}

adjust_for_contention() {
  local active_pytest=0
  if command -v pgrep >/dev/null 2>&1; then
    active_pytest="$( (pgrep -fa 'python3 -m pytest' 2>/dev/null || true) | wc -l | tr -d ' ' )"
  fi

  if [[ "${active_pytest:-0}" -gt 0 ]]; then
    local extra_timeout=$((active_pytest * 150))
    if [[ "$extra_timeout" -gt 900 ]]; then
      extra_timeout=900
    fi
    AGENT_TIMEOUT=$((AGENT_TIMEOUT + extra_timeout))
    if [[ "$MAX_PARALLEL" -gt 1 ]]; then
      MAX_PARALLEL=$((MAX_PARALLEL - 1))
    fi
    echo "[80-20] contention detected: external_pytest=$active_pytest timeout=${AGENT_TIMEOUT}s max_parallel=$MAX_PARALLEL"
  fi
}

if [[ "$MODE" == "auto" ]]; then
  resolve_mode
fi

case "$MODE" in
  quick)
    AGENTS="agent-2,agent-4"
    MAX_PARALLEL=2
    AGENT_TIMEOUT=900
    ;;
  focused)
    AGENTS="agent-1,agent-2,agent-4"
    MAX_PARALLEL=3
    AGENT_TIMEOUT=2100
    ;;
  full)
    AGENTS="agent-1,agent-2,agent-3,agent-4"
    MAX_PARALLEL=4
    AGENT_TIMEOUT=2700
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    echo "Usage: $0 [auto|quick|focused|full] [extra run_agent_cycle args]" >&2
    exit 2
    ;;
esac

adjust_for_contention

if [[ -n "$AUTO_REASON" ]]; then
  echo "[80-20] auto-selected mode=$MODE ($AUTO_REASON)"
fi
echo "[80-20] mode=$MODE agents=$AGENTS profile=$PROFILE"
python3 scripts/agents/run_agent_cycle.py \
  --agents "$AGENTS" \
  --profile-file "$PROFILE" \
  --timeout "$AGENT_TIMEOUT" \
  --max-parallel "$MAX_PARALLEL" \
  "$@"
