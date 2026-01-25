#!/bin/bash
# Интеграционный тест для Ledger API

set -e

echo "🧪 Интеграционный тест Ledger API"
echo "=================================="

BASE_URL="${BASE_URL:-http://localhost:8080}"
LEDGER_API="${BASE_URL}/api/v1/ledger"

echo ""
echo "1️⃣ Проверка статуса..."
STATUS_RESPONSE=$(curl -s "${LEDGER_API}/status")
echo "✅ Статус получен:"
echo "$STATUS_RESPONSE" | python3 -m json.tool

echo ""
echo "2️⃣ Индексирование ledger..."
INDEX_RESPONSE=$(curl -s -X POST "${LEDGER_API}/index")
echo "✅ Индексирование завершено:"
echo "$INDEX_RESPONSE" | python3 -m json.tool

echo ""
echo "3️⃣ Тест поиска (POST)..."
SEARCH_RESPONSE=$(curl -s -X POST "${LEDGER_API}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "Какие метрики?", "top_k": 3}')
echo "✅ Результаты поиска:"
echo "$SEARCH_RESPONSE" | python3 -m json.tool

echo ""
echo "4️⃣ Тест поиска (GET)..."
SEARCH_GET_RESPONSE=$(curl -s "${LEDGER_API}/search?q=Какие%20компоненты&top_k=3")
echo "✅ Результаты поиска (GET):"
echo "$SEARCH_GET_RESPONSE" | python3 -m json.tool

echo ""
echo "5️⃣ Тест Drift Detection..."
DRIFT_RESPONSE=$(curl -s -X POST "${LEDGER_API}/drift/detect")
echo "✅ Результаты drift detection:"
echo "$DRIFT_RESPONSE" | python3 -m json.tool

echo ""
echo "✅ Все тесты пройдены успешно!"

