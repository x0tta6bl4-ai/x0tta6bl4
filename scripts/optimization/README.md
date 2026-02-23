# Ubuntu System Optimization Scripts

Набор скриптов для оптимизации Ubuntu 24.04 LTS

## 🚨 КРИТИЧНО: Диск заполнен на 100%!

**Текущее состояние:**
- Использование диска: **100%** (101GB из 107GB)
- Доступно: **23MB** (критично!)
- Docker занимает: **~15GB**

## ⚡ Быстрая Очистка (СРОЧНО!)

```bash
# Запустите эту команду для немедленного освобождения места:
sudo ./scripts/optimization/quick_cleanup.sh
```

Эта команда:
- Очистит Docker (освободит ~10-12GB)
- Очистит APT кэш (освободит ~1-2GB)
- Очистит журналы (освободит ~400MB)
- Очистит temporary файлы

**Ожидаемый результат:** Освобождение 12-15GB места

---

## 📁 Структура Скриптов

### Основные Скрипты

| Скрипт | Описание | Требует sudo |
|--------|----------|--------------|
| `master_optimizer.sh` | Главный оркестратор (запускает всё) | ✅ |
| `quick_cleanup.sh` | **Быстрая критичная очистка** | ✅ |
| `system_analyzer.sh` | Анализ системы и сравнение snapshots | ❌ |
| `git_fix.sh` | Исправление git safe.directory | ❌ |
| `docker_optimizer.sh` | Оптимизация Docker | ✅ |
| `disk_cleanup.sh` | Очистка диска | ✅ |
| `services_optimizer.sh` | Оптимизация systemd сервисов | ✅ |
| `automated_maintenance.sh` | Настройка автоматизации | ✅ |

---

## 🎯 Использование

### 1. Анализ Системы (без изменений)

```bash
# Создать snapshot текущего состояния
./scripts/optimization/system_analyzer.sh --snapshot before

# Посмотреть список всех snapshots
./scripts/optimization/system_analyzer.sh --list

# Анализ без запуска оптимизаций
sudo ./scripts/optimization/master_optimizer.sh --analyze
```

### 2. Критичные Оптимизации (P0)

```bash
# Запустить только критичные оптимизации
sudo ./scripts/optimization/master_optimizer.sh --p0

# С автоподтверждением (для автоматизации)
sudo ./scripts/optimization/master_optimizer.sh --p0 --yes

# Dry-run (показать что будет сделано)
sudo ./scripts/optimization/master_optimizer.sh --p0 --dry-run
```

**P0 включает:**
- Очистку Docker
- Очистку APT кэша
- Очистку журналов
- Удаление старых ядер
- Исправление git конфигурации

### 3. Оптимизация Производительности (P1)

```bash
# Запустить оптимизации производительности
sudo ./scripts/optimization/master_optimizer.sh --p1
```

**P1 включает:**
- Отключение медленных systemd сервисов
- Оптимизацию времени загрузки
- Настройку Docker log rotation

### 4. Полная Оптимизация

```bash
# Запустить всё (P0 + P1)
sudo ./scripts/optimization/master_optimizer.sh --all --yes
```

### 5. Настройка Автоматизации

```bash
# Настроить автоматическую еженедельную очистку
sudo ./scripts/optimization/master_optimizer.sh --setup-automation

# Или вручную
sudo ./scripts/optimization/automated_maintenance.sh --setup-timers
sudo ./scripts/optimization/automated_maintenance.sh --setup-monitor
```

---

## 📊 Индивидуальные Скрипты

### Docker Optimization

```bash
# Анализ Docker без изменений
./scripts/optimization/docker_optimizer.sh --analyze

# Очистка images
sudo ./scripts/optimization/docker_optimizer.sh --clean-images

# Очистка volumes
sudo ./scripts/optimization/docker_optimizer.sh --clean-volumes

# Полная очистка (ДЕСТРУКТИВНО!)
sudo ./scripts/optimization/docker_optimizer.sh --prune-all --yes

# Настройка log rotation
sudo ./scripts/optimization/docker_optimizer.sh --setup-log-rotation
```

### Disk Cleanup

```bash
# Анализ диска
./scripts/optimization/disk_cleanup.sh --analyze

# Очистка APT кэша
sudo ./scripts/optimization/disk_cleanup.sh --apt-cache

# Очистка журналов
sudo ./scripts/optimization/disk_cleanup.sh --journal

# Удаление старых ядер
sudo ./scripts/optimization/disk_cleanup.sh --old-kernels

# Всё сразу
sudo ./scripts/optimization/disk_cleanup.sh --all --yes
```

### Services Optimization

