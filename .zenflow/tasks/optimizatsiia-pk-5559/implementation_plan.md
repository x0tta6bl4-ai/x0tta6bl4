# Детальный План Реализации: Оптимизация Ubuntu

**Дата:** 24 января 2026  
**Версия:** 1.0  
**Сложность:** Medium

---

## Обзор

Этот план разбивает оптимизацию Ubuntu на 7 фаз с конкретными задачами, критериями верификации и временными оценками.

**Общее время:** 3.5-5 часов (распределено на 2 дня)  
**Ожидаемый результат:** Освобождение 20-30GB дискового пространства, ускорение загрузки на 50%+

---

## Phase 1: Preparation & Safety (30 минут)

### Статус: [ ] Not Started

**Цель:** Создать backup и подготовительные скрипты

### Задачи:

#### [ ] Task 1.1: System Backup
```bash
# Создать snapshot через Timeshift (если установлен)
sudo timeshift --create --comments "Before optimization 2026-01-24"

# ИЛИ через LVM snapshot
sudo lvcreate -L 5G -s -n ubuntu-lv-snapshot /dev/ubuntu-vg/ubuntu-lv
```

**Verification:**
- Snapshot создан и виден в `sudo lvs` или `sudo timeshift --list`

#### [ ] Task 1.2: Create Scripts Directory
```bash
mkdir -p /home/x0ttta6bl4/scripts/optimization
cd /home/x0ttta6bl4/scripts/optimization
```

**Verification:**
- Директория создана: `ls -la /home/x0ttta6bl4/scripts/optimization`

#### [ ] Task 1.3: System Analyzer Script

**Создать:** `scripts/optimization/system_analyzer.sh`

```bash
#!/bin/bash
# System Analyzer - собирает метрики before/after

SNAPSHOT_DIR="/home/x0ttta6bl4/.zenflow/tasks/optimizatsiia-pk-5559"

snapshot() {
    local name=$1
    local output="${SNAPSHOT_DIR}/baseline_${name}.json"
    
    cat > "$output" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "disk": {
    "usage_percent": $(df / | tail -1 | awk '{print $5}' | sed 's/%//'),
    "used_gb": "$(df -BG / | tail -1 | awk '{print $3}')",
    "free_gb": "$(df -BG / | tail -1 | awk '{print $4}')"
  },
  "docker": {
    "images_count": $(docker images -q | wc -l),
    "volumes_count": $(docker volume ls -q | wc -l),
    "total_size": "$(docker system df --format '{{.Size}}')"
  },
  "journal_size": "$(journalctl --disk-usage | awk '{print $7}')",
  "boot_time": "$(systemd-analyze time | grep -oP '\d+\.\d+s \(kernel\)' || echo 'N/A')"
}
EOF
    
    echo "✅ Snapshot saved: $output"
    cat "$output"
}

compare() {
    local before="${SNAPSHOT_DIR}/baseline_before.json"
    local after="${SNAPSHOT_DIR}/baseline_after.json"
    
    if [ ! -f "$before" ] || [ ! -f "$after" ]; then
        echo "❌ ERROR: Missing snapshot files"
        exit 1
    fi
    
    echo "📊 Comparison Report"
    echo "===================="
    echo ""
    echo "Disk Usage:"
    before_usage=$(jq -r '.disk.usage_percent' "$before")
    after_usage=$(jq -r '.disk.usage_percent' "$after")
    echo "  Before: ${before_usage}%"
    echo "  After:  ${after_usage}%"
    echo "  Change: $((after_usage - before_usage))%"
    echo ""
    
    echo "Free Space:"
    before_free=$(jq -r '.disk.free_gb' "$before")
    after_free=$(jq -r '.disk.free_gb' "$after")
    echo "  Before: $before_free"
    echo "  After:  $after_free"
    echo ""
    
    echo "Docker Images:"
    before_images=$(jq -r '.docker.images_count' "$before")
    after_images=$(jq -r '.docker.images_count' "$after")
    echo "  Before: $before_images"
    echo "  After:  $after_images"
    echo "  Removed: $((before_images - after_images))"
}

case "$1" in
    --snapshot)
        snapshot "$2"
        ;;
    --compare)
        compare "$2" "$3"
        ;;
    *)
        echo "Usage: $0 --snapshot <before|after>"
        echo "       $0 --compare before after"
        exit 1
        ;;
esac
```

