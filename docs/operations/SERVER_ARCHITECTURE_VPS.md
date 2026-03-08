# Архитектура сервера 89.125.1.107 (x0tta6bl4 VPS)

> Документ для агентов и новых сессий. Обновлён: 2026-03-05.
> **КРИТИЧНО:** VPN на порту 39829 обслуживает реальных пользователей. Любые изменения
> в сетевом стеке (xray, x-ui, nginx, ufw, порты) требуют явного подтверждения владельца.

---

## 1. Инфраструктура

| Параметр | Значение |
|---|---|
| IP | 89.125.1.107 |
| Hostname | 01164.com |
| OS | Ubuntu 24.04.4 LTS (kernel 6.8.0-101) |
| CPU | 2 vCPU |
| RAM | 3.8 GiB (используется ~1.9 GiB) |
| Диск | 40 GB (~27 GB занято, 72%) |
| SSH | порт 22, root доступ |

---

## 2. Docker-стек (MaaS x0tta6bl4)

Compose-файл: `/opt/x0tta6bl4/docker-compose.production.yml`
Docker network: `x0tta6bl4_maas-network` (bridge)

| Контейнер | Образ | Порты (host→container) | Статус |
|---|---|---|---|
| `x0tta6bl4-control-plane-1` | `x0tta6bl4-control-plane` (local build) | `8010→8000` | healthy |
| `x0tta6bl4-db-1` | `postgres:16-alpine` | internal 5432 | healthy |
| `x0tta6bl4-redis-1` | `redis:7-alpine` | internal 6379 | running |
| `x0tta6bl4-vault-1` | `hashicorp/vault:1.15` | `8201→8200` | healthy |
| `hbbs` | `rustdesk/rustdesk-server` | 21114-21116, 21118 | running (3 days) |
| `hbbr` | `rustdesk/rustdesk-server` | 21117, 21119 | running (3 days) |

### Control Plane

- Запускается через: `uvicorn src.core.app:app --host 0.0.0.0 --port 8000`
- Исходники: `/opt/x0tta6bl4/` (НЕ git-репозиторий, код скопирован)
- Dockerfile: `Dockerfile.production`
- Python: 3.12
- Env-файл: `/opt/x0tta6bl4/.env`
- liboqs bind-mounts: `/usr/local/lib/liboqs.so*` → `/app/lib/` (ro)

### База данных (PostgreSQL 16)

- URL внутри сети: `postgresql://maas_user:maas_pass@db:5432/maas_db`
- 20 таблиц: users, mesh_instances, mesh_nodes, marketplace_listings/escrows,
  invoices, payments, sessions, governance_proposals/votes, audit_logs, и др.
- Текущая миграция alembic: `c8adf0b52d1e` (add_user_expires_at_column)
- **Примечание:** миграция `a1b2c3d4e5f6` (performance indexes) применяется только
  через `docker cp` в контейнер — не бакается в образ при rebuild.

### Vault (HashiCorp Vault 1.15)

- Storage: **file** (persistent volume `x0tta6bl4_vault_data`) — переключено с inmem
- Адрес снаружи: `http://89.125.1.107:8201`
- Адрес внутри сети: `http://vault:8200`
- Статус: initialized=true, sealed=false
- Init-файл с unseal keys: `/root/.vault-init.json` (chmod 600, только root)
- Auto-unseal: cron `@reboot` + `*/5 * * * *` → `/opt/x0tta6bl4/scripts/vault-unseal.sh`
- KV v2 engine: смонтирован на `secret/`
- **ВАЖНО:** приложение использует root token (VAULT_TOKEN в .env). Нужно создать
  policy с минимальными правами.

### Redis

- URL внутри сети: `redis://redis:6379/0`
- Персистентности нет (ephemeral). Используется как кэш.

---

## 3. VPN-стек (КРИТИЧЕСКИЙ, НЕ ТРОГАТЬ без подтверждения)

### x-ui + xray (основной VPN)

- Менеджер: **x-ui** (процесс `x-ui`, pid ~751590)
- Панель управления: порт **628** (TCP), порт **2096** (subscription)
- xray binary: `/usr/local/x-ui/bin/xray-linux-amd64`
- xray конфиг: `/usr/local/x-ui/bin/config.json`

**Inbound (пользовательский трафик):**
- Протокол: VLESS + Reality (TLS 1.3)
- Порт: **39829** (TCP + UDP, открыт в UFW)
- **Клиенты:** 33 зарегистрированных в x-ui, ~200+ одновременных TCP-соединений (у одного клиента может быть несколько)
- Dest (SNI spoof): `www.google.com:443`
- shortIds: `["6b", "97", "a1", "18e154a0558d9263", "88c2", "fb34"]`
  - `88c2` и `fb34` добавлены для обратной совместимости со старыми клиентами
- privateKey: в конфиге x-ui (НЕ публиковать)

**Inbound (dokodemo-door / внутренний):**
- Порт: **10085** (только localhost)

**ПРЕДЫСТОРИЯ:** ранее параллельно работал standalone `xray.service` на том же порту
39829 с другим конфигом (shortIds: 88c2, fb34, dest: microsoft.com). Он был остановлен
и задизейблен. Теперь только x-ui управляет xray.

---

## 4. Nginx (reverse proxy)

Конфиг: `/etc/nginx/sites-enabled/`
Порт: 80 (HTTP)

| Location | Проксируется на |
|---|---|
| `/` | статическая заглушка / лендинг |
| `/dashboard` | — |
| `/api/` | `http://127.0.0.1:8010/api/` |
| `/health` | `http://127.0.0.1:8010/health` |
| `/metrics` | `http://127.0.0.1:8010/metrics` |

