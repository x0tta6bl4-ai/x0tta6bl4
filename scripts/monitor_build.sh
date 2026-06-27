#!/bin/bash

LOG_FILE=$(ls -t /tmp/docker_build_v3.4.0_*.log 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ]; then
    echo "❌ Лог файл не найден"
    exit 1
fi

echo "=== Docker Build Monitor ==="
echo "Время: $(date '+%H:%M:%S')"
echo "Лог: $LOG_FILE"
echo ""

# Проверить статус
if grep -q "✅ BUILD УСПЕШЕН" "$LOG_FILE" 2>/dev/null; then
    echo "✅ BUILD ЗАВЕРШЁН УСПЕШНО!"
    echo ""
    docker images x0tta6bl4:3.4.0 2>&1 | head -3
    exit 0
elif grep -q "❌ BUILD FAILED" "$LOG_FILE" 2>/dev/null; then
    echo "❌ BUILD ЗАВЕРШИЛСЯ С ОШИБКОЙ!"
    echo ""
    tail -20 "$LOG_FILE" | grep -i "error\|failed" -A 5
    exit 1
fi

# Показать прогресс
echo "🟢 BUILD В ПРОЦЕССЕ..."
echo ""

# Последние события
echo "📈 Последние 10 событий:"
tail -50 "$LOG_FILE" | grep -E "Step|#\[|DONE|CACHED|transferring|ERROR" | tail -10

echo ""
echo "📊 Статистика:"
SIZE=$(wc -l < "$LOG_FILE" 2>/dev/null || echo "0")
echo "  Строк в логе: $SIZE"

# Проверить активный процесс
if ps aux | grep -q "[d]ocker build"; then
    echo "  Процесс: ✅ Активен"
else
    echo "  Процесс: ⚠️  Не найден (возможно завершился)"
fi

echo ""
echo "💡 Для просмотра в реальном времени: tail -f $LOG_FILE"