**Сделать исполняемым:**
```bash
chmod +x scripts/optimization/system_analyzer.sh
```

**Verification:**
```bash
./scripts/optimization/system_analyzer.sh --snapshot before
cat .zenflow/tasks/optimizatsiia-pk-5559/baseline_before.json
```

---

## Phase 2: Critical Disk Cleanup (1-2 часа)

### Статус: [ ] Not Started

**Цель:** Освободить минимум 20GB дискового пространства

### Task 2.1: Docker Cleanup (освобождает ~10-12GB)

#### [ ] Subtask 2.1.1: Create Docker Optimizer Script

**Создать:** `scripts/optimization/docker_optimizer.sh`

```bash
#!/bin/bash
# Docker Optimizer - очистка Docker images, volumes, build cache

set -e

DRY_RUN=false

if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
fi

echo "🐳 Docker Optimizer"
echo "=================="
echo ""

# Текущее состояние
echo "📊 Current Docker Usage:"
docker system df
echo ""

# Подсчёт потенциально освобождаемого места
reclaimable=$(docker system df --format "{{.Reclaimable}}" | head -1)
echo "💾 Reclaimable space: $reclaimable"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "🔍 DRY-RUN MODE (no changes will be made)"
    echo ""
    echo "Would execute:"
    echo "  - docker image prune -a (remove all unused images)"
    echo "  - docker volume prune (remove unused volumes)"
    echo "  - docker builder prune (remove build cache)"
    echo "  - docker container prune (remove stopped containers)"
    exit 0
fi

# Подтверждение
read -p "🗑️  Remove unused Docker resources? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Cancelled"
    exit 0
fi

# Очистка
echo ""
echo "🧹 Cleaning Docker..."
echo ""

echo "1. Removing unused images..."
docker image prune -a -f

echo "2. Removing unused volumes..."
docker volume prune -f

echo "3. Removing build cache..."
docker builder prune -a -f

echo "4. Removing stopped containers..."
docker container prune -f

echo ""
echo "✅ Docker cleanup completed!"
echo ""
echo "📊 New Docker Usage:"
docker system df
```

**Сделать исполняемым:**
```bash
chmod +x scripts/optimization/docker_optimizer.sh
```

**Verification:**
```bash
./scripts/optimization/docker_optimizer.sh --dry-run  # Проверка
./scripts/optimization/docker_optimizer.sh            # Выполнение
docker system df                                      # Проверка результата
```

**Success Criteria:**
- Docker total size <5GB
- Images count <8
- Volumes count <15

---

### Task 2.2: APT Cache Cleanup

#### [ ] Subtask 2.2.1: Create Disk Cleanup Script

**Создать:** `scripts/optimization/disk_cleanup.sh`

