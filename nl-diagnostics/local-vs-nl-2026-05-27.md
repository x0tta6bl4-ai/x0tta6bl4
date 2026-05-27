# Local VPN work vs NL server state, 2026-05-27

## Короткий вывод

Локальная VPN-разработка и реальный NL-сервер сейчас не являются одной полностью синхронизированной поставкой.

Есть три разных слоя:

1. Локальный клиентский контур на этой машине: `vpn_status`, `vpn_heal`, `vpn_watchdog`, `route-bypass`.
2. Шаблонный серверный проект `x0tta6bl4-xray-vps`: полезен для health-check и старого плана установки, но не отражает реальную схему NL один-в-один.
3. Реальный NL runtime: `x-ui.service` + Xray из `/usr/local/x-ui`, Ghost VPN, Ghost Access Bot, `/opt/x0tta6bl4-mesh`, cron-аудиторы и runtime-state timers.

VPN сейчас работает и на клиентской стороне, и на NL-сервере.

Последняя read-only сверка:

```text
snapshot: nl-diagnostics/snapshots/20260527T154832Z
classification: advisory / external_network / observe
provider_status: recent_boot_gap
transport_status: advisory
current boot: 2026-05-27 14:58 UTC
NL writes: 0
```

## Локальный клиентский контур

Проверка:

```text
bash scripts/vpn_status.sh --check --no-color
Result: PASS (warnings=0)
```

Ключевые признаки:

```text
x0tta-node.service: active
x0tta-vpn-watchdog.service: active
x0tta-vpn-route-bypass.service: active
x0tta-vpn-boot-validate.timer: enabled
singbox_tun: up
SOCKS5: 127.0.0.1:10918
VPN exit IP: 89.125.1.107
FIN-WAIT-2: 0
CLOSE-WAIT: 0
```

Маршруты правильные:

```text
89.125.1.107 via 192.168.0.1 dev enp8s0
1.1.1.1 via 172.18.0.2 dev singbox_tun table 2022
```

Это значит: сам NL endpoint не загоняется обратно в туннель, а обычный трафик идёт через VPN.

Установленные локально route-bypass/watchdog файлы совпадают с локальными исходниками:

```text
scripts/apply_vpn_route_bypass.sh == /usr/local/sbin/x0tta-vpn-route-bypass
scripts/vpn_boot_validate.sh == /usr/local/sbin/x0tta-vpn-boot-validate
infra/systemd/x0tta-vpn-watchdog.service == /etc/systemd/system/x0tta-vpn-watchdog.service
infra/systemd/x0tta-vpn-route-bypass.service == /etc/systemd/system/x0tta-vpn-route-bypass.service
infra/systemd/x0tta-vpn-boot-validate.service == /etc/systemd/system/x0tta-vpn-boot-validate.service
infra/systemd/x0tta-vpn-boot-validate.timer == /etc/systemd/system/x0tta-vpn-boot-validate.timer
infra/systemd/x0tta-node-route-bypass.conf == /etc/systemd/system/x0tta-node.service.d/10-route-bypass.conf
```

Локальная отдельная проблема, не влияющая на текущий VPN PASS:

```text
ghost-access-activity-sync.service: failed
reason: service path still points at /mnt/projects/scripts/sync_xray_device_activity.py
current source has been restored under services/nl-server/ghost-access/sync_xray_device_activity.py

x0tta6bl4-ebpf-dataplane.service: failed
reason: Go build failed on VCS status; suggested fix in log: -buildvcs=false
```

## Реальный NL-сервер

Текущее состояние:

```text
hostname: 01164.com
boot: 2026-05-27 14:58 UTC
load average: low
systemctl --failed: ifup@eth0.service only
```

`ifup@eth0.service` сейчас считается предупреждением, а не причиной VPN outage:
основные сервисы active, listener ports на месте, packet loss на клиенте 0.

Активные важные сервисы:

```text
x-ui.service: active
warp-svc.service: active
ghost-vpn.service: active
ghost-tcp-bridge.service: active
ghost-access-nl-beta.service: active
nginx.service: active
docker.service: active
x0tta6bl4-profile-status-api.service: active
```

