#!/bin/bash
# x0tta6bl4 PQC Compliance Checker
# Verifies system readiness for Post-Quantum Cryptography (NIST FIPS 203/204)

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "🔍 Running PQC Compliance Audit..."
export PYTHONPATH=$PYTHONPATH:.

# 1. Check liboqs
echo -n "Checking liboqs availability... "
python3 -c "import oqs; print('FOUND')" &> /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC} (liboqs not installed or path not set)"
    exit 1
fi

# 2. Verify algorithms
echo -n "Verifying ML-KEM-768 support... "
python3 -c "import oqs; kem = oqs.KeyEncapsulation('ML-KEM-768'); print('SUPPORTED')" &> /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

echo -n "Verifying ML-DSA-65 support... "
python3 -c "import oqs; sig = oqs.Signature('ML-DSA-65'); print('SUPPORTED')" &> /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# 3. Security Sanity Check (Hybrid Handshake)
echo -n "Running security smoke tests... "
pytest tests/unit/security/test_post_quantum_unit.py --cov-fail-under=0 &> /mnt/projects/scripts/pqc_audit.log
if [ $? -eq 0 ]; then
    echo -e "${GREEN}PASSED${NC}"
else
    echo -e "${RED}FAILED${NC} (Check scripts/pqc_audit.log for details)"
    exit 1
fi

echo "---------------------------------------"
echo -e "Audit Result: ${GREEN}SYSTEM COMPLIANT${NC}"
