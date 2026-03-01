#!/bin/bash
# x0tta6bl4 Interactive Demo Scenario
# Показывает самоисцеление сети при атаке.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

clear
echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}    x0tta6bl4: Autonomous Mesh Intelligence Demo      ${NC}"
echo -e "${CYAN}======================================================${NC}"
echo ""

sleep 1
echo -e "🚀 [1/4] Инициализация виртуальной Mesh-топологии (5 узлов)..."
sleep 2
echo -e "✅ Топология построена. Консенсус достигнут."
echo -e "   📍 Маршрут: Node A -> Node B -> Node C -> Exit"
echo ""

sleep 2
echo -e "🛡️ [2/4] Установка Post-Quantum (Kyber) сессий..."
sleep 1
echo -e "✅ ML-KEM-768 Handshake успешный. Трафик защищен."
echo ""

sleep 2
echo -e "🔥 ${RED}[ALERT] Внимание! Обнаружена аномалия трафика на Node B!${NC}"
echo -e "   Атака: ${YELLOW}DDoS / Packet Drop Spike (loss > 80%)${NC}"
echo ""

sleep 2
echo -e "🧠 [3/4] Активация MAPE-K (Monitor-Analyze-Plan-Execute)..."
echo -e "   ⏳ Analyze: GraphSAGE детектирует компрометацию узла B."
sleep 1
echo -e "   ⏳ Plan: LLM Agent предлагает изоляцию узла B и маршрутизацию через узел D."
sleep 1
echo -e "   ⚡ Execute: Обновление правил eBPF/XDP на соседних узлах..."
echo ""

sleep 2
echo -e "✨ [4/4] Самоисцеление завершено! (MTTR: 1.4s)"
echo -e "✅ Трафик успешно перенаправлен."
echo -e "   📍 Новый маршрут: Node A -> Node D -> Node C -> Exit"
echo ""

echo -e "${GREEN}Демонстрация успешно завершена.${NC}"
echo -e "👉 Для доступа к дашборду запустите: ${CYAN}make run-api${NC}"
echo ""
