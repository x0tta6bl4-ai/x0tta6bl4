#!/bin/bash
set -e

# Легковесная сборка с мониторингом нагрузки
VERSION="3.4.0"
LOG_FILE="/tmp/docker_build_v${VERSION}_$(date '+%Y%m%d_%H%M%S').log"
DOCKERFILE="Dockerfile"
IMAGE_NAME="x0tta6bl4:${VERSION}"

echo "=== Docker Build (Light Mode) ===" | tee "$LOG_FILE"
echo "Version: $VERSION" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Проверка нагрузки ПЕРЕД сборкой
echo "=== System Check ===" | tee -a "$LOG_FILE"
LOAD_1MIN=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | tr -d '%us,')
MEM_FREE=$(free -m | awk 'NR==2 {print $7}')

echo "Load Average (1min): $LOAD_1MIN" | tee -a "$LOG_FILE"
echo "CPU Usage: ${CPU_USAGE}%" | tee -a "$LOG_FILE"
echo "Free Memory: ${MEM_FREE}MB" | tee -a "$LOG_FILE"

# Проверка критических порогов
if (( $(echo "$LOAD_1MIN > 8.0" | bc -l 2>/dev/null || echo 0) )); then
    echo "⚠️  WARNING: High Load Average ($LOAD_1MIN). Build may be slow." | tee -a "$LOG_FILE"
    read -t 5 -p "Continue anyway? (y/n) " -n 1 -r || REPLY="y"
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Build cancelled by user" | tee -a "$LOG_FILE"
        exit 1
    fi
fi

if [ "$MEM_FREE" -lt 2048 ]; then
    echo "⚠️  WARNING: Low free memory (${MEM_FREE}MB < 2GB)" | tee -a "$LOG_FILE"
fi

# Проверка свободного места
FREE_SPACE=$(df /mnt/AC74CC2974CBF3DC | awk 'NR==2 {print int($4/1024/1024)}')
echo "Free Disk Space: ${FREE_SPACE}GB" | tee -a "$LOG_FILE"

if [ "$FREE_SPACE" -lt 50 ]; then
    echo "❌ ERROR: Insufficient disk space (${FREE_SPACE}GB < 50GB)" | tee -a "$LOG_FILE"
    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "=== Starting Build ===" | tee -a "$LOG_FILE"
echo "Build will use .dockerignore to exclude Camera/ and large files" | tee -a "$LOG_FILE"
echo "Monitor: tail -f $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Флаг для мониторинга
touch /tmp/docker_build_running.flag

# Запуск мониторинга в фоне
/mnt/AC74CC2974CBF3DC/scripts/monitor_system_load.sh > /tmp/system_load_monitor.log 2>&1 &
MONITOR_PID=$!
echo "System monitor started (PID: $MONITOR_PID)" | tee -a "$LOG_FILE"

# Функция очистки при выходе
cleanup() {
    echo "" | tee -a "$LOG_FILE"
    echo "=== Cleanup ===" | tee -a "$LOG_FILE"
    kill $MONITOR_PID 2>/dev/null || true
    rm -f /tmp/docker_build_running.flag
    echo "Cleanup complete" | tee -a "$LOG_FILE"
}
trap cleanup EXIT

# Запуск сборки с ограничениями
# Используем --memory и --cpus для ограничения ресурсов buildkit
export DOCKER_BUILDKIT=1
export BUILDKIT_STEP_LOG_MAX_SIZE=50000000
export BUILDKIT_STEP_LOG_MAX_SPEED=10000000

if docker build \
    --progress=plain \
    --tag "$IMAGE_NAME" \
    --tag "x0tta6bl4:latest" \
    -f "$DOCKERFILE" \
    . 2>&1 | tee -a "$LOG_FILE"; then
    
    echo "" | tee -a "$LOG_FILE"
    echo "✅ BUILD SUCCESSFUL!" | tee -a "$LOG_FILE"
    echo "Image: $IMAGE_NAME" | tee -a "$LOG_FILE"
    docker images "$IMAGE_NAME" | tee -a "$LOG_FILE"
    
    # Финальная проверка нагрузки
    echo "" | tee -a "$LOG_FILE"
    echo "=== Final System Check ===" | tee -a "$LOG_FILE"
    uptime | tee -a "$LOG_FILE"
    top -bn1 | head -5 | tee -a "$LOG_FILE"
    
else
    EXITCODE=$?
    echo "" | tee -a "$LOG_FILE"
    echo "❌ BUILD FAILED (exit code: $EXITCODE)" | tee -a "$LOG_FILE"
    echo "See $LOG_FILE for details" | tee -a "$LOG_FILE"
    exit $EXITCODE
fi



