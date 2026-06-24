#!/bin/bash
# 🔧 АВТОМАТИЧЕСКИЙ СКРИПТ ОПТИМИЗАЦИИ x0tta6bl4
# Дата: 4 января 2026
# Использование: bash optimize-system.sh [--aggressive]

set -e

echo "🚀 === x0tta6bl4 System Optimization Script ==="
echo "Время начала: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Функции
check_status() {
  echo "📊 Текущий статус:"
  echo "   Load Average: $(uptime | awk -F'load average:' '{print $2}')"
  echo "   CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2 $3 $4}')"
  top -bn1 | head -15
}

step1_delete_clusters() {
  echo ""
  echo "🔴 === ЭТАП 1: УДАЛЕНИЕ НЕИСПОЛЬЗУЕМЫХ КЛАСТЕРОВ ==="
  echo "   Это удалит control-plane-staging и local кластеры"
  read -p "   Продолжить? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "   ⏭️  Пропущено"
    return
  fi
  
  echo "   ⏳ Удаляю x0tta6bl4-control-plane-staging..."
  kind delete cluster --name x0tta6bl4-control-plane-staging --quiet 2>/dev/null || echo "   ⚠️  Не найден"
  
  echo "   ⏳ Удаляю x0tta6bl4-local..."
  kind delete cluster --name x0tta6bl4-local --quiet 2>/dev/null || echo "   ⚠️  Не найден"
  
  sleep 5
  echo "   ✅ Кластеры удалены"
  echo "   📦 Оставшиеся кластеры: $(kind get clusters 2>/dev/null | tr '\n' ', ')"
}

step2_close_ide() {
  echo ""
  echo "🔴 === ЭТАП 2: ЗАКРЫТИЕ IDE И БРАУЗЕРА ==="
  read -p "   Закрыть Cursor IDE? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    killall -9 cursor cursor-server node 2>/dev/null || true
    sleep 2
    echo "   ✅ IDE закрыта"
  fi
  
  read -p "   Закрыть Chrome/Chromium? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    killall -9 chrome chromium 2>/dev/null || true
    sleep 2
    echo "   ✅ Браузер закрыт"
  fi
}

step3_monitor() {
  echo ""
  echo "🔴 === ЭТАП 3: МОНИТОРИНГ (30 сек) ==="
  echo "   Наблюдаю за системой..."
  for i in {1..6}; do
    echo ""
    echo "   [$(($i*5))s] Load: $(uptime | awk -F'load average:' '{print $2}') | Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
    sleep 5
  done
  
  echo ""
  echo "   ✅ Мониторинг завершён"
}

step4_check_health() {
  echo ""
  echo "🟢 === ЭТАП 4: ПРОВЕРКА ЗДОРОВЬЯ ==="
  
  echo "   Контейнеры:"
  docker stats --no-stream 2>/dev/null | head -5 || echo "   ⚠️  Docker недоступен"
  
  echo ""
  echo "   Kubernetes кластеры:"
  for cluster in $(kind get clusters 2>/dev/null); do
    echo "   - $cluster: $(kubectl --context kind-$cluster get nodes 2>/dev/null | wc -l) nodes" || echo "   - $cluster: недоступен"
  done
  
  echo ""
  echo "   Статус sidecar:"
  docker exec x0tta6bl4-staging-control-plane ps aux 2>/dev/null | grep -c sidecar || echo "   ⚠️  sidecar не найден"
}

# Main flow
echo ""
echo "Доступные действия:"
echo "  1. ЭТАП 1: Удалить неиспользуемые кластеры"
echo "  2. ЭТАП 2: Закрыть IDE/браузер"
echo "  3. ЭТАП 3: Мониторить 30 сек"
echo "  4. ЭТАП 4: Проверить здоровье"
echo "  0. Выполнить все (рекомендуется)"
echo "  c. Только проверка статуса"
echo ""

if [ "$1" == "--aggressive" ]; then
  CHOICE="0"
else
  read -p "Выбери опцию (0-4, c): " CHOICE
fi

case $CHOICE in
  0)
    check_status
    step1_delete_clusters
    step2_close_ide
    step3_monitor
    step4_check_health
    ;;
  1) step1_delete_clusters ;;
  2) step2_close_ide ;;
  3) step3_monitor ;;
  4) step4_check_health ;;
  c) check_status ;;
  *)
    echo "❌ Неверный выбор"
    exit 1
    ;;
esac

echo ""
echo "✅ === ОПТИМИЗАЦИЯ ЗАВЕРШЕНА ==="
echo "Время окончания: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "📊 Финальный статус:"
check_status