Основной Xray на NL запускается не через `xray.service`, а через `x-ui.service`:

```text
/usr/local/x-ui/x-ui
/usr/local/x-ui/bin/xray-linux-amd64.real -c bin/config.json
```

Старый `xray.service` есть, но отключён:

```text
xray.service: disabled, inactive
xray@.service: disabled
xray-probe-monitor.service: disabled, inactive
```

Слушающие порты:

```text
443/tcp      x-ui/Xray main VLESS Reality
2083/tcp     x-ui/Xray secondary VLESS Reality
39829/tcp    x-ui/Xray legacy/current client VLESS Reality
2443/tcp     ghost-access-nl-beta Xray
4433/udp     ghost-vpn
4434/tcp     ghost-tcp-bridge
51820/udp    WireGuard/WARP-related listener
8443/tcp     nginx, not x-ui/Xray
```

Runtime state на сервере:

```text
transport_health_status: advisory
subscription_health_status: healthy
warp_status: healthy
xui_service_ok: true
listener_443_ok: true
best_path: secondary / 2083
mode: degraded
reason: telegram media edges are slow from the current egress path
recommended_action: observe
```

Важно: `mode=degraded` сейчас не означает, что VPN transport сломан. В runtime-state degraded из-за Telegram media latency spread, а сами основные транспортные пути здоровы.

## Локальный `x0tta6bl4-xray-vps` vs реальный NL

Локальный шаблон `x0tta6bl4-xray-vps/configs/server-config.json` описывает:

```text
api: 10085
443 vless reality
9443 trojan reality
8443 vless splithttp tls
8388 shadowsocks
8080 vless tls
```

Реальный `/usr/local/x-ui/bin/config.json` на NL содержит:

```text
api: 62789
39829 vless reality
443 vless reality
2083 vless reality
```

Вывод: `x0tta6bl4-xray-vps` сейчас не источник истины для NL-конфига. Его `health-check.sh` уже умеет читать реальный x-ui config и поэтому полезен для диагностики, но `server-config.json` и старый install plan не совпадают с продуктивной NL-схемой.

Результат x-ui-aware health-check по SSH:

```text
Overall Status: HEALTHY
Checks Passed: 15
Checks Failed: 0
Warnings: 2
Xray service: x-ui
Xray config: /usr/local/x-ui/bin/config.json
Xray version: Xray 26.2.6
```

Warnings:

```text
Error log file not found
TLS certificate not found
```

Для Reality-only inbounds это не критично само по себе, но health-check помечает как warning.

## Серверные скрипты и локальная сверка

На NL реально используются скрипты, которые теперь частично восстановлены в
локальной source-зоне `services/nl-server/`:

```text
/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py
/opt/ghost-access-bot/current/scripts/run_vpn_delivery_canary.py
/opt/ghost-access-bot/current/scripts/xray_runtime_user_manager.py
/opt/ghost-access-bot/current/scripts/xui_client_manager.py
/opt/x0tta6bl4-mesh/scripts/rotation_timer.sh
```

Часть старых локальных копий есть только в:

```text
/mnt/projects/backup-20260410-090811/scripts/
```

Но их хеши не совпадают с текущими серверными файлами, то есть сервер ушёл вперёд или был изменён отдельно.

## Совпадающие файлы после аварийной правки

Эти два файла синхронизированы между локальным `nl-diagnostics` и NL:

```text
nl-diagnostics/proactive_auditor.py == /usr/local/bin/proactive_auditor.py
nl-diagnostics/auto-port-fallback.sh == /usr/local/bin/auto-port-fallback.sh
```

В них уже добавлена защита от restart storm:

```text
cooldown 30 минут
проверка перегруза
lock для auto-port-fallback
таймауты и логирование
```

## Практический вывод

Что считается актуальным:

```text
Клиентский контур:
/mnt/projects/scripts/vpn_status.sh
/mnt/projects/scripts/vpn_heal.sh
/mnt/projects/src/network/vpn_watchdog.py
/mnt/projects/src/network/self_healing_daemon.py
/mnt/projects/infra/systemd/x0tta-vpn-*.service|timer

Серверный runtime:
NL:/etc/systemd/system/x-ui.service
NL:/usr/local/x-ui/bin/config.json
NL:/etc/x-ui/x-ui.db
NL:/opt/x0tta6bl4-mesh/
NL:/opt/ghost-access-bot/current/
NL:/mnt/projects/src/network/ghost_vpn_*.py
```

Что устарело или не является источником истины:

```text
x0tta6bl4-xray-vps/configs/server-config.json
x0tta6bl4-xray-vps/docs/deployment-plan.md sections about standalone xray.service
локальные ghost-access исходники в текущем /mnt/projects, потому что их нет
```

## Рекомендуемые действия

1. Сделать серверный snapshot в локальный каталог, например `/mnt/projects/nl-diagnostics/server-snapshot-20260527/`, без секретов и без баз с персональными данными.
2. Разделить репозиторий на два явно документированных профиля:
   - `local-client-profile`: route-bypass, watchdog, boot validation, local xray/sing-box.
   - `nl-server-profile`: x-ui, Ghost VPN, Ghost Access Bot, x0tta6bl4-mesh timers.
3. Обновить `docs/runbooks/NL_VPN_HEALTH.md`: явно написать, что `x0tta6bl4-xray-vps/configs/server-config.json` не равен реальному NL config.
4. Убрать или восстановить локальные failed units:
   - `ghost-access-activity-sync.service`
   - `x0tta6bl4-ebpf-dataplane.service`
5. Для NL считать `runtime-state.json` и `x-ui db/config` источником истины, а не старый `xray.service`.

## Update 2026-05-27T07:27Z

Снят свежий read-only snapshot/profile:

```text
snapshot: nl-diagnostics/snapshots/20260527T072732Z
profile: nl-diagnostics/nl-server-profile/20260527T072838Z
refresh report: nl-diagnostics/nl-current-state-refresh-20260527T072732Z.md
gap report: nl-diagnostics/nl-profile-gap-analysis-20260527T072838Z.md
```

Текущий статус NL:

```text
overall_status: advisory
transport_status: advisory
telegram_media_status: degraded
failure_domain: external_network
recommended_action: observe
NL writes: 0
```

Ключевой вывод не изменился:

```text
это не текущий x-ui outage;
основные listener ports 443/2083/39829 есть;
x-ui, warp, ghost-vpn, ghost-tcp-bridge, ghost-access-nl-beta, nginx, docker active;
runtime mode на NL всё ещё degraded из-за Telegram media, а не из-за VPN transport.
```

Локально подготовлена отдельная server-source зона:

```text
services/nl-server/
```

Свежий read-only профиль NL:

```text
nl-diagnostics/nl-server-profile/20260527T173222Z
nl-diagnostics/nl-profile-gap-analysis-20260527T173222Z.md
```

На 2026-05-27 17:32 UTC NL не показывает x-ui outage: `x-ui`,
`warp-svc`, `ghost-vpn`, `ghost-tcp-bridge`, `ghost-access-nl-beta`, `nginx`
active; ports `443`, `2083`, `39829`, `2443`, `4433`, `4434` listen.
Runtime mode остается `degraded`, но reason: Telegram media edges, action:
`observe`.

Текущий gap-summary после локального review:

```json
{
  "local_name_drift": 7,
  "missing_local_source": 2,
  "redacted_review_only": 2,
  "same_hash_elsewhere": 15,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Что уже совпадает с NL по хешам:

```text
services/nl-server/mesh-runtime/build_runtime_state.py
services/nl-server/mesh-runtime/apply_config_auto.py
services/nl-server/mesh-runtime/full_stealth_config.py
services/nl-server/mesh-runtime/rotation_timer.sh
services/nl-server/mesh-runtime/listener_loss_signal.py
services/nl-server/mesh-runtime/publish_client_profile_hint.py
services/nl-server/mesh-runtime/monitor.py
services/nl-server/mesh-runtime/profile_status_api.py
services/nl-server/mesh-runtime/auto_monitor.py
services/nl-server/ghost-access/sync_xray_device_activity.py
services/nl-server/ghost-vpn/ghost_tcp_bridge.py
services/nl-server/ghost-vpn/ghost_vpn_server.py
services/nl-server/ghost-vpn/ghost_vpn_client.py
services/nl-server/ghost-access/check_bot_user_chains.py
```

Что создано как redacted template, а не raw source:

```text
services/nl-server/templates/nl-beta-2443.example.json
```

Что намеренно отличается локально:

```text
services/nl-server/mesh-runtime/vps_build_runtime_state.py
  причина: локальная semantic fix для Telegram-only degraded -> advisory/observe

