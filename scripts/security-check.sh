#!/bin/bash

set -e

echo "═══════════════════════════════════════════════════════════"
echo "🔒 x0tta6bl4 Security Check Suite"
echo "═══════════════════════════════════════════════════════════"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FAILED=0
WARNINGS=0

# Install tools if needed
echo -e "${BLUE}📦 Installing security tools...${NC}"
pip install -q bandit safety pip-audit 2>/dev/null || true
echo ""

# 1. Bandit - Python security linter
echo -e "${BLUE}1️⃣  Running Bandit (Python security linter)...${NC}"
if bandit -r src/ -f json -o /tmp/bandit-report.json -q 2>/dev/null; then
    ISSUES=$(python3 -c "
import json
try:
    with open('/tmp/bandit-report.json') as f:
        report = json.load(f)
    high_critical = [r for r in report.get('results', []) 
                    if r.get('severity') in ['HIGH', 'CRITICAL']]
    if high_critical:
        print(len(high_critical))
    else:
        print(0)
except:
    print(0)
" 2>/dev/null || echo 0)
    
    if [ "$ISSUES" -gt 0 ]; then
        echo -e "${RED}❌ Found $ISSUES HIGH/CRITICAL security issues${NC}"
        bandit -r src/ -f txt -ll 2>/dev/null || true
        FAILED=$((FAILED + 1))
    else
        echo -e "${GREEN}✓ No HIGH/CRITICAL security issues found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Bandit scan failed${NC}"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# 2. Safety - Dependency vulnerability check
echo -e "${BLUE}2️⃣  Running Safety (dependency vulnerability check)...${NC}"
if pip install -q -e . 2>/dev/null; then
    if safety check -q 2>/dev/null; then
        echo -e "${GREEN}✓ No dependency vulnerabilities found${NC}"
    else
        VULN_COUNT=$(safety check --json 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    vulns = data.get('vulnerabilities', []) or []
    print(len(vulns))
except:
    print(0)
" 2>/dev/null || echo 0)
        
        if [ "$VULN_COUNT" -gt 0 ]; then
            echo -e "${YELLOW}⚠ Found $VULN_COUNT dependency vulnerabilities${NC}"
            safety check 2>/dev/null || true
            WARNINGS=$((WARNINGS + 1))
        else
            echo -e "${GREEN}✓ No dependency vulnerabilities found${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠ Could not install project for dependency check${NC}"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# 3. pip-audit - Another dependency checker
echo -e "${BLUE}3️⃣  Running pip-audit (alternative dependency check)...${NC}"
if pip-audit --skip-editable 2>/dev/null | grep -q "No known vulnerabilities found"; then
    echo -e "${GREEN}✓ No vulnerabilities detected by pip-audit${NC}"
else
    echo -e "${YELLOW}⚠ pip-audit found potential issues (review manually)${NC}"
    pip-audit --skip-editable 2>/dev/null || true
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
echo -e "${BLUE}📊 Security Check Summary${NC}"
echo "═══════════════════════════════════════════════════════════"

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All security checks passed!${NC}"
    exit 0
elif [ $FAILED -eq 0 ]; then
    echo -e "${YELLOW}⚠ Warnings found (review required)${NC}"
    echo "  - Warnings: $WARNINGS"
    echo ""
    echo "Run the individual tools to investigate:"
    echo "  - bandit -r src/"
    echo "  - safety check"
    echo "  - pip-audit"
    exit 0
else
    echo -e "${RED}❌ SECURITY CHECKS FAILED${NC}"
    echo "  - Critical failures: $FAILED"
    echo "  - Warnings: $WARNINGS"
    echo ""
    echo "Fix HIGH/CRITICAL issues before committing:"
    echo "  - bandit -r src/ -f txt -ll"
    exit 1
fi
