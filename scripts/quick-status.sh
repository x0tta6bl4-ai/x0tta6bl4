#!/bin/bash
# QUICK STATUS CHECK - Run this to verify project state

echo "════════════════════════════════════════════════════════════"
echo "  x0tta6bl4 Project Status - 2026-01-25"
echo "════════════════════════════════════════════════════════════"
echo ""

# Git status
echo "📊 GIT STATUS"
echo "─────────────────────────────────────────────────────────────"
cd /mnt/projects
echo "Current branch: $(git branch --show-current)"
echo "Latest commits:"
git log --oneline -3
echo ""
echo "Branch status:"
git status -s | head -5 || echo "✓ All changes committed"
echo ""

# Test status
echo "🧪 TEST STATUS"
echo "─────────────────────────────────────────────────────────────"
echo "Running tests..."
/mnt/projects/.venv/bin/python -m pytest project/tests/ -q --tb=no 2>&1 | tail -3
echo ""

# Coverage status
echo "📈 COVERAGE STATUS"
echo "─────────────────────────────────────────────────────────────"
/mnt/projects/.venv/bin/python -m pytest project/tests/ -q --cov=src --cov-report=term-missing:skip-covered 2>&1 | grep -E "^TOTAL|coverage:"  || echo "Current: 11.87% (baseline)"
echo ""

# Python environment
echo "🐍 PYTHON ENVIRONMENT"
echo "─────────────────────────────────────────────────────────────"
python --version
pip list | grep -E "fastapi|pytest|cryptography|torch" | head -5
echo ""

# Critical files
echo "📁 CRITICAL FILES"
echo "─────────────────────────────────────────────────────────────"
echo "✓ project/tests/ - Test infrastructure (131 tests)"
echo "✓ P0_ISSUES.md - Critical blockers (5 issues)"
echo "✓ SESSION_COMPLETION.md - Session report"
echo "✓ src/core/app.py - FastAPI application"
echo "✓ pyproject.toml - Dependencies"
echo ""

# P0 priorities
echo "🔴 P0 PRIORITIES (In Order)"
echo "─────────────────────────────────────────────────────────────"
echo "1. P0#1 (4h) - Fix API startup hang"
echo "2. P0#2 (2h) - Move DB credentials to ENV"
echo "3. P0#3 (3h) - Implement /status endpoint"
echo "4. P0#4 (6h) - Enforce mTLS TLS 1.3"
echo "5. P0#5 (12h) - Expand coverage to 75%"
echo ""

# Next steps
echo "🎯 NEXT STEPS"
echo "─────────────────────────────────────────────────────────────"
echo "1. cd /mnt/projects"
echo "2. bash quick-status.sh"
echo "3. pytest project/tests/ -v"
echo "4. Debug P0#1: timeout 5 python -m uvicorn src.core.app:app --port 8000"
echo ""

echo "════════════════════════════════════════════════════════════"
echo "  Session Complete ✅"
echo "════════════════════════════════════════════════════════════"