services/nl-server/ghost-vpn/ghost_vpn_protocol.py
  причина: локальный fallback для import compatibility
```

Sensitive Ghost Access files:

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
```

Они существуют только как redacted review copies:

```text
raw source saved locally: false
deployable: false
```

Итог по сравнению: локальная разработка уже закрывает диагностику, статусные
семантики и часть server-source, но NL остаётся read-only и не получил локальные
исправления. Перед любым deploy нужен свежий read-only profile, backup/rollback
plan и явное разрешение на запись.

Local client healing update:

```text
src/network/vpn_watchdog.py
src/network/self_healing_daemon.py
scripts/vpn_provider_guard.py
tests/unit/network/test_vpn_health_autodetect_unit.py
tests/unit/scripts/test_vpn_provider_guard_unit.py
nl-diagnostics/local-client-healing-audit-2026-05-27.md
nl-diagnostics/local-provider-guard-audit-2026-05-27.md
```

Изменение:

```text
local heal cooldown default: 60 sec -> 1800 sec
vpn_watchdog default client port: 443 -> 39829
vpn_status --json added to local snapshot evidence
provider guard added before local heal mutation
provider guard tracks snapshot age; default max age is 3600 sec
VPN_HEAL_FORCE=1 requires fresh snapshot evidence by default
watchdog SIGTERM local xray is blocked unless VPN_WATCHDOG_ALLOW_HARD_HEAL=1
watchdog SIGTERM path requires fresh provider-guard evidence
```

Это локальное изменение. Оно не меняет NL и не включает автолечение само по себе.
Если fresh snapshot отсутствует, устарел или не классифицируется, forced heal
останавливается до `ss -K` и до `SIGHUP` local `xray`, если не задан явный
ручной override `VPN_HEAL_IGNORE_PROVIDER_GUARD=1`.
Если `SIGHUP` в watchdog не сработает, `SIGTERM` local `xray` теперь также
останется заблокированным без отдельного `VPN_WATCHDOG_ALLOW_HARD_HEAL=1`.

Provider incident packet update:

```text
fresh snapshot: nl-diagnostics/snapshots/20260527T154832Z
packet: nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T154832Z.md
packet_type: provider_watch
snapshot_stale: false
current provider state: recent_boot_gap, unclean previous boot, no confirmed active provider outage
current shutdown lines: none in selected snapshot
historical provider evidence: hypervisor initiated shutdown on 2026-05-26
current NL runtime: mode=degraded, recommended_action=observe, transport=advisory
NL writes: 0
```

Практический смысл: для провайдера теперь есть готовый локальный Markdown/JSON
пакет с короткими доказательствами. При этом текущий статус не смешивается с
историческим outage: сейчас transport healthy, свежий snapshot показывает
boot gap без явной строки `hypervisor initiated shutdown`, поэтому это
`provider_watch`, а не автоматический provider outage.

Boot gap report:

```text
nl-diagnostics/boot-gap-2026-05-27-report.md
previous boot last entry: 2026-05-27 08:53:30 UTC
current boot first entry: 2026-05-27 14:58:37 UTC
gap: 21907 seconds
current boot journal: previous journal corrupted or uncleanly shut down
```

Profile switch policy:

```text
nl-diagnostics/profile-switch-policy-2026-05-27.md
switch_profile is advisory, not automatic
automatic_allowed=false
fresh snapshot required before manual review
NL writes: 0
```
