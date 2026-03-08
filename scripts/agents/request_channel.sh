#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
COORD="$ROOT/scripts/agents/swarm_coord.py"

usage() {
  cat >&2 <<'EOF'
usage:
  scripts/agents/request_channel.sh sync --agent <id> [--summary <text>] [--tail <n>] [--request-id <id>]
  scripts/agents/request_channel.sh open --agent <id> --summary <text> [extra swarm_coord args]
  scripts/agents/request_channel.sh note --agent <id> --kind <kind> --message <text> [extra args]
  scripts/agents/request_channel.sh show [--request-id <id>] [extra swarm_coord args]
  scripts/agents/request_channel.sh tail [--request-id <id>] [--limit <n>] [extra swarm_coord args]
  scripts/agents/request_channel.sh close --agent <id> --result <text> [extra args]
  scripts/agents/request_channel.sh status [extra swarm_coord args]
EOF
  exit 2
}

cmd="${1:-}"
[[ -n "$cmd" ]] || usage
shift || true

case "$cmd" in
  sync)
    agent=""
    summary=""
    request_id=""
    tail_limit="${REQUEST_CHANNEL_TAIL_LIMIT:-8}"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --agent)
          agent="${2:-}"
          shift 2
          ;;
        --summary)
          summary="${2:-}"
          shift 2
          ;;
        --request-id)
          request_id="${2:-}"
          shift 2
          ;;
        --tail)
          tail_limit="${2:-}"
          shift 2
          ;;
        *)
          echo "[swarm] unknown sync argument: $1" >&2
          usage
          ;;
      esac
    done

    show_args=()
    tail_args=(--limit "$tail_limit")
    if [[ -n "$request_id" ]]; then
      show_args+=(--request-id "$request_id")
      tail_args+=(--request-id "$request_id")
    fi

    if "$COORD" show-request "${show_args[@]}" >/dev/null 2>&1; then
      "$COORD" show-request "${show_args[@]}"
      "$COORD" tail-notes "${tail_args[@]}"
      exit 0
    fi

    [[ -n "$agent" && -n "$summary" ]] || {
      echo "[swarm] sync needs --agent and --summary when no active request exists" >&2
      exit 2
    }

    open_args=(open-request --agent "$agent" --summary "$summary")
    if [[ -n "$request_id" ]]; then
      open_args+=(--request-id "$request_id")
    fi
    "$COORD" "${open_args[@]}"
    "$COORD" tail-notes "${tail_args[@]}"
    ;;
  open)
    exec "$COORD" open-request "$@"
    ;;
  note)
    exec "$COORD" post-note "$@"
    ;;
  show)
    exec "$COORD" show-request "$@"
    ;;
  tail)
    exec "$COORD" tail-notes "$@"
    ;;
  close)
    exec "$COORD" close-request "$@"
    ;;
  status)
    exec "$COORD" status "$@"
    ;;
  *)
    usage
    ;;
esac