```bash
#!/bin/bash
# Disk Cleanup - комплексная очистка диска

set -e

DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
fi

echo "🧹 Disk Cleanup Utility"
echo "======================"
echo ""

# Функция для безопасного выполнения команды
run_cmd() {
    local desc=$1
    shift
    
    echo "▶ $desc"
    
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] Would execute: $@"
    else
        "$@"
        echo "  ✅ Done"
    fi
    echo ""
}

# 1. APT Cache Cleanup
echo "📦 APT Cache Cleanup"
echo "-------------------"
apt_cache_size=$(du -sh /var/cache/apt 2>/dev/null | cut -f1 || echo "0")
echo "Current APT cache size: $apt_cache_size"
echo ""

run_cmd "Cleaning APT cache" sudo apt-get clean
run_cmd "Autocleaning APT" sudo apt-get autoclean
run_cmd "Autoremoving packages" sudo apt-get autoremove --purge -y

# 2. Journal Cleanup
echo "📝 Journal Cleanup"
echo "-----------------"
journal_size=$(journalctl --disk-usage | awk '{print $7}')
echo "Current journal size: $journal_size"
echo ""

run_cmd "Vacuuming journal (7 days)" sudo journalctl --vacuum-time=7d
run_cmd "Vacuuming journal (100MB max)" sudo journalctl --vacuum-size=100M

# 3. Old Kernels Cleanup
echo "🐧 Old Kernels Cleanup"
echo "---------------------"
current_kernel=$(uname -r)
echo "Current kernel: $current_kernel"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] Would remove old kernels except current and latest"
else
    # Получить список всех ядер кроме текущего
    old_kernels=$(dpkg --list | grep linux-image | grep -v "$current_kernel" | awk '{print $2}' | grep -v 'linux-image-generic' | head -n -1)
    
    if [ -n "$old_kernels" ]; then
        echo "Removing old kernels:"
        echo "$old_kernels"
        sudo apt-get purge -y $old_kernels
        sudo update-grub
        echo "✅ Old kernels removed"
    else
        echo "ℹ️  No old kernels to remove"
    fi
fi
echo ""

# 4. Temporary Files Cleanup
echo "🗑️  Temporary Files Cleanup"
echo "-------------------------"

run_cmd "Cleaning /tmp (>7 days)" sudo find /tmp -type f -atime +7 -delete
run_cmd "Cleaning /var/tmp (>30 days)" sudo find /var/tmp -type f -atime +30 -delete
run_cmd "Cleaning user cache" rm -rf ~/.cache/thumbnails/*
run_cmd "Emptying trash" rm -rf ~/.local/share/Trash/*

# 5. Large Files Analysis
echo "🔍 Large Files Analysis"
echo "----------------------"
echo "Finding files >100MB..."
echo ""

if [ "$DRY_RUN" = false ]; then
    find / -type f -size +100M 2>/dev/null | while read file; do
        size=$(du -h "$file" | cut -f1)
        echo "  $size - $file"
    done | sort -rh | head -20 > /tmp/large_files_report.txt
    
    echo "Top 10 largest files:"
    head -10 /tmp/large_files_report.txt
    echo ""
    echo "Full report: /tmp/large_files_report.txt"
fi

echo ""
echo "✅ Disk cleanup completed!"
```

**Сделать исполняемым:**
```bash
chmod +x scripts/optimization/disk_cleanup.sh
```

**Verification:**
```bash
./scripts/optimization/disk_cleanup.sh --dry-run  # Проверка
sudo ./scripts/optimization/disk_cleanup.sh       # Выполнение
df -h /                                           # Проверка результата
```

**Success Criteria:**
- `/var/cache/apt` <100MB
- Journal size <100MB
- Old kernels removed (только 2 последних оставлены)
- `/tmp` и `/var/tmp` очищены

---

## Phase 3: Git Configuration Fix (5-10 минут)

### Статус: [ ] Not Started

**Цель:** Исправить git safe.directory для всех репозиториев

### Task 3.1: Git Fix Script

#### [ ] Subtask 3.1.1: Create Git Fix Script

**Создать:** `scripts/optimization/git_fix.sh`

```bash
#!/bin/bash
# Git Configuration Fix - исправление safe.directory

echo "🔧 Git Configuration Fix"
echo "======================="
echo ""

# Найти все git репозитории в домашней директории
echo "🔍 Finding all git repositories..."
repos=$(find /home/x0ttta6bl4 -name ".git" -type d 2>/dev/null)

count=0
for gitdir in $repos; do
    repo=$(dirname "$gitdir")
    echo "  Adding: $repo"
    git config --global --add safe.directory "$repo"
    ((count++))
done

echo ""
echo "✅ Added $count repositories to safe.directory"
echo ""

# Исправить права доступа на .zenflow
echo "🔐 Fixing permissions for .zenflow..."
find /home/x0ttta6bl4/.zenflow -type d -exec chmod 755 {} \; 2>/dev/null
find /home/x0ttta6bl4/.zenflow -type f -exec chmod 644 {} \; 2>/dev/null
echo "✅ Permissions fixed"
echo ""

# Проверка
echo "🧪 Testing git access..."
cd /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559 2>/dev/null || {
    echo "⚠️  WARNING: Test repository not found"
    exit 0
}

if git status &>/dev/null; then
    echo "✅ Git working correctly!"
else
    echo "❌ Git still has issues"
    exit 1
fi
```

