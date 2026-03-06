#!/usr/bin/env bash
# =============================================================================
# scripts/agent-coord.sh — shared agent coordination helper
#
# Front door for all agents (claude, gemini, codex, etc.) at session start/end.
# Compatibility state: /mnt/projects/.agent-coord/
# Authoritative request thread: shared swarm state via scripts/agents/request_channel.sh
#
# Usage:
#   source scripts/agent-coord.sh         (loads functions)
#   scripts/agent-coord.sh status         (print global state)
#   scripts/agent-coord.sh inbox AGENT    (show inbox for AGENT)
#   scripts/agent-coord.sh log AGENT EVENT [JSON...]   (append log entry)
#   scripts/agent-coord.sh send FROM TO SUBJECT BODY   (drop inbox message)
#   scripts/agent-coord.sh session_start AGENT [SUMMARY]
#   scripts/agent-coord.sh session_end AGENT [JSON-PAYLOAD]
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COORD_DIR="${X0TTA6BL4_AGENT_COORD_DIR:-${ROOT_DIR}/.agent-coord}"
STATE="${COORD_DIR}/state.json"
LOG="${COORD_DIR}/log.jsonl"
REQUEST_CHANNEL="${ROOT_DIR}/scripts/agents/request_channel.sh"
SWARM_COORD="${ROOT_DIR}/scripts/agents/swarm_coord.py"
VALIDATION_PREFLIGHT="${ROOT_DIR}/scripts/agents/validation_preflight.sh"
ROADMAP_QUEUE="${ROOT_DIR}/plans/ROADMAP_AGENT_QUEUE.json"

mkdir -p "${COORD_DIR}/inbox"

if [[ ! -f "${STATE}" ]]; then
  python3 - "${STATE}" <<'PY'
import json, sys
state_path = sys.argv[1]
payload = {
    "_format": "x0tta6bl4 agent coordination state v1",
    "_updated": None,
    "_note": "Shared by all agents on /mnt/projects. Read on session start, update on session end.",
    "agents": {
        "claude": {
            "role": "verification/evidence/compliance",
            "scope": [
                "scripts/verify-v1.1.sh",
                "docs/verification/",
                "compliance/soc2/",
                "security/sbom/"
            ],
            "last_active": None,
            "last_verified_here": [],
            "status": "unknown"
        },
        "gemini": {
            "role": "eBPF datapath / live attach",
            "scope": [
                "ebpf/prod/",
                "edge/5g/ebpf/"
            ],
            "last_active": None,
            "last_verified_here": [],
            "status": "unknown"
        },
        "codex": {
            "role": "5G/Open5GS transport / integration tests",
            "scope": [
                "edge/5g/",
                "integration/",
                "test/"
            ],
            "last_active": None,
            "last_verified_here": [],
            "status": "unknown"
        }
    },
    "global_verified_here": {
        "updated": None,
        "items": []
    },
    "global_not_verified_yet": [],
    "do_not_claim_publicly": []
}
with open(state_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=True, indent=2)
    fh.write("\n")
PY
fi

request_channel_available() {
  [[ -x "${REQUEST_CHANNEL}" ]]
}

request_has_active() {
  request_channel_available && "${REQUEST_CHANNEL}" show >/dev/null 2>&1
}

request_sync() {
  local agent="${1:-}"
  local summary="${2:-}"
  request_channel_available || return 0
  if [[ -n "${summary}" ]]; then
    "${REQUEST_CHANNEL}" sync --agent "${agent}" --summary "${summary}" || true
  else
    if request_has_active; then
      "${REQUEST_CHANNEL}" sync --agent "${agent}" || true
    fi
  fi
}

