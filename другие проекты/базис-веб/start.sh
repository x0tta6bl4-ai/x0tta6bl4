#!/bin/bash

# 🚀 Скрипт запуска приложения BASIS-WEB локально

echo "🎯 Запуск BASIS-WEB..."
echo ""

# Проверить наличие Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js не установлен"
    echo "📥 Установите Node.js с https://nodejs.org/"
    exit 1
fi

# Проверить версию Node.js
NODE_VERSION=$(node -v)
echo "✓ Node.js версия: $NODE_VERSION"

# Проверить наличие npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm не установлен"
    exit 1
fi

NPM_VERSION=$(npm -v)
echo "✓ npm версия: $NPM_VERSION"

echo ""
echo "📦 Проверка зависимостей..."

# Проверить наличие node_modules
if [ ! -d "node_modules" ]; then
    echo "⚠️  node_modules не найден"
    echo "📥 Установка зависимостей..."
    npm install
else
    echo "✓ node_modules найден"
fi

echo ""
echo "🔧 Проверка конфигурации..."

# Проверить .env.local
if [ ! -f ".env.local" ]; then
    echo "⚠️  .env.local не найден"
    echo "📝 Создание .env.local..."
    cat > .env.local << 'EOF'
# Gemini API Key (получить на https://aistudio.google.com/apikey)
VITE_GEMINI_API_KEY=your_api_key_here

# Опционально
VITE_DEBUG=false
EOF
    echo "⚠️  Замените 'your_api_key_here' на реальный ключ Gemini API"
else
    echo "✓ .env.local найден"
fi

echo ""
echo "🎬 Запуск приложения..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Приложение будет доступно по адресу:"
echo "   http://localhost:5173"
echo ""
echo "💡 Нажмите Ctrl+C для остановки"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Запустить dev сервер
npm run dev