**Сделать исполняемым и запустить:**
```bash
chmod +x scripts/optimization/git_fix.sh
./scripts/optimization/git_fix.sh
```

**Verification:**
```bash
cd /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559
git status  # Должно работать без ошибок
```

---

## Phase 4: System Services Optimization (30-60 минут)

### Статус: [ ] Not Started

**Цель:** Оптимизировать загрузку системы (уменьшить время на 50%)

### Task 4.1: Services Optimizer Script

#### [ ] Subtask 4.1.1: Create Services Optimizer

**Создать:** `scripts/optimization/services_optimizer.sh`

```bash
#!/bin/bash
# Services Optimizer - оптимизация systemd сервисов

set -e

DRY_RUN=false
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
fi

echo "⚡ System Services Optimizer"
echo "==========================="
echo ""

# Анализ текущего состояния
echo "📊 Current Boot Time:"
systemd-analyze time
echo ""

echo "🐌 Slowest Services (top 10):"
systemd-analyze blame | head -10
echo ""

# Сохранить отчёт
systemd-analyze blame > /tmp/services_before.txt
echo "📄 Full report saved: /tmp/services_before.txt"
echo ""

# Функция для безопасного отключения сервиса
disable_service() {
    local service=$1
    local reason=$2
    
    if systemctl is-enabled "$service" &>/dev/null; then
        echo "  ▶ $service"
        echo "    Reason: $reason"
        
        if [ "$DRY_RUN" = true ]; then
            echo "    [DRY-RUN] Would disable and mask"
        else
            sudo systemctl disable "$service" 2>/dev/null || true
            sudo systemctl mask "$service" 2>/dev/null || true
            echo "    ✅ Disabled"
        fi
    else
        echo "  ℹ️  $service already disabled"
    fi
    echo ""
}

# Список сервисов для отключения
echo "🗑️  Disabling Unnecessary Services"
echo "--------------------------------"
echo ""

# Plymouth (boot splash)
disable_service "plymouth-quit-wait.service" "Boot splash not needed for server"

# Snapd (если не используется)
if ! snap list &>/dev/null || [ $(snap list | wc -l) -le 1 ]; then
    disable_service "snapd.service" "Snap not in use"
    disable_service "snapd.socket" "Snap not in use"
    disable_service "snapd.seeded.service" "Snap not in use"
else
    echo "ℹ️  Snapd is in use, keeping enabled"
    echo ""
fi

# Bluetooth (если не используется)
if ! bluetoothctl show &>/dev/null; then
    disable_service "bluetooth.service" "Bluetooth not in use"
fi

# ModemManager (если нет модема)
disable_service "ModemManager.service" "No modem present"

# CUPS (если нет принтера)
if ! lpstat -p &>/dev/null 2>&1; then
    disable_service "cups.service" "No printer configured"
    disable_service "cups-browsed.service" "No printer configured"
fi

# NetworkManager-wait-online optimization
echo "🌐 Optimizing NetworkManager-wait-online"
echo "--------------------------------------"
echo ""

nm_override="/etc/systemd/system/NetworkManager-wait-online.service.d/override.conf"

if [ "$DRY_RUN" = true ]; then
    echo "[DRY-RUN] Would create: $nm_override"
else
    sudo mkdir -p /etc/systemd/system/NetworkManager-wait-online.service.d/
    sudo tee "$nm_override" > /dev/null <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/nm-online -q --timeout=5
EOF
    echo "✅ Created NetworkManager override (5s timeout)"
fi
echo ""

# Reload systemd
if [ "$DRY_RUN" = false ]; then
    echo "🔄 Reloading systemd daemon..."
    sudo systemctl daemon-reload
    echo "✅ Reloaded"
    echo ""
fi

echo "✅ Services optimization completed!"
echo ""
echo "ℹ️  Reboot required to see boot time improvements"
```

**Сделать исполняемым:**
```bash
chmod +x scripts/optimization/services_optimizer.sh
```