request_note_if_open() {
  local agent="${1:-}"
  local kind="${2:-progress}"
  local message="${3:-}"
  local next_action="${4:-}"
  request_has_active || return 0
  [[ -n "${message}" ]] || return 0
  if [[ -n "${next_action}" ]]; then
    "${REQUEST_CHANNEL}" note --agent "${agent}" --kind "${kind}" \
      --message "${message}" --next "${next_action}" || true
  else
    "${REQUEST_CHANNEL}" note --agent "${agent}" --kind "${kind}" \
      --message "${message}" || true
  fi
}

request_close_or_note() {
  local agent="${1:-}"
  local payload="${2:-{}}"
  request_has_active || return 0

  mapfile -t _parsed < <(python3 - "${payload}" <<'PY'
import json, sys
import re
payload = sys.argv[1]
try:
    data = json.loads(payload) if payload else {}
except Exception:
    data = {"note": payload}
    result_match = re.search(r'"result"\s*:\s*"([^"]+)"', payload)
    next_match = re.search(r'"next(?:_action)?"\s*:\s*"([^"]+)"', payload)
    if result_match:
        data["result"] = result_match.group(1)
    if next_match:
        data["next"] = next_match.group(1)

result = str(data.get("result", "")).strip()
next_ = str(data.get("next", "") or data.get("next_action", "")).strip()
verified = data.get("verified_here")
files_changed = data.get("files_changed", [])
parts = []
if verified not in (None, ""):
    parts.append(f"verified_here={verified}")
if files_changed:
    parts.append("files_changed=" + ",".join(str(x) for x in files_changed))
if not parts and data:
    parts.append(json.dumps(data, ensure_ascii=True, sort_keys=True))
message = "; ".join(parts)
print(result)
print(next_)
print(message)
PY
  )

  local result="${_parsed[0]:-}"
  local next_action="${_parsed[1]:-}"
  local message="${_parsed[2]:-}"

  if [[ -n "${result}" ]]; then
    if [[ -n "${next_action}" ]]; then
      "${REQUEST_CHANNEL}" close --agent "${agent}" --result "${result}" --next "${next_action}" || true
    else
      "${REQUEST_CHANNEL}" close --agent "${agent}" --result "${result}" || true
    fi
    return 0
  fi

  if [[ -n "${message}" ]]; then
    request_note_if_open "${agent}" "handoff" "session_end: ${message}" "${next_action}"
  fi
}

run_validation_preflight() {
  local agent="${1:-}"
  local allow_blocked="${2:-0}"
  local cmd=("${VALIDATION_PREFLIGHT}" --agent "${agent}")
  if [[ -n "${IFACE:-}" ]]; then
    cmd+=(--iface "${IFACE}")
  fi

  if "${cmd[@]}"; then
    return 0
  fi

  if [[ "${allow_blocked}" == "1" ]]; then
    echo "[coord] validation preflight is blocked, but continuing because --allow-blocked was set."
    echo "[coord] Do not upgrade any live claim without the missing artifacts."
    return 0
  fi

  echo "[coord] validation session blocked by preflight."
  echo "[coord] Re-run after prerequisites are present, or use --allow-blocked for standby/handoff only."
  return 2
}

cmd_roadmap_sync() {
  local agent="${1:-lead-coordinator}"
  [[ -n "${agent}" ]] || { echo "usage: agent-coord.sh roadmap_sync AGENT" >&2; exit 1; }
  "${SWARM_COORD}" roadmap-sync --agent "${agent}" --post-note
}

cmd_next_task() {
  local agent="${1:-}"
  shift || true
  local mode=""
  [[ -n "${agent}" ]] || { echo "usage: agent-coord.sh next_task AGENT [--mode verification|validation]" >&2; exit 1; }
  while [[ $# -gt 0 ]]; do
    case "${1}" in
      --mode)
        mode="${2:-}"
        [[ -n "${mode}" ]] || { echo "next_task: --mode requires a value" >&2; exit 1; }
        shift 2
        ;;
      *)
        echo "next_task: unknown argument '${1}'" >&2
        exit 1
        ;;
    esac
  done
  if [[ -n "${mode}" ]]; then
    "${SWARM_COORD}" roadmap-next --agent "${agent}" --mode "${mode}"
  else
    "${SWARM_COORD}" roadmap-next --agent "${agent}"
  fi
}

