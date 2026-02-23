#!/bin/bash
# x0tta6bl4 Magic Installer v1.0
# Usage: curl -sSL https://get.x0t.io | bash -s <JOIN_TOKEN>

TOKEN="${1}"
API_URL="http://localhost:8000/api/v1/maas" # В проде будет публичный URL

echo "--- x0tta6bl4: Initializing Secure Node ---"

# 1. Проверка зависимостей
if ! command -v docker &> /dev/null; then
    echo "Installing engine..."
    sudo apt-get update -qq && sudo apt-get install -y docker.io -qq
fi

# 2. Автоматическая регистрация устройства
NODE_ID="node-$(hostname)-$(date +%s)"
echo "Registering device: $NODE_ID"

# 3. Запуск контейнера-невидимки
# Он сам подтянет ключи, настроит PQC и свяжется с мешем
sudo docker run -d 
    --name x0t-agent 
    --restart always 
    -e JOIN_TOKEN="$TOKEN" 
    -e NODE_ID="$NODE_ID" 
    -e API_URL="$API_URL" 
    x0tta6bl4/agent:latest

echo "--- SUCCESS ---"
echo "Your device is now INVISIBLE and PROTECTED."
echo "Manage it at: https://my.x0t.io"