**Verification:**
```bash
./scripts/optimization/services_optimizer.sh --dry-run  # Проверка
sudo ./scripts/optimization/services_optimizer.sh       # Выполнение
sudo reboot                                             # Перезагрузка
systemd-analyze time                                    # Проверка времени загрузки
```

**Success Criteria:**
- Boot time уменьшен на >30%
- Нет сервисов с временем загрузки >5s (кроме docker)
- `plymouth-quit-wait.service` отключен или masked

---

## Phase 5: Automated Maintenance (30-45 минут)

### Статус: [ ] Not Started

**Цель:** Настроить автоматическую очистку и мониторинг

### Task 5.1: Systemd Timer для Disk Cleanup

#### [ ] Subtask 5.1.1: Create Maintenance Script

**Создать:** `scripts/optimization/automated_maintenance.sh`

```bash
#!/bin/bash
# Automated Maintenance - еженедельная автоматическая очистка

LOG_FILE="/var/log/automated-maintenance.log"

log() {
    echo "[$(date -Iseconds)] $1" | sudo tee -a "$LOG_FILE"
}

log "=== Starting automated maintenance ==="

# APT cleanup
log "Running APT cleanup..."
sudo apt-get clean
sudo apt-get autoclean
sudo apt-get autoremove --purge -y

# Journal cleanup
log "Running journal cleanup..."
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=100M

# Docker cleanup (только unused)
log "Running Docker cleanup..."
docker image prune -f
docker volume prune -f
docker builder prune -f

# Проверка использования диска
usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
log "Current disk usage: ${usage}%"

if [ "$usage" -gt 85 ]; then
    log "⚠️  WARNING: Disk usage above 85%!"
    # Можно добавить отправку уведомления
fi

log "=== Maintenance completed ==="
```

**Сделать исполняемым:**
```bash
chmod +x scripts/optimization/automated_maintenance.sh
```

#### [ ] Subtask 5.1.2: Create Systemd Service

**Создать:** `/etc/systemd/system/disk-cleanup.service`

```bash
sudo tee /etc/systemd/system/disk-cleanup.service > /dev/null <<EOF
[Unit]
Description=Weekly disk cleanup and maintenance
After=network.target

[Service]
Type=oneshot
ExecStart=/home/x0ttta6bl4/scripts/optimization/automated_maintenance.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### [ ] Subtask 5.1.3: Create Systemd Timer

**Создать:** `/etc/systemd/system/disk-cleanup.timer`

```bash
sudo tee /etc/systemd/system/disk-cleanup.timer > /dev/null <<EOF
[Unit]
Description=Weekly disk cleanup timer

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
EOF
```

#### [ ] Subtask 5.1.4: Enable Timer

```bash
sudo systemctl daemon-reload
sudo systemctl enable disk-cleanup.timer
sudo systemctl start disk-cleanup.timer
```

**Verification:**
```bash
systemctl list-timers | grep disk-cleanup  # Должен быть активен
systemctl status disk-cleanup.timer        # Проверка статуса
```

---

### Task 5.2: Docker Log Rotation

#### [ ] Subtask 5.2.1: Configure Docker Logging

**Настроить:** `/etc/docker/daemon.json`

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

sudo systemctl restart docker
```

**Verification:**
```bash
docker info | grep -A 5 "Logging Driver"
# Должно показать: json-file с max-size: 10m, max-file: 3
```

---

### Task 5.3: Disk Space Monitoring

#### [ ] Subtask 5.3.1: Create Monitoring Script

**Создать:** `scripts/optimization/disk_monitor.sh`