print_execution_buckets() {
  [[ -f "${ROADMAP_QUEUE}" ]] || return 0
  python3 - "${ROADMAP_QUEUE}" <<'PY'
import json, sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

buckets = data.get("execution_buckets", {})
tasks = {task["id"]: task for task in data.get("tasks", [])}

if not buckets:
    raise SystemExit(0)

print("")
print("Execution buckets:")
for bucket_name in ("verification-ready", "live-validation-only", "blocked-horizon-2"):
    bucket = buckets.get(bucket_name)
    if not bucket:
        continue
    task_ids = bucket.get("task_ids", [])
    print(f"  {bucket_name}: {len(task_ids)}")
    for task_id in task_ids[:3]:
        task = tasks.get(task_id, {})
        agent = task.get("agent", "?")
        status = task.get("status", "?")
        print(f"    - {task_id} [{agent}/{status}]")
PY
}

print_agent_bucket_summary() {
  local agent="${1:-}"
  local mode="${2:-}"
  [[ -n "${agent}" && -f "${ROADMAP_QUEUE}" ]] || return 0
  python3 - "${ROADMAP_QUEUE}" "${agent}" "${mode}" <<'PY'
import json, sys

queue_path, agent, mode = sys.argv[1:4]
with open(queue_path, encoding="utf-8") as fh:
    data = json.load(fh)

tasks = [task for task in data.get("tasks", []) if task.get("agent") == agent]
if mode:
    tasks = [task for task in tasks if task.get("mode") == mode]

if not tasks:
    raise SystemExit(0)

ready = [task for task in tasks if task.get("status") == "ready"]
current = ready[0] if ready else tasks[0]
bucket = current.get("bucket", "unclassified")
print(f"[coord] current bucket: {bucket}")
print(f"[coord] bucket task: {current.get('id')} — {current.get('summary')}")
PY
}

# ── status ────────────────────────────────────────────────────────────────────
cmd_status() {
  echo ""
  echo "========================================================="
  echo "  x0tta6bl4 — Agent Coordination State"
  echo "  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "========================================================="
  echo ""

  if [[ ! -f "${STATE}" ]]; then
    echo "  state.json not found — coordination not initialized" >&2
    return 1
  fi

  python3 - "${STATE}" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
agents = s.get("agents", {})
print("Agents:")
for name, info in agents.items():
    role = info.get("role", "?")
    status = info.get("status", "?")
    last = info.get("last_active") or "never"
    print(f"  {name:<10} [{status:<8}] last={last}")
    print(f"             role: {role}")
    vh = info.get("last_verified_here", [])
    if vh:
        for v in vh[-2:]:
            print(f"             + {v}")
print("")
print("VERIFIED HERE (global):")
print("  [compatibility summary only — mixed execution contexts may be reflected here]")
print("  [for current machine-local truth, prefer the latest verify_run log entry and scripts/verify-v1.1.sh --fast]")
for item in s.get("global_verified_here", {}).get("items", []):
    print(f"  + {item}")
print("")
print("NOT VERIFIED YET:")
for item in s.get("global_not_verified_yet", []):
    print(f"  - {item}")
PY

  print_execution_buckets

  if request_channel_available && "${REQUEST_CHANNEL}" show >/dev/null 2>&1; then
    echo ""
    echo "Active request thread:"
    "${REQUEST_CHANNEL}" show || true
  fi

  echo ""
  echo "Recent log:"
  tail -3 "${LOG}" 2>/dev/null | python3 -c '
import sys, json
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        e = json.loads(line)
        print(f"  [{e.get(\"ts\",\"?\")}] {e.get(\"agent\",\"?\")} → {e.get(\"event\",\"?\")} (verified={e.get(\"verified_here\",\"-\")})")
    except Exception:
        print("  " + line[:100])
' 2>/dev/null || true
  echo ""
}