```bash
# Анализ времени загрузки
./scripts/optimization/services_optimizer.sh --analyze

# Оптимизация загрузки
sudo ./scripts/optimization/services_optimizer.sh --optimize-boot

# Отключение Plymouth (boot splash)
sudo ./scripts/optimization/services_optimizer.sh --disable-plymouth

# Всё сразу
sudo ./scripts/optimization/services_optimizer.sh --all --yes
```

### Git Fix

```bash
# Автоматически найти и исправить все репозитории
./scripts/optimization/git_fix.sh --auto

# Добавить конкретный репозиторий
./scripts/optimization/git_fix.sh --add /path/to/repo

# Показать все safe.directory записи
./scripts/optimization/git_fix.sh --list
```

---

## 📈 Сравнение Результатов

```bash
# Создать snapshot ДО оптимизации
./scripts/optimization/system_analyzer.sh --snapshot before

# ... выполнить оптимизации ...

# Создать snapshot ПОСЛЕ оптимизации
./scripts/optimization/system_analyzer.sh --snapshot after

# Сравнить результаты
./scripts/optimization/system_analyzer.sh --compare before after
```

---

## 🔄 Автоматизация

### Systemd Timers (рекомендуется)

```bash
# Установить timers
sudo ./scripts/optimization/automated_maintenance.sh --setup-timers

# Проверить статус
sudo systemctl list-timers disk-cleanup.timer docker-cleanup.timer

# Удалить timers
sudo ./scripts/optimization/automated_maintenance.sh --remove-timers
```

### Cron Jobs (альтернатива)

```bash
# Установить cron jobs
sudo ./scripts/optimization/automated_maintenance.sh --setup-cron

# Посмотреть установленные cron jobs
cat /etc/cron.d/system-optimization

# Удалить cron jobs
sudo ./scripts/optimization/automated_maintenance.sh --remove-cron
```

---

## 🎯 Целевые Метрики

| Метрика | До | Цель | Метод проверки |
|---------|----|----|----------------|
| Использование диска | 100% | <70% | `df -h /` |
| Свободное место | 23MB | >30GB | `df -h /` |
| Docker images | 12 | <5 | `docker images` |
| Docker volumes | 29 | <10 | `docker volume ls` |
| Журналы | 487MB | <100MB | `journalctl --disk-usage` |
| Время загрузки | ~35s | <20s | `systemd-analyze time` |

---

## ⚠️ Предупреждения

1. **Всегда создавайте backup перед запуском:**
   ```bash
   # Если установлен Timeshift
   sudo timeshift --create --comments "Before optimization"
   
   # Или хотя бы snapshot
   ./scripts/optimization/system_analyzer.sh --snapshot before
   ```

2. **Docker cleanup удалит неиспользуемые images и volumes!**
   - Используйте `--dry-run` для проверки
   - Убедитесь что нет важных данных в volumes

3. **После оптимизации сервисов требуется перезагрузка:**
   ```bash
   sudo reboot
   ```

4. **Проверьте результаты после перезагрузки:**
   ```bash
   systemd-analyze time
   df -h /
   ```

---

## 📝 Логи

Все операции логируются в:
```
~/optimization.log
```

Просмотр логов:
```bash
tail -f ~/optimization.log
```

---

## 🆘 Помощь

Для каждого скрипта доступна встроенная помощь:

```bash
./scripts/optimization/master_optimizer.sh --help
./scripts/optimization/docker_optimizer.sh --help
./scripts/optimization/disk_cleanup.sh --help
# и т.д.
```

---

## 📊 Пример Полного Workflow

```bash
# 1. Анализ текущего состояния
./scripts/optimization/system_analyzer.sh --snapshot before
sudo ./scripts/optimization/master_optimizer.sh --analyze

# 2. Критичная очистка (СРОЧНО при 100% диске!)
sudo ./scripts/optimization/quick_cleanup.sh

# 3. Полная оптимизация
sudo ./scripts/optimization/master_optimizer.sh --all --yes

# 4. Snapshot после оптимизации
./scripts/optimization/system_analyzer.sh --snapshot after

# 5. Сравнение результатов
./scripts/optimization/system_analyzer.sh --compare before after

# 6. Настройка автоматизации
sudo ./scripts/optimization/master_optimizer.sh --setup-automation

# 7. Перезагрузка
sudo reboot

# 8. Проверка после перезагрузки
systemd-analyze time
df -h /
```

---

## ✅ Критерии Успеха

Оптимизация считается успешной если:

- ✅ Использование диска < 70%
- ✅ Доступно > 30GB свободного места
- ✅ Docker images < 5
- ✅ Docker volumes < 10
- ✅ Журналы < 100MB
- ✅ Время загрузки < 20s
- ✅ Git репозитории работают без ошибок
- ✅ Система загружается без критичных ошибок

---

**Версия:** 1.0  
**Дата:** 24 января 2026  
**Совместимость:** Ubuntu 24.04 LTS
