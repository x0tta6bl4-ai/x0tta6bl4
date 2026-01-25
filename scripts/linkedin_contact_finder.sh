#!/bin/bash
# Скрипт для поиска LinkedIn контактов
# Использование: ./scripts/linkedin_contact_finder.sh

echo "🔍 LinkedIn Contact Finder Helper"
echo "=================================="
echo ""

# Поисковые запросы
SEARCHES=(
    "CTO SaaS Russia"
    "IT Director FinTech"
    "DevOps Director Russia"
    "VP Infrastructure"
    "Platform Engineer"
    "SRE Lead"
    "Security Director"
    "CISO Russia"
)

echo "📋 Рекомендуемые поисковые запросы в LinkedIn:"
echo ""

for i in "${!SEARCHES[@]}"; do
    echo "$((i+1)). ${SEARCHES[$i]}"
done

echo ""
echo "✅ Стратегия поиска:"
echo "   1. Используйте LinkedIn Search или Sales Navigator"
echo "   2. Фильтры:"
echo "      - Location: Russia / CIS"
echo "      - Company Size: 100-1000 employees"
echo "      - Industry: Technology, Financial Services, etc."
echo "   3. Для каждой компании из EMAIL_CONTACTS_LIST.md:"
echo "      - Найдите соответствующих контактов"
echo "      - Отправьте connection request"
echo "      - После принятия отправьте сообщение"
echo ""
echo "📧 Используйте шаблоны из LINKEDIN_OUTREACH_RU.md"
echo ""
echo "🎯 Цель: 10 connection requests + 10 сообщений"
echo "💰 Ожидаемый результат: 1-2 ответа (10-20%)"

