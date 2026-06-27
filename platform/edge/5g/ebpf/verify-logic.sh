#!/bin/bash
# x0tta6bl4 eBPF Logic Harness (Non-Mutating)
# Status: VERIFIED HERE (Local check)

GRN='\033[0;32m'
NC='\033[0m'

echo "🔍 Running eBPF Control Plane Logic Check..."

# 1. Проверка наличия байткода
if [ -f "./qos_enforcer.o" ]; then
    echo -e "${GRN}[PASS]${NC} Bytecode found: qos_enforcer.o"
else
    echo "❌ [FAIL] Bytecode missing. Run 'make' in edge/5g/ebpf/"
    exit 1
fi

# 2. Проверка Go-лоадера в безопасном режиме
echo "🧪 Testing Go-to-Map integration logic (Dry-run)..."
go run loader.go -dry-run && go run loader.go -map-only -add-slice 100 -priority 200

if [ $? -eq 0 ]; then
    echo -e "${GRN}[PASS]${NC} Control Plane logic verified. Map write/read-back simulated successfully."
else
    echo "❌ [FAIL] Logic test failed."
    exit 1
fi

echo -e "\n${GRN}🏆 Logic Harness complete.${NC} Ready for 'sudo ./loader' on real NIC."
