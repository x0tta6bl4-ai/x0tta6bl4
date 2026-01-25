#!/bin/bash
# Мониторинг нагрузки системы во время Docker build

LOG_FILE="/tmp/system_load_monitor.log"
ALERT_LOAD=8.0
ALERT_CPU=80.0

echo "=== System Load Monitor ===" | tee "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "Alert thresholds: Load > $ALERT_LOAD, CPU > $ALERT_CPU%" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Load Average
    LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
    
    # CPU Usage
    CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | tr -d '%us,')
    
    # Memory
    MEM_FREE=$(free -m | awk 'NR==2 {printf "%.1f", $7}')
    MEM_TOTAL=$(free -m | awk 'NR==2 {print $2}')
    MEM_PERCENT=$(free | awk 'NR==2 {printf "%.1f", ($3/$2)*100}')
    
    # I/O Wait
    IOWAIT=$(top -bn1 | grep "Cpu(s)" | awk '{print $10}' | tr -d '%wa,')
    
    # Docker build process
    BUILD_PID=$(pgrep -f "docker build.*x0tta6bl4")
    if [ -n "$BUILD_PID" ]; then
        BUILD_CPU=$(ps -p "$BUILD_PID" -o %cpu= 2>/dev/null | tr -d ' ' || echo "0")
        BUILD_MEM=$(ps -p "$BUILD_PID" -o %mem= 2>/dev/null | tr -d ' ' || echo "0")
        BUILD_STATUS="✅ RUNNING (PID: $BUILD_PID, CPU: ${BUILD_CPU}%, MEM: ${BUILD_MEM}%)"
    else
        BUILD_STATUS="❌ NOT RUNNING"
    fi
    
    # Log
    echo "[$TIMESTAMP] Load: $LOAD | CPU: ${CPU}% | Mem: ${MEM_PERCENT}% (${MEM_FREE}MB free) | I/O Wait: ${IOWAIT}% | Build: $BUILD_STATUS" | tee -a "$LOG_FILE"
    
    # Alerts (using awk for float comparison)
    LOAD_NUM=$(echo "$LOAD" | awk '{print $1+0}')
    CPU_NUM=$(echo "$CPU" | awk '{print $1+0}')
    
    if (( $(awk "BEGIN {print ($LOAD_NUM > $ALERT_LOAD)}") )); then
        echo "⚠️  ALERT: High Load Average ($LOAD > $ALERT_LOAD)" | tee -a "$LOG_FILE"
    fi
    
    if (( $(awk "BEGIN {print ($CPU_NUM > $ALERT_CPU)}") )); then
        echo "⚠️  ALERT: High CPU Usage (${CPU}% > ${ALERT_CPU}%)" | tee -a "$LOG_FILE"
    fi
    
    # Check if build is still running
    if [ -z "$BUILD_PID" ] && [ -f /tmp/docker_build_running.flag ]; then
        echo "✅ Build completed or stopped" | tee -a "$LOG_FILE"
        rm -f /tmp/docker_build_running.flag
        break
    fi
    
    sleep 10
done

echo "" | tee -a "$LOG_FILE"
echo "=== Monitor stopped: $(date) ===" | tee -a "$LOG_FILE"

