#!/usr/bin/env bash
#
# lane_pickup.sh — one-shot session opener for any lane agent.
#
# Usage:
#   bash scripts/agents/lane_pickup.sh <agent> [--mode verification|validation]
#
# What it does:
#   1. Opens a session via agent-coord.sh (front-door, auto-injects integrity context)
#   2. Runs a lane-scoped memory_recall against this agent's domain keywords
#   3. Prints inbox digest (count + 3 most recent subjects)
#   4. Prints next ready task from roadmap queue
#   5. Prints the source-of-truth files this lane should read first
#
# Closing: agent must call agent-coord.sh session_end_submit with verification[].
# This script does NOT close the session — it only opens it cleanly.

set -euo pipefail

AGENT="${1:-}"
[[ -n "$AGENT" ]] || { echo "usage: $0 <agent> [--mode verification|validation]" >&2; exit 1; }
shift || true

MODE_FLAG=()
if [[ "${1:-}" == "--mode" && -n "${2:-}" ]]; then
  MODE_FLAG=(--mode "$2")
  shift 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COORD="$ROOT_DIR/scripts/agent-coord.sh"

# Lane-domain keywords used for memory_recall narrowing.
declare -A DOMAIN
DOMAIN[bot-product-flow]="retired alias; use codex for bot onboarding subscription delivery telegram aiogram menu /start /sub deep-link"
DOMAIN[vpn-runtime-ops]="retired alias; use codex for x-ui xray runtime client device transport reality fallback orphan UUID"
DOMAIN[payment-ops]="retired alias; use codex for payment yoomoney yookassa cardlink webhook pending approved completed idempotency"
DOMAIN[client-compat-qa]="retired alias; use codex for client compat hiddify happ v2raytun import iphone android matrix"
DOMAIN[vpn-observability]="retired alias; use codex for monitor canary subscription health policy probe latest.json prometheus"
DOMAIN[lead-coordinator]="retired alias; use codex for roadmap freeze release verification snapshot digest"
DOMAIN[gemini]="ebpf xdp af_xdp live attach datapath bpf_loader prog_id benchmark verify-local"
DOMAIN[codex]="ghost access vpn vps bot x-ui xray payment client import monitoring open5gs 5g signaling integration test bridge upf amf"
DOMAIN[claude]="retired alias; use codex for evidence verification compliance soc2 sbom cosign rekor pqc"

# Lane-specific source-of-truth file pointers.
declare -A SOT
SOT[bot-product-flow]="retired alias; use codex. telegram_bot_simple.py + onboarding_logic.py + onboarding_delivery.py + docs/ghost-access/SELF_TEST_CHECKLIST.md"
SOT[vpn-runtime-ops]="retired alias; use codex. telegram_bot_simple.py + database.py + scripts/xui_client_manager.py + scripts/xray_runtime_user_manager.py + .claude/rules/50-prod-source-of-truth.md"
SOT[payment-ops]="retired alias; use codex. telegram_bot_simple.py + database.py + docs/ghost-access/EXECUTION_PLAN.md"
SOT[client-compat-qa]="retired alias; use codex. docs/ghost-access/SELF_TEST_CHECKLIST.md + onboarding_delivery.py DELIVERY_MATRIX"
SOT[vpn-observability]="retired alias; use codex. scripts/run_vpn_service_access_agent.py + /var/lib/ghost-access/vpn-service-access-agent/latest.json + deploy/systemd/ghost-access-vpn-monitor.service"
SOT[lead-coordinator]="retired alias; use codex. plans/ROADMAP_AGENT_QUEUE.json + STATUS_REALITY.md + AGENTS.md"
SOT[gemini]="docs/team/GEMINI_RUNBOOK.md + ebpf/prod/ + STATUS_REALITY.md (read-only — DO NOT EDIT)"
SOT[codex]="AGENTS.md + .claude/rules/50-prod-source-of-truth.md + telegram_bot_simple.py + database.py + scripts/xui_client_manager.py + scripts/xray_runtime_user_manager.py + edge/5g/ + integration/ + test/"
SOT[claude]="retired alias; use codex. scripts/verify-v1.1.sh + docs/verification/ + AGENTS.md"

domain="${DOMAIN[$AGENT]:-$AGENT}"
sot="${SOT[$AGENT]:-AGENTS.md}"

echo "================================================================"
echo "  lane_pickup → $AGENT"
echo "================================================================"
echo
echo "[1/5] Opening session…"
bash "$COORD" session_start "$AGENT" "${MODE_FLAG[@]}" "lane_pickup automated" 2>&1 | tail -5
echo
echo "[2/5] Memory recall on lane domain ($domain)…"
bash "$COORD" memory_recall --query "$domain" --limit 5 --all-agents 2>&1 | tail -15
echo
echo "[3/5] Inbox digest…"
inbox_lines=$(bash "$COORD" inbox "$AGENT" 2>&1 | grep -E "^\[2026" || true)
inbox_count=$(printf '%s\n' "$inbox_lines" | grep -c "^\[" || true)
echo "  total messages: $inbox_count"
echo "  last 3 subjects:"
printf '%s\n' "$inbox_lines" | tail -3 | sed 's/^/    /'
echo
echo "[4/5] Next ready task from roadmap…"
bash "$COORD" next_task "$AGENT" "${MODE_FLAG[@]}" 2>&1 | head -15
echo
echo "[5/5] Source of truth for this lane:"
echo "  $sot"
echo
echo "When done, close with:"
echo "  bash scripts/agent-coord.sh session_end_submit $AGENT \\"
echo "       --source-of-truth \"$sot\" \\"
echo "       --memory-tool 'memory_recall' \\"
echo "       --verification-entry 'cmd::exit_code::VERIFIED HERE' \\"
echo "       --result 'short summary'"
echo "================================================================"
