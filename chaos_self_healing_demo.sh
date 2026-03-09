#!/bin/bash
# =============================================================================
# x0tta6bl4 MaaS — Chaos & Self-Healing Live Demo
# =============================================================================
# This script simulates node failures in a Kubernetes mesh cluster
# to demonstrate real-time self-healing and MTTR tracking in Grafana.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1m\033[33m'
NC='\033[0m'

NAMESPACE=${1:-"default"}
TENANT_ID=${2:-"enterprise-demo"}

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}   x0tta6bl4 CHAOS DEMO: SELF-HEALING VALIDATION           ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "Target Namespace: ${YELLOW}$NAMESPACE${NC}"
echo -e "Target Tenant:    ${YELLOW}$TENANT_ID${NC}"

# 1. Check current mesh health
echo -e "\n${BLUE}[1/3] Проверка исходного состояния сети...${NC}"
READY_PODS=$(kubectl get pods -n $NAMESPACE -l "maas.x0tta6bl4.net/tenant=$TENANT_ID" -o jsonpath='{.items[*].status.containerStatuses[0].ready}' | grep -o "true" | wc -l)
TOTAL_PODS=$(kubectl get pods -n $NAMESPACE -l "maas.x0tta6bl4.net/tenant=$TENANT_ID" | grep -v NAME | wc -l)

if [ "$READY_PODS" -eq 0 ]; then
    echo -e "${RED}❌ Ошибка: В кластере нет готовых подов для тенанта $TENANT_ID${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Сеть стабильна: $READY_PODS/$TOTAL_PODS узлов активны.${NC}"

# 2. Inject Fault (Kill a random node)
echo -e "\n${RED}[2/3] ИНЪЕКЦИЯ СБОЯ: Принудительная остановка случайного узла...${NC}"
TARGET_POD=$(kubectl get pods -n $NAMESPACE -l "maas.x0tta6bl4.net/tenant=$TENANT_ID" -o jsonpath='{.items[0].metadata.name}')

echo -e "🔥 Killing pod: ${YELLOW}$TARGET_POD${NC}"
kubectl delete pod $TARGET_POD -n $NAMESPACE --grace-period=0 --force

# 3. Monitor Recovery (Self-Healing)
echo -e "\n${BLUE}[3/3] ОЖИДАНИЕ САМОВОССТАНОВЛЕНИЯ (MAPE-K LOOP)...${NC}"
START_TIME=$(date +%s)

while true; do
    NEW_READY=$(kubectl get pods -n $NAMESPACE -l "maas.x0tta6bl4.net/tenant=$TENANT_ID" -o jsonpath='{.items[*].status.containerStatuses[0].ready}' | grep -o "true" | wc -l)
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    echo -ne "⏱️ Прошло: ${ELAPSED}с | Активных узлов: $NEW_READY/$TOTAL_PODS \r"
    
    if [ "$NEW_READY" -ge "$TOTAL_PODS" ]; then
        echo -e "\n\n${GREEN}✨ СЕТЬ ПОЛНОСТЬЮ ВОССТАНОВЛЕНА!${NC}"
        echo -e "📊 Фактический MTTR: ${YELLOW}${ELAPSED} секунд${NC}"
        break
    fi
    
    if [ "$ELAPSED" -gt 120 ]; then
        echo -e "\n${RED}❌ Тайм-аут: Самовосстановление заняло слишком много времени (>120с)${NC}"
        exit 1
    fi
    sleep 1
done

echo -e "\n${BLUE}============================================================${NC}"
echo -e "${GREEN}${BOLD}DEMO COMPLETED SUCCESSFULLY!${NC}"
echo -e "Перейдите в Grafana (MaaS Enterprise ROI), чтобы увидеть"
echo -e "обновленные данные об экономии простоя."
echo -e "${BLUE}============================================================${NC}"