# ── inbox ─────────────────────────────────────────────────────────────────────
cmd_inbox() {
  local agent="${1:-}"
  [[ -n "${agent}" ]] || { echo "usage: agent-coord.sh inbox AGENT" >&2; exit 1; }
  local inbox="${COORD_DIR}/inbox/${agent}.jsonl"
  if [[ ! -f "${inbox}" ]]; then
    echo "  inbox for ${agent}: empty"
    return 0
  fi
  echo ""
  echo "=== Inbox for ${agent} ==="
  python3 - "${inbox}" <<'PY'
import json, sys
lines = open(sys.argv[1]).readlines()
for line in lines:
    line = line.strip()
    if not line: continue
    try:
        m = json.loads(line)
        print(f"\n[{m.get('ts','?')}] from={m.get('from','?')} priority={m.get('priority','?')}")
        print(f"  Subject: {m.get('subject','?')}")
        body = m.get("body", "")
        for l in body.split(". ")[:4]:
            print(f"  {l.strip()}.")
        cmd = m.get("exact_next_command","")
        if cmd:
            print(f"  → NEXT: {cmd}")
        skip = m.get("files_do_not_touch",[])
        if skip:
            print(f"  → DO NOT TOUCH: {', '.join(skip)}")
    except Exception as ex:
        print(f"  (parse error: {ex})")
PY
  echo ""
}

# ── log ───────────────────────────────────────────────────────────────────────
cmd_log() {
  local agent="${1:-unknown}"; local event="${2:-event}"; shift 2 || true
  local extra="${*:-{}}"
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local note_payload
  note_payload="$(python3 - "${extra}" <<'PY'
import json, sys
raw = sys.argv[1]
if raw.startswith("{"):
    candidate = raw
    while candidate:
        try:
            print(json.dumps(json.loads(candidate), ensure_ascii=True, sort_keys=True))
            raise SystemExit(0)
        except Exception:
            if candidate.endswith("}"):
                candidate = candidate[:-1]
                continue
            break
print(raw)
PY
)"
  python3 - "${LOG}" "${agent}" "${event}" "${ts}" "${extra}" <<'PY'
import json, sys
log_path, agent, event, ts, extra = sys.argv[1:6]
extra_data = None
if extra.startswith("{"):
    candidate = extra
    while candidate:
        try:
            extra_data = json.loads(candidate)
            break
        except Exception:
            if candidate.endswith("}"):
                candidate = candidate[:-1]
                continue
            break
if extra_data is None:
    extra_data = {"note": extra}
entry = {"ts": ts, "agent": agent, "event": event, **extra_data}
with open(log_path, "a") as f:
    f.write(json.dumps(entry) + "\n")
print(f"[coord] logged: {agent} → {event} at {ts}")
PY

  case "${event}" in
    session_start|session_end)
      ;;
    *)
      request_note_if_open "${agent}" "progress" "${event}: ${note_payload}" ""
      ;;
  esac
}

# ── send ──────────────────────────────────────────────────────────────────────
cmd_send() {
  local from="${1:-}"; local to="${2:-}"; local subject="${3:-}"; local body="${4:-}"
  [[ -n "${from}" && -n "${to}" && -n "${subject}" ]] || {
    echo "usage: agent-coord.sh send FROM TO SUBJECT BODY" >&2; exit 1
  }
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  local inbox="${COORD_DIR}/inbox/${to}.jsonl"
  python3 - "${inbox}" "${from}" "${to}" "${subject}" "${body}" "${ts}" <<'PY'
import json, sys
inbox_path, from_, to_, subject, body, ts = sys.argv[1:7]
entry = {"ts": ts, "from": from_, "to": to_, "subject": subject, "body": body, "priority": "normal"}
with open(inbox_path, "a") as f:
    f.write(json.dumps(entry) + "\n")
print(f"[coord] message sent: {from_} → {to_}: {subject}")
PY

  request_note_if_open "${from}" "handoff" "to=${to} subject=${subject} body=${body}" ""
}

