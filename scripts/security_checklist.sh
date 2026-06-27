#!/usr/bin/env bash
set -euo pipefail

YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🔍 Security Checklist${NC}"
echo "===================="

# Check 1: Secrets in repo
echo -n "❓ No secrets in repository... "
if find . \( -name "*.pem" -o -name "*.key" -o -name "*.p12" -o -name "*.der" \) | grep -v ".example" | grep -q .; then
  echo -e "${RED}❌ FAIL${NC}"
  echo "   Found secrets (showing first 10):"
  find . \( -name "*.pem" -o -name "*.key" -o -name "*.p12" -o -name "*.der" \) | grep -v ".example" | head -10
else
  echo -e "${GREEN}✅ PASS${NC}"
fi

# Check 2: .env committed
echo -n "❓ No committed .env files... "
if git ls-files | grep -E '\\.env$' | grep -q .; then
  echo -e "${RED}❌ FAIL${NC}"
  git ls-files | grep -E '\\.env$' || true
else
  echo -e "${GREEN}✅ PASS${NC}"
fi

# Check 3: Pre-commit hooks
echo -n "❓ Pre-commit hooks installed... "
if [[ -f .git/hooks/pre-commit ]]; then
  echo -e "${GREEN}✅ PASS${NC}"
else
  echo -e "${YELLOW}⚠️  WARNING${NC}"
  echo "   Run: pre-commit install"
fi

# Check 4: Dockerfile non-root
echo -n "❓ Dockerfile uses non-root user... "
if grep -E "^USER\\s+[^r]*$" Dockerfile >/dev/null 2>&1; then
  echo -e "${GREEN}✅ PASS${NC}"
else
  echo -e "${YELLOW}⚠️  WARNING${NC}"
  echo "   Add USER directive to Dockerfile"
fi

# Check 5: SPIRE secrets externalized (values.yaml)
VALUES_PATH="infra/security/spiffe-spire/helm-charts/spire-optimization/values.yaml"
echo -n "❓ SPIRE secrets externalized... "
if grep -E "caArnFromSecret|credentials:\\s+secretName" "$VALUES_PATH" >/dev/null 2>&1; then
  echo -e "${GREEN}✅ PASS${NC}"
else
  echo -e "${YELLOW}⚠️  WARNING${NC}"
  echo "   Use External Secrets Operator for AWS PCA ARN"
fi

# Check 6: Batman-adv isolation
BVALUES_PATH="infra/networking/batman-adv/helm-charts/batman-adv-optimization/values-production.yaml"
echo -n "❓ Batman-adv has node isolation... "
if [[ -f "$BVALUES_PATH" ]] && grep -q "nodeSelector:" "$BVALUES_PATH"; then
  echo -e "${GREEN}✅ PASS${NC}"
else
  echo -e "${YELLOW}⚠️  WARNING${NC}"
  echo "   Add nodeSelector and taints in values-production.yaml"
fi

# Check 7: PQC adapter feature flags
echo -n "❓ PQC adapter feature flags... "
if grep -q "PQC_MODE" x0tta6bl4_paradox_zone/src/pqc_adapter.py >/dev/null 2>&1; then
  echo -e "${GREEN}✅ PASS${NC}"
else
  echo -e "${YELLOW}⚠️  WARNING${NC}"
  echo "   Add PQC_MODE environment variable gating"
fi

# Check 8: Coverage report presence
echo -n "❓ Coverage report present... "
if [[ -f coverage.xml ]]; then
  echo -e "${GREEN}✅ PASS${NC}"
else
  echo -e "${YELLOW}⚠️  WARNING${NC}"
  echo "   Run pytest --cov to generate coverage.xml"
fi

echo -e "\n${GREEN}Checklist complete.${NC}"
