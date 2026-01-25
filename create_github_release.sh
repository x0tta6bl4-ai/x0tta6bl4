#!/bin/bash
# Автоматизированное создание GitHub Release для v3.2.0
# Требует: GitHub token в переменной окружения GITHUB_TOKEN

set -e

# Конфигурация
REPO="x0tta6bl4-ai/x0tta6bl4"
TAG="v3.2.0"
RELEASE_TITLE="v3.2.0 - SPRINT 3 Production Optimization Release"
RELEASE_NOTES_FILE="/mnt/projects/RELEASE_NOTES_v3.2.0_2026_01_25.md"

echo "🚀 Создание GitHub Release для $TAG..."

# Проверка наличия GITHUB_TOKEN
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ ОШИБКА: Переменная окружения GITHUB_TOKEN не установлена"
    echo "Установите токен: export GITHUB_TOKEN=<ваш_токен>"
    echo ""
    echo "Как получить токен:"
    echo "  1. Перейти на https://github.com/settings/tokens"
    echo "  2. Нажать 'Generate new token'"
    echo "  3. Выбрать 'repo' и 'read:user' scopes"
    echo "  4. Скопировать токен"
    exit 1
fi

# Проверка наличия файла релиз-нот
if [ ! -f "$RELEASE_NOTES_FILE" ]; then
    echo "❌ ОШИБКА: Файл релиз-нот не найден: $RELEASE_NOTES_FILE"
    exit 1
fi

# Прочтение содержимого релиз-нот
RELEASE_BODY=$(cat "$RELEASE_NOTES_FILE")

# Проверка, существует ли уже релиз
echo "Проверка существующих релизов..."
EXISTING_RELEASE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
    "https://api.github.com/repos/$REPO/releases/tags/$TAG" \
    | grep -o '"id":' | wc -l)

if [ "$EXISTING_RELEASE" -gt 0 ]; then
    echo "ℹ️  Релиз $TAG уже существует"
    echo "Обновление релиза..."
    
    # Получить ID существующего релиза
    RELEASE_ID=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/$REPO/releases/tags/$TAG" \
        | grep -o '"id":[^,]*' | head -1 | grep -o '[0-9]*')
    
    # Обновить релиз
    curl -s -X PATCH \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$REPO/releases/$RELEASE_ID" \
        -d "{
            \"tag_name\": \"$TAG\",
            \"target_commitish\": \"main\",
            \"name\": \"$RELEASE_TITLE\",
            \"body\": $(echo "$RELEASE_BODY" | jq -Rs .),
            \"draft\": false,
            \"prerelease\": false
        }" > /dev/null
    
    echo "✅ Релиз успешно обновлен!"
else
    echo "Создание нового релиза..."
    
    # Создать новый релиз
    RESPONSE=$(curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$REPO/releases" \
        -d "{
            \"tag_name\": \"$TAG\",
            \"target_commitish\": \"main\",
            \"name\": \"$RELEASE_TITLE\",
            \"body\": $(echo "$RELEASE_BODY" | jq -Rs .),
            \"draft\": false,
            \"prerelease\": false
        }")
    
    # Проверить результат
    if echo "$RESPONSE" | grep -q '"id":'; then
        RELEASE_URL=$(echo "$RESPONSE" | grep -o '"html_url":"[^"]*' | cut -d'"' -f4)
        echo "✅ Релиз успешно создан!"
        echo "📍 URL: $RELEASE_URL"
    else
        echo "❌ ОШИБКА при создании релиза:"
        echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
        exit 1
    fi
fi

echo ""
echo "✨ GitHub Release automation завершена!"
echo "Проверить релиз: https://github.com/$REPO/releases/tag/$TAG"