# ── session_start helper ──────────────────────────────────────────────────────
cmd_session_start() {
  local agent="${1:-}"
  shift || true
  local summary=""
  local mode=""
  local allow_blocked="0"
  [[ -n "${agent}" ]] || { echo "usage: agent-coord.sh session_start AGENT [--mode verification|validation] [SUMMARY]" >&2; exit 1; }
  while [[ $# -gt 0 ]]; do
    case "${1}" in
      --mode)
        mode="${2:-}"
        [[ -n "${mode}" ]] || { echo "session_start: --mode requires a value" >&2; exit 1; }
        shift 2
        ;;
      --allow-blocked)
        allow_blocked="1"
        shift
        ;;
      *)
        if [[ -n "${summary}" ]]; then
          summary="${summary} ${1}"
        else
          summary="${1}"
        fi
        shift
        ;;
    esac
  done
  echo ""
  echo "=== Agent session start: ${agent} ==="
  cmd_status
  cmd_inbox "${agent}"
  if [[ "${mode}" == "validation" ]]; then
    run_validation_preflight "${agent}" "${allow_blocked}"
  fi
  request_sync "${agent}" "${summary}"
  if [[ -n "${mode}" ]]; then
    echo "[coord] requested execution mode: ${mode}"
    if [[ "${allow_blocked}" == "1" ]]; then
      cmd_log "${agent}" "session_start" "{\"mode\":\"${mode}\",\"allow_blocked\":true}"
    else
      cmd_log "${agent}" "session_start" "{\"mode\":\"${mode}\"}"
    fi
    cmd_next_task "${agent}" --mode "${mode}" || true
    print_agent_bucket_summary "${agent}" "${mode}"
  else
    cmd_log "${agent}" "session_start" "{}"
    cmd_next_task "${agent}" || true
    print_agent_bucket_summary "${agent}" ""
  fi
  echo "[coord] Done. Check inbox above for messages from other agents."
  echo ""
}

# ── session_end helper ────────────────────────────────────────────────────────
cmd_session_end() {
  local agent="${1:-}"; shift || true
  [[ -n "${agent}" ]] || { echo "usage: agent-coord.sh session_end AGENT [JSON-PAYLOAD]" >&2; exit 1; }
  local payload="${1:-{}}"
  cmd_log "${agent}" "session_end" "${payload}"
  request_close_or_note "${agent}" "${payload}"
  echo "[coord] Session end logged for ${agent}."
  echo "[coord] Drop messages to other agents:"
  for peer in gemini codex claude; do
    [[ "${peer}" == "${agent}" ]] && continue
    echo "  scripts/agent-coord.sh send ${agent} ${peer} 'subject' 'body'"
  done
  echo ""
}

# ── dispatch ──────────────────────────────────────────────────────────────────
COMMAND="${1:-status}"
shift || true

case "${COMMAND}" in
  status)        cmd_status ;;
  inbox)         cmd_inbox "$@" ;;
  log)           cmd_log "$@" ;;
  send)          cmd_send "$@" ;;
  roadmap_sync)  cmd_roadmap_sync "$@" ;;
  next_task)     cmd_next_task "$@" ;;
  session_start) cmd_session_start "$@" ;;
  session_end)   cmd_session_end "$@" ;;
  *)
    echo "unknown command: ${COMMAND}" >&2
    echo "commands: status | inbox AGENT | log AGENT EVENT [JSON] | send FROM TO SUBJECT BODY | roadmap_sync AGENT | next_task AGENT [--mode verification|validation] | session_start AGENT [--mode verification|validation] [--allow-blocked] [SUMMARY] | session_end AGENT [JSON]" >&2
    exit 1
    ;;
esac
