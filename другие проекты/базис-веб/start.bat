@echo off
REM 🚀 Скрипт запуска приложения BASIS-WEB локально (Windows)

setlocal enabledelayedexpansion

echo 🎯 Запуск BASIS-WEB...
echo.

REM Проверить наличие Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Node.js не установлен
    echo 📥 Установите Node.js с https://nodejs.org/
    pause
    exit /b 1
)

REM Проверить версию Node.js
for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
echo ✓ Node.js версия: %NODE_VERSION%

REM Проверить наличие npm
where npm >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ npm не установлен
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
echo ✓ npm версия: %NPM_VERSION%

echo.
echo 📦 Проверка зависимостей...

REM Проверить наличие node_modules
if not exist "node_modules" (
    echo ⚠️  node_modules не найден
    echo 📥 Установка зависимостей...
    call npm install
    if !ERRORLEVEL! NEQ 0 (
        echo ❌ Ошибка при установке зависимостей
        pause
        exit /b 1
    )
) else (
    echo ✓ node_modules найден
)

echo.
echo 🔧 Проверка конфигурации...

REM Проверить .env.local
if not exist ".env.local" (
    echo ⚠️  .env.local не найден
    echo 📝 Создание .env.local...
    (
        echo # Gemini API Key ^(получить на https://aistudio.google.com/apikey^)
        echo VITE_GEMINI_API_KEY=your_api_key_here
        echo.
        echo # Опционально
        echo VITE_DEBUG=false
    ) > .env.local
    echo ⚠️  Замените 'your_api_key_here' на реальный ключ Gemini API
) else (
    echo ✓ .env.local найден
)

echo.
echo 🎬 Запуск приложения...
echo ════════════════════════════════════════════════════════
echo.
echo 📱 Приложение будет доступно по адресу:
echo    http://localhost:5173
echo.
echo 💡 Нажмите Ctrl+C для остановки
echo ════════════════════════════════════════════════════════
echo.

REM Запустить dev сервер
call npm run dev

pause