```bash
#!/bin/bash
# Disk Monitor - мониторинг использования диска

THRESHOLD_WARNING=85
THRESHOLD_CRITICAL=90
LOG_FILE="/var/log/disk-monitor.log"

usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')

log() {
    echo "[$(date -Iseconds)] $1" | tee -a "$LOG_FILE"
}

if [ "$usage" -gt "$THRESHOLD_CRITICAL" ]; then
    log "🚨 CRITICAL: Disk usage at ${usage}% (threshold: ${THRESHOLD_CRITICAL}%)"
    log "Running emergency cleanup..."
    
    # Запустить автоматическую очистку
    /home/x0ttta6bl4/scripts/optimization/automated_maintenance.sh
    
    new_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    log "Cleanup completed. New usage: ${new_usage}%"
    
elif [ "$usage" -gt "$THRESHOLD_WARNING" ]; then
    log "⚠️  WARNING: Disk usage at ${usage}% (threshold: ${THRESHOLD_WARNING}%)"
else
    log "✅ OK: Disk usage at ${usage}%"
fi
```

**Сделать исполняемым:**
```bash
chmod +x scripts/optimization/disk_monitor.sh
```

#### [ ] Subtask 5.3.2: Add Cron Job

```bash
# Добавить задачу в crontab (проверка каждый час)
(crontab -l 2>/dev/null; echo "0 * * * * /home/x0ttta6bl4/scripts/optimization/disk_monitor.sh") | crontab -
```

**Verification:**
```bash
crontab -l | grep disk_monitor  # Должен быть в списке
./scripts/optimization/disk_monitor.sh  # Ручной запуск для теста
cat /var/log/disk-monitor.log  # Проверка логов
```

---

## Phase 6: Testing & Verification (30-45 минут)

### Статус: [ ] Not Started

**Цель:** Проверить все изменения и собрать метрики

### Task 6.1: After State Snapshot

#### [ ] Subtask 6.1.1: Create After Snapshot

```bash
cd /home/x0ttta6bl4/scripts/optimization
./system_analyzer.sh --snapshot after
```

**Verification:**
- Файл `baseline_after.json` создан

#### [ ] Subtask 6.1.2: Generate Comparison Report

```bash
./system_analyzer.sh --compare before after > /tmp/optimization_comparison.txt
cat /tmp/optimization_comparison.txt
```

**Verification:**
- Отчёт показывает улучшения:
  - Disk usage уменьшен
  - Free space увеличен
  - Docker images/volumes уменьшены

---

### Task 6.2: Automated Tests

#### [ ] Subtask 6.2.1: Disk Usage Test

```bash
#!/bin/bash
usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$usage" -lt 70 ]; then
    echo "✅ PASS: Disk usage is ${usage}% (target: <70%)"
    exit 0
else
    echo "❌ FAIL: Disk usage is ${usage}% (target: <70%)"
    exit 1
fi
```

#### [ ] Subtask 6.2.2: Docker Test

```bash
#!/bin/bash
images=$(docker images -q | wc -l)
if [ "$images" -lt 8 ]; then
    echo "✅ PASS: Docker images count: $images (target: <8)"
else
    echo "⚠️  WARNING: Docker images count: $images (target: <8)"
fi
```

#### [ ] Subtask 6.2.3: Boot Time Test

```bash
#!/bin/bash
echo "📊 Boot Time Analysis:"
systemd-analyze time
echo ""
echo "🐌 Slowest Services:"
systemd-analyze blame | head -5
```

#### [ ] Subtask 6.2.4: Git Test

```bash
#!/bin/bash
cd /home/x0ttta6bl4/.zenflow/worktrees/optimizatsiia-pk-5559
if git status &>/dev/null; then
    echo "✅ PASS: Git working correctly"
else
    echo "❌ FAIL: Git has issues"
    exit 1
fi
```

---

### Task 6.3: Manual Verification

#### [ ] Checklist:

- [ ] Система загружается без ошибок
- [ ] Docker контейнеры работают: `docker ps`
- [ ] Сетевое подключение работает: `ping -c 3 8.8.8.8`
- [ ] Git репозитории доступны: `git status` в тестовом репозитории
- [ ] Критичные сервисы запущены:
  ```bash
  systemctl status docker
  systemctl status NetworkManager
  systemctl status systemd-resolved
  ```
- [ ] Нет критичных ошибок в журнале: `journalctl -p err --since today`

---

## Phase 7: Documentation & Reporting (15-30 минут)

### Статус: [ ] Not Started

**Цель:** Создать итоговый отчёт

### Task 7.1: Generate Report

#### [ ] Subtask 7.1.1: Create report.md