---

## 5. Дополнительные Python-сервисы (нативные, не Docker)

| Процесс | Порт | Описание |
|---|---|---|
| `/opt/x0tta6bl4/run_brain_dynamic.py` | **9092** | P2P Swarm / ConsciousnessEngine, bootstrap-маяк |
| `/opt/x0tta6bl4-mesh/scripts/monitor.py` | — | мониторинг mesh |
| `/opt/x0tta6bl4-mesh/scripts/auto_monitor.py` | — | автомониторинг + авто-конфиг |
| `fail2ban-server` | — | защита от брутфорса |
| `uvicorn` (в Docker) | 8010 (внешний) | основной MaaS API |

Порт **8080** (TCP) — слушает python3 (вероятно статический сервер или второй uvicorn).
Порт **9090** (TCP) — слушает python3 (Prometheus exporter или метрики).

---

## 6. RustDesk (удалённый доступ)

Контейнеры `hbbs` + `hbbr` (rustdesk-server).

| Порт | Назначение |
|---|---|
| 21114 | API |
| 21115 | NAT test |
| 21116 TCP+UDP | rendezvous |
| 21117 | relay |
| 21118 | WebSocket |
| 21119 | WebSocket relay |

---

## 7. UFW (firewall)

Статус: **active**.
Открытые порты: 22, 80, 443, 628, 2053, 2083, 2087, 2096, 8080, 8081, 8443,
9091, 9092, 10809/10810, 21114-21119, 39829.

**Порты НЕ открытые (только внутренние):**
- 8010 (MaaS API — через nginx на /api/)
- 8201 (Vault — доступен локально, НЕ должен быть публичным)
- 5432 (PostgreSQL)
- 6379 (Redis)

**ВНИМАНИЕ:** порт 8201 (Vault) слушает на `0.0.0.0` но UFW его не блокирует явно.
Рекомендуется добавить правило `ufw deny 8201` или ограничить по IP.

---

## 8. Crontab (root)

```
@reboot  sleep 15 && /opt/x0tta6bl4/scripts/vault-unseal.sh >> /var/log/vault-unseal.log 2>&1
*/5 * * * *          /opt/x0tta6bl4/scripts/vault-unseal.sh >> /var/log/vault-unseal.log 2>&1
```

---

## 9. Ключевые пути

| Путь | Содержимое |
|---|---|
| `/opt/x0tta6bl4/` | исходники MaaS (не git) |
| `/opt/x0tta6bl4/.env` | env-переменные (DATABASE_URL, REDIS_URL, VAULT_*) |
| `/opt/x0tta6bl4/docker-compose.production.yml` | основной compose |
| `/opt/x0tta6bl4/scripts/vault-unseal.sh` | auto-unseal скрипт |
| `/opt/x0tta6bl4-mesh/scripts/` | скрипты мониторинга mesh |
| `/root/.vault-init.json` | unseal keys + root token (chmod 600) |
| `/usr/local/x-ui/bin/config.json` | xray конфиг (VPN) |
| `/var/log/vault-unseal.log` | лог авто-анпечатывания Vault |

---

## 10. MaaS API

- Base URL (внешний): `http://89.125.1.107/api/` (через nginx)
- Base URL (прямой): `http://89.125.1.107:8010`
- Docs: `http://89.125.1.107:8010/docs`
- Health: `http://89.125.1.107:8010/health/detailed`
- Версия: `3.4.0`
- Эндпоинтов: 159
- Режим: DEVELOPMENT (`X0TTA6BL4_PRODUCTION=false`)
- mTLS: отключено (`MTLS_ENABLED=false`)
- PQC: liboqs установлен, fail-closed отключён (`PQC_FAIL_CLOSED` не задан)
- Intelligence Engine: деградирован (PyTorch недоступен, fail-open)

### 10.1. API Authentication

Доступ к защищённым эндпоинтам:
1. **JWT Bearer Token** — стандарт для веб-сессий
2. **X-API-Key Header** — статический ключ, хранится в `maas_db.users.api_key` (PostgreSQL на VPS)

**ВАЖНО для агентов:** Пользователи в production — только в PostgreSQL `maas_db` (контейнер `x0tta6bl4-db-1`).
Локальный файл `x0tta6bl4_enterprise.db` (SQLite) на dev-машине `/mnt/projects/` — это тестовая база,
она НЕ связана с VPS и не влияет на работу сервера.

---

## 11. Известные проблемы / TODO

1. **Vault root token в .env** — создать policy с минимальными правами, заменить root token
2. **Vault порт 8201 публичный** — добавить `ufw deny 8201` или ограничить по IP
3. **Миграция a1b2c3d4e5f6** не бакается в образ — добавить файл в Dockerfile.production
4. **Диск 72%** — при достижении 85% начнутся проблемы, нужен мониторинг/cleanup
5. **ENVIRONMENT=development** — для продакшна переключить на production
6. **Redis без пароля** — добавить requirepass в compose

---

## 12. Правила для агентов

- **НЕ ТРОГАТЬ:** xray конфиг, x-ui, UFW правило для 39829, nginx — без явного ОК владельца
- **Перед рестартом control-plane:** убедиться что vault unsealed (`curl http://localhost:8201/v1/sys/seal-status`)
- **После rebuild образа:** заново `docker cp` миграцию a1b2c3d4e5f6 и запустить `alembic upgrade head`
- **Изменения в .env:** требуют `docker compose up -d control-plane` для применения
- **Git repo:** `/mnt/projects` на локальной машине разработки, не на VPS. На VPS код скопирован вручную.
