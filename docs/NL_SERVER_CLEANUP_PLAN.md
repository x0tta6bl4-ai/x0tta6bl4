# NL Server Cleanup Plan

## Статус: NL read-only (nl_write_allowed: False)

**Мы НЕ можем** писать на NL сервер из этого кодовой базы.
**Мы МОЖЕМ** чистить локальный код и готовить скрипты для SSH.

---

## Что безопасно удалить из ЛОКАЛЬНОГО кода

### 1. Устаревшие Docker Compose файлы
```
docker-compose.minimal.yml      — симуляция mesh (не реальная сеть)
docker-compose.yml              — dev, не production
staging/docker-compose.*.y      — staging, не NL
deploy/docker-compose.*.y       — testnet, не NL
```

### 2. Дублирующие скрипты
```
scripts/run_backend.py          — дубль demo_server.py
scripts/run_demo.py             — дубль demo_server.py
scripts/run_server.sh           — дубль start-dev.sh
scripts/run_tests.sh            — дубль aggregate_tests.sh
scripts/run_all_tests.sh        — дубль aggregate_tests.sh
```

### 3. Устаревшие артефакты
```
*.db                             — SQLite databases (не в git)
*.pyc                            — bytecode
__pycache__/                     — cache
htmlcov/                         — coverage reports
.pytest_cache/                   — test cache
.ruff_cache/                     — linter cache
.mypy_cache/                     — type checker cache
```

### 4. Временные файлы
```
tmp/                             — temp files
.tmp/                            — temp files
cache/                           — cache files
output/                          — output files
results/                         — test results (дубль)
```

---

## Чего НЕ ТРОГАТЬ (production NL)

| Сервис | Статус | Причина |
|--------|--------|---------|
| **x-ui.service** | 🔴 NEVER STOP | 12+ платящих пользователей |
| **xray** | 🔴 NEVER STOP | Основной VPN |
| **warp-svc** | 🔴 NEVER STOP | Cloudflare WARP |
| **fail2ban** | 🔴 NEVER STOP | SSH protection |
| **nginx** | 🔴 NEVER STOP | Web server |
| **ghost-vpn** | ⚠️ Experimental | Не production, но работает |
| **SSH config** | 🔴 NEVER CHANGE | Can lock out |

---

## Скрипт чистки (для SSH)

Когда получим SSH доступ, запустить:

```bash
#!/bin/bash
# nl-cleanup.sh — Safe cleanup for NL server
# Run ONLY after operator approval

set -e

echo "=== NL Server Cleanup ==="

# 1. Remove deprecated Shadowsocks inbound (0 clients)
echo "Removing deprecated Shadowsocks inbound (port 34506)..."
# x-ui API call to remove inbound

# 2. Clean old logs
echo "Cleaning old logs..."
find /var/log -name "*.gz" -mtime +30 -delete 2>/dev/null
journalctl --vacuum-time=7d

# 3. Clean Docker images (if any)
docker image prune -f 2>/dev/null

# 4. Clean apt cache
apt-get clean

# 5. Remove unused packages
apt-get autoremove -y

# 6. Verify services
echo "=== Service Status ==="
systemctl is-active x-ui xray warp-svc fail2ban nginx

echo "=== Cleanup Complete ==="
```

---

## Что нужно сделать на NL после чистки

1. **Prometheus + node-exporter** — развёртывание мониторинга
2. **Go agent** — как master node mesh
3. **Security hardening** — ограничить x-ui, отключить SSH password
4. **PQC in datapath** — eBPF XDP filter
