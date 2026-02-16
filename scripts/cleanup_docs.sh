#!/bin/bash

# Create directories if they don't exist
mkdir -p docs/01-architecture
mkdir -p docs/04-deployment
mkdir -p docs/05-operations
mkdir -p docs/archive/phase1_artifacts

# Move Architecture docs
mv docs/ARCHITECTURE_DIAGRAMS.md docs/01-architecture/ 2>/dev/null
mv docs/ARCHITECTURE_DIAGRAM_DECODED.md docs/01-architecture/ 2>/dev/null
mv docs/DIAGRAM_DECODED.md docs/01-architecture/ 2>/dev/null

# Move Deployment docs
mv docs/DEPLOYMENT_GUIDE.md docs/04-deployment/ 2>/dev/null
mv docs/DATABASE_SETUP.md docs/04-deployment/ 2>/dev/null
mv docs/LEDGER_ML_DEPS_*.md docs/04-deployment/ 2>/dev/null
mv docs/РУКОВОДСТВО_ПО_ДЕПЛОЮ.md docs/04-deployment/DEPLOYMENT_GUIDE_RU.md 2>/dev/null

# Move Operations docs
mv docs/TROUBLESHOOTING_GUIDE.md docs/05-operations/ 2>/dev/null
mv docs/EMERGENCY_PROCEDURES.md docs/05-operations/ 2>/dev/null
mv docs/ALERTING_INTEGRATION.md docs/05-operations/ 2>/dev/null
mv docs/PROMETHEUS_METRICS.md docs/05-operations/ 2>/dev/null
mv docs/EBPF_PERFORMANCE_MONITORING_GUIDE.md docs/05-operations/ 2>/dev/null

# Archive Phase 1 / Status Artifacts
mv docs/BENCHMARK_OUTPUT.txt docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/BUILD_*.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/CLAIMS_AUDIT.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/COVERAGE_REPORT.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/DOCUMENTATION_COMPLETE.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/P1_*.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/PHASE_*.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/VERIFICATION_REPORT_FINAL.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/FSI_CHECKLIST.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/GRANT_TECHNICAL_EVIDENCE.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/PITCH_DECK_FINAL_SUMMARY.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/TEST_COVERAGE_PLAN.md docs/archive/phase1_artifacts/ 2>/dev/null
mv docs/PERFORMANCE_VALIDATION_PLAN.md docs/archive/phase1_artifacts/ 2>/dev/null

echo "Docs cleanup complete."
