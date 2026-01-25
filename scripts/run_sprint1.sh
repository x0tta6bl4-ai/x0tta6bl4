#!/bin/bash

# Sprint 1: Week 1 Validation - Complete Execution
# Runs all Week 1 validation tasks

set -euo pipefail

PROJECT_ROOT="/mnt/AC74CC2974CBF3DC"
cd "$PROJECT_ROOT"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     🚀 SPRINT 1: WEEK 1 VALIDATION - EXECUTING              ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Track results
TOTAL_TASKS=0
PASSED_TASKS=0
FAILED_TASKS=0

# Function to run task
run_task() {
    local task_name="$1"
    local task_command="$2"
    
    TOTAL_TASKS=$((TOTAL_TASKS + 1))
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "TASK: $task_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if eval "$task_command"; then
        echo "✅ $task_name: PASSED"
        PASSED_TASKS=$((PASSED_TASKS + 1))
        echo ""
        return 0
    else
        echo "❌ $task_name: FAILED"
        FAILED_TASKS=$((FAILED_TASKS + 1))
        echo ""
        return 1
    fi
}

# Task 1: Security Audit
run_task "Security Audit" "python3 scripts/security_audit_checklist.py"

# Task 2: Performance Baseline (requires server)
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    run_task "Performance Baseline" "python3 scripts/performance_baseline.py"
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "TASK: Performance Baseline"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  Server not running. Skipping performance baseline."
    echo "   To run later: python3 scripts/performance_baseline.py"
    echo ""
    TOTAL_TASKS=$((TOTAL_TASKS + 1))
fi

# Task 3: Team Training Checklist
run_task "Team Training Checklist" "python3 scripts/team_training_checklist.py"

# Task 4: Documentation Check
run_task "Documentation Check" "
    test -f docs/team/ON_CALL_RUNBOOK.md && \
    test -f docs/team/INCIDENT_RESPONSE_PLAN.md && \
    test -f docs/team/READINESS_CHECKLIST.md && \
    echo '✅ All team documentation exists'
"

# Task 5: Staging Scripts Check
run_task "Staging Scripts Check" "
    test -f scripts/staging_deployment.py && \
    test -f scripts/run_load_test.py && \
    test -f scripts/run_staging_validation.sh && \
    echo '✅ All staging scripts exist'
"

# Summary
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║     📊 SPRINT 1 SUMMARY                                      ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Total Tasks: $TOTAL_TASKS"
echo "Passed: $PASSED_TASKS"
echo "Failed: $FAILED_TASKS"
echo "Skipped: $((TOTAL_TASKS - PASSED_TASKS - FAILED_TASKS))"
echo ""

if [ $FAILED_TASKS -eq 0 ]; then
    echo "✅ SPRINT 1: ALL TASKS PASSED"
    echo ""
    echo "Next steps:"
    echo "  1. Deploy to staging: python3 scripts/staging_deployment.py"
    echo "  2. Run load test: python3 scripts/run_load_test.py"
    echo "  3. Run chaos tests: python3 tests/chaos/staging_chaos_test.py"
    echo "  4. Conduct team training (Jan 3)"
    exit 0
else
    echo "❌ SPRINT 1: SOME TASKS FAILED"
    echo ""
    echo "Please fix failed tasks before proceeding."
    exit 1
fi

