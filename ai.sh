#!/usr/bin/env bash
# ai.sh — One-touch AI agent orchestration for x0tta6bl4
# Usage: ./ai.sh <command> [args]
#
# Each command loads the appropriate role file and runs the agent
# with the correct context files.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ROLES_DIR="$PROJECT_ROOT/ai/roles"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "x0tta6bl4 AI Agent Orchestrator"
    echo ""
    echo "Usage: ./ai.sh <command>"
    echo ""
    echo "Commands:"
    echo "  plan        Run Architect agent — update roadmap, plan sprint"
    echo "  code        Run Dev agent — implement current tasks"
    echo "  ops-test    Run Ops agent — run tests and benchmarks"
    echo "  gtm         Run GTM agent — grant prep, marketing content"
    echo "  cycle       Run parallel 4-agent skill-aware cycle"
    echo "  status      Show current sprint status from ACTION_PLAN_NOW.md"
    echo "  walkthrough Show recent decisions from docs/walkthrough.md"
    echo ""
    echo "Examples:"
    echo "  ./ai.sh plan              # Plan next sprint"
    echo "  ./ai.sh code              # Implement top task"
    echo "  ./ai.sh ops-test          # Run full test suite"
    echo "  ./ai.sh gtm               # Update grant materials"
    echo "  ./ai.sh cycle             # Run fast parallel agent cycle"
    echo "  ./ai.sh status            # Print current sprint"
}

# Print current sprint status
cmd_status() {
    echo -e "${BLUE}=== Current Sprint ===${NC}"
    echo ""
    if [ -f "$PROJECT_ROOT/ACTION_PLAN_NOW.md" ]; then
        # Show sprint header and incomplete tasks
        head -5 "$PROJECT_ROOT/ACTION_PLAN_NOW.md"
        echo ""
        echo -e "${YELLOW}--- Pending tasks ---${NC}"
        grep -n '^\- \[ \]' "$PROJECT_ROOT/ACTION_PLAN_NOW.md" || echo "  (none)"
        echo ""
        echo -e "${GREEN}--- Done ---${NC}"
        grep -c '^\- \[x\]' "$PROJECT_ROOT/ACTION_PLAN_NOW.md" | xargs -I{} echo "  {} tasks completed"
    else
        echo "  ACTION_PLAN_NOW.md not found"
    fi
}

# Print recent walkthrough decisions
cmd_walkthrough() {
    echo -e "${BLUE}=== Recent Decisions ===${NC}"
    echo ""
    if [ -f "$PROJECT_ROOT/docs/walkthrough.md" ]; then
        # Show last batch entry (most recent ## heading and its content)
        awk '/^## [0-9]/{found=1; block=$0; next} found && /^## [0-9]/{print block; exit} found{block=block"\n"$0} END{if(found) print block}' \
            "$PROJECT_ROOT/docs/walkthrough.md"
    else
        echo "  docs/walkthrough.md not found"
    fi
}

# Run agent with role context
run_agent() {
    local role="$1"
    local role_file="$ROLES_DIR/$role.md"

    if [ ! -f "$role_file" ]; then
        echo -e "${RED}Error: Role file not found: $role_file${NC}"
        exit 1
    fi

    echo -e "${BLUE}=== Loading $role agent ===${NC}"
    echo -e "Role: ${GREEN}$role_file${NC}"
    echo -e "Sprint: ${GREEN}ACTION_PLAN_NOW.md${NC}"
    echo -e "Log: ${GREEN}docs/walkthrough.md${NC}"
    echo ""

    # Build context: role + sprint + walkthrough
    local context=""
    context+="--- ROLE ---"$'\n'
    context+="$(cat "$role_file")"$'\n\n'
    context+="--- CURRENT SPRINT ---"$'\n'
    context+="$(cat "$PROJECT_ROOT/ACTION_PLAN_NOW.md")"$'\n\n'

    if [ -f "$PROJECT_ROOT/docs/walkthrough.md" ]; then
        context+="--- DECISION LOG ---"$'\n'
        context+="$(cat "$PROJECT_ROOT/docs/walkthrough.md")"$'\n'
    fi

    echo "$context"
    echo ""
    echo -e "${YELLOW}Context loaded. Paste the above into your AI agent, or pipe it:${NC}"
    echo -e "  ./ai.sh $role | pbcopy     # macOS"
    echo -e "  ./ai.sh $role | xclip      # Linux"
}

cmd_cycle() {
    python3 "$PROJECT_ROOT/scripts/agents/run_agent_cycle.py" "$@"
}

# Main dispatch
cmd="${1:-}"
if [ "$#" -gt 0 ]; then
    shift
fi

case "$cmd" in
    plan)       run_agent "architect" ;;
    code)       run_agent "dev" ;;
    ops-test)   run_agent "ops" ;;
    gtm)        run_agent "gtm" ;;
    cycle)      cmd_cycle "$@" ;;
    status)     cmd_status ;;
    walkthrough) cmd_walkthrough ;;
    -h|--help|help) usage ;;
    "")         usage ;;
    *)
        echo -e "${RED}Unknown command: $cmd${NC}"
        echo ""
        usage
        exit 1
        ;;
esac