**Шаблон отчёта:** `.zenflow/tasks/optimizatsiia-pk-5559/report.md`

```markdown
# Отчёт: Оптимизация Ubuntu 24.04 LTS

**Дата:** [DATE]  
**Выполнил:** [USER]

## Executive Summary

### Key Metrics

| Метрика | Before | After | Change |
|---------|--------|-------|--------|
| Disk Usage | X% | Y% | ΔZ% |
| Free Space | XGB | YGB | +ZGB |
| Docker Images | X | Y | -Z |
| Docker Volumes | X | Y | -Z |
| Journal Size | XMB | YMB | -ZMB |
| Boot Time | Xs | Ys | -Zs |

### Success Rate

- ✅ P0 Tasks: X/5 completed
- ✅ P1 Tasks: X/6 completed
- Overall: X%

## Disk Space Analysis

### Freed Space by Category

1. Docker cleanup: XGB
2. APT cache: XGB
3. Journals: XMB
4. Old kernels: XGB
5. Temporary files: XGB

**Total freed:** XGB

## Docker Optimization

### Removed Resources

- Images removed: X (freed YGB)
- Volumes removed: X (freed YGB)
- Build cache cleared: XMB

### Configuration Changes

- Log rotation enabled (max-size: 10m, max-file: 3)

## Services Optimization

### Disabled/Masked Services

1. plymouth-quit-wait.service (reason: not needed for server)
2. [list other services]

### Boot Time Improvements

- Before: Xs
- After: Ys
- Improvement: Z% faster

### Slowest Services After Optimization

[List top 5]

## Issues Encountered

### Issue 1: [Title]
- **Problem:** [description]
- **Solution:** [solution]
- **Status:** ✅ Resolved

## Recommendations

### Immediate Actions

1. [recommendation]

### Future Improvements

1. [recommendation]

## Maintenance Plan

### Automated Tasks

1. **Weekly cleanup** (disk-cleanup.timer)
   - APT cache cleanup
   - Journal rotation
   - Docker unused resources cleanup

2. **Hourly monitoring** (disk_monitor.sh)
   - Disk usage check
   - Alert on >85% usage
   - Emergency cleanup on >90%

### Manual Tasks (Monthly)

1. Review large files report
2. Check Docker images/volumes in use
3. Review system services
4. Update and reboot

## Conclusion

[Summary of results and next steps]
```

---

## Success Criteria Checklist

### ✅ Minimum Success (P0)

- [ ] Освобождено >20GB дискового пространства
- [ ] Использование диска <70%
- [ ] Docker оптимизирован (<8GB total)
- [ ] Git конфигурация исправлена (нет ошибок safe.directory)
- [ ] Система загружается без критичных ошибок

### ⚙️ Target Success (P1)

- [ ] Время загрузки уменьшено на >30%
- [ ] Автоматическая очистка настроена (systemd timer)
- [ ] Мониторинг диска работает (cron job)
- [ ] Все тесты проходят успешно
- [ ] Отчёт сгенерирован и содержит все метрики

### 🎯 Stretch Goals (P2)

- [ ] Boot time <20 секунд
- [ ] Освобождено >30GB
- [ ] Использование диска <60%
- [ ] Документация полная и детальная

---

## Timeline

| Phase | Estimated Time | Status |
|-------|---------------|--------|
| Phase 1: Preparation | 30 min | [ ] |
| Phase 2: Disk Cleanup | 1-2 hours | [ ] |
| Phase 3: Git Fix | 5-10 min | [ ] |
| Phase 4: Services Optimization | 30-60 min | [ ] |
| Phase 5: Automated Maintenance | 30-45 min | [ ] |
| Phase 6: Testing | 30-45 min | [ ] |
| Phase 7: Documentation | 15-30 min | [ ] |

**Total:** 3.5-5 hours

---

## Next Steps

1. Начать с Phase 1 (Preparation & Safety)
2. Создать backup системы
3. Запустить baseline snapshot
4. Последовательно выполнить все фазы
5. Проверить Success Criteria после каждой фазы
6. Сгенерировать итоговый отчёт
