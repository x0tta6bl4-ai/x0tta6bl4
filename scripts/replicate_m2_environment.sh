#!/usr/bin/env bash
# ==============================================================================
# Milestone M2 Operational Validation Replication Script
# Allows external engineers/auditors to replicate M2 evidence on any Linux host.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

echo "=========================================================================="
echo "🚀 REPLICATING MILESTONE M2 OPERATIONAL VALIDATION"
echo "=========================================================================="

cd "${PROJECT_ROOT}"

# Check Python environment
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required to run M2 validation."
    exit 1
fi

# Run Failure Scenarios
echo "--> Executing Scenario F-001 (Packet Loss 80%)..."
python3 scripts/run_m2_operational_validation.py --failure F-001

echo "--> Executing Scenario F-002 (High Latency 300ms)..."
python3 scripts/run_m2_operational_validation.py --failure F-002

echo "--> Executing Scenario F-003 (Node Crash)..."
python3 scripts/run_m2_operational_validation.py --failure F-003

echo "--> Executing Scenario F-005 (Invalid SVID Injection)..."
python3 scripts/run_m2_operational_validation.py --failure F-005

echo "=========================================================================="
echo "🎉 REPLICATION COMPLETE"
echo "Machine-Readable Evidence Written To: results/milestone_m2_report.json"
echo "=========================================================================="
