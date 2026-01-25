#!/bin/bash
set -e
set -o pipefail

VERSION="3.4.0"
LOG_FILE="/home/x0ttta6bl4/.gemini/tmp/da868052b21fa3b7a4183be8a40d6a1193ba25404ce7b233195ce0da24422ed9/docker_build_v${VERSION}_$(date +%Y%m%d_%H%M%S).log"
DOCKERFILE="Dockerfile"
IMAGE_NAME="x0tta6bl4:${VERSION}"

echo "=== Docker Build Attempt $(date) ===" | tee -a "$LOG_FILE"
echo "DEBUG_LOG_FILE: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Version: $VERSION" | tee -a "$LOG_FILE"
echo "Image: $IMAGE_NAME" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Проверить свободное место
FREE_SPACE=$(df /mnt/AC74CC2974CBF3DC | awk 'NR==2 {print int($4/1024/1024)}')
echo "Free Disk Space: ${FREE_SPACE}GB" | tee -a "$LOG_FILE"

if [ "$FREE_SPACE" -lt 50 ]; then
    echo "❌ ОШИБКА: Недостаточно дискового пространства!" | tee -a "$LOG_FILE"
    echo "   Required: 50GB, Available: ${FREE_SPACE}GB" | tee -a "$LOG_FILE"
    exit 1
fi

# Проверить доступную память
FREE_MEM=$(free -m | awk 'NR==2 {print $7}')
echo "Free Memory: ${FREE_MEM}MB" | tee -a "$LOG_FILE"

if [ "$FREE_MEM" -lt 1024 ]; then
    echo "⚠️  WARNING: Low memory (< 1GB free)" | tee -a "$LOG_FILE"
fi

# Проверить Docker daemon
if ! systemctl is-active --quiet docker; then
    echo "❌ ОШИБКА: Docker daemon не запущен!" | tee -a "$LOG_FILE"
    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "=== Starting Build ===" | tee -a "$LOG_FILE"

# Запустить build с логированием
cd /mnt/AC74CC2974CBF3DC

if docker build \
    --progress=plain \
    --tag "$IMAGE_NAME" \
    --tag "x0tta6bl4:latest" \
    -f "$DOCKERFILE" \
    . 2>&1 | tee -a "$LOG_FILE"; then
    
    echo "" | tee -a "$LOG_FILE"
    echo "✅ BUILD УСПЕШЕН!" | tee -a "$LOG_FILE"
    docker images "$IMAGE_NAME" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "📋 Лог сохранён в: $LOG_FILE" | tee -a "$LOG_FILE"
    
else
    EXITCODE=$?
    echo "" | tee -a "$LOG_FILE"
    echo "❌ BUILD FAILED (exit code: $EXITCODE)" | tee -a "$LOG_FILE"
    echo "See $LOG_FILE for details"
    exit $EXITCODE
fi



