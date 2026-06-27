# NL Source Reconciliation Plan, 2026-05-27

## Статус

Этот план построен из локального sanitized профиля:

```text
nl-diagnostics/nl-server-profile/latest
```

NL не изменялся. Gap-analysis читал только локальный профиль и локальный workspace.

Отчёты:

```text
nl-diagnostics/nl-profile-gap-analysis-2026-05-27.md
nl-diagnostics/nl-profile-gap-analysis-2026-05-27.json
```

## Главный вывод

Реальный NL runtime сейчас не представлен в локальном workspace как нормальный source-of-truth.

Summary:

```json
{
  "local_name_drift": 6,
  "missing_local_source": 19,
  "same_hash_elsewhere": 1,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Это означает:

- 19 текущих NL runtime-файлов отсутствуют локально;
- 6 файлов имеют старые одноимённые локальные backup-копии, но хеши отличаются;
- 1 файл совпадает только в старом backup;
- 4 x-ui артефакта являются runtime binary/db/config и не должны становиться обычными repo source файлами.

## Приоритеты reconciliation

### P0. Не трогать NL

До отдельной команды:

```text
no scp to NL
no systemctl on NL except read-only status/list/cat
no sqlite write
no x-ui restart
no cron/timer changes
```

Разрешено:

```text
scp/cat/ssh read from NL only if output is sanitized locally before saving as source
hash/metadata/profile summaries
local docs/tests/scripts
```

### P1. Repo ownership map

Создать локальную структуру ownership, например:

```text
nl-diagnostics/reconciliation/
  manifest.json
  server-only.md
  source-candidates.md
```

Назначение:

- какие файлы должны вернуться в repo как source;
- какие файлы являются server runtime artifact;
- какие файлы являются backup/forensics only;
- какие файлы требуют redaction или ручного review.

### P2. Вернуть source для read-only observability

Сначала вернуть или реконструировать только observability/control-plane source, не меняющий NL:

```text
/opt/x0tta6bl4-mesh/scripts/build_runtime_state.py
/opt/x0tta6bl4-mesh/scripts/listener_loss_signal.py
/opt/x0tta6bl4-mesh/scripts/publish_client_profile_hint.py
/opt/x0tta6bl4-mesh/scripts/health_check.sh
/opt/ghost-access-bot/current/scripts/run_vpn_delivery_canary.py
/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py
/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py
/opt/ghost-access-bot/current/scripts/xray_runtime_user_manager.py
/opt/ghost-access-bot/current/scripts/xui_client_manager.py
```

Reason:

Эти файлы объясняют текущие статусы, canary checks, x-ui user/runtime sync и runtime-state. Без них локальная диагностика не может быть полностью проверяемой.

Current local result:

```text
sync_xray_device_activity.py is now promoted to services/nl-server/ghost-access/
build_runtime_state.py, listener_loss_signal.py and publish_client_profile_hint.py are already promoted to services/nl-server/mesh-runtime/
```

### P3. Вернуть Ghost VPN source отдельно

Текущие NL файлы отсутствуют локально:

```text
/mnt/projects/src/network/ghost_vpn_server.py
/mnt/projects/src/network/ghost_vpn_client.py
/mnt/projects/src/network/ghost_vpn_protocol.py
/mnt/projects/scripts/ghost_tcp_bridge.py
```

Действие:

- читать с NL только в локальную quarantine-директорию;
- проверить на секреты;
- только потом переносить в repo source area;
- добавить тест запуска/import без поднятия реального сервиса.

Current local result:

```text
ghost_vpn_protocol.py is promoted with an intentional local import fallback
ghost_tcp_bridge.py is now promoted to services/nl-server/ghost-vpn/
ghost_vpn_server.py and ghost_vpn_client.py are now promoted as local source only
ghost_vpn_server.py and ghost_vpn_client.py remain class C/not deployable until mutation gates exist
```

### P4. Сконвертировать sensitive config в template

Не сохранять как production config:

```text
/etc/ghost-access/nl-beta-2443.json
/usr/local/x-ui/bin/config.json
/etc/x-ui/x-ui.db
```

Вместо этого сделать:

```text
templates/nl/nl-beta-2443.example.json
templates/nl/x-ui-config-shape.example.json
docs/runbooks/x-ui-db-backup-and-restore.md
```

Правило:

Никаких UUID, private/public keys, shortId, passwords, subscription URLs.

### P5. Server runtime artifacts remain runtime-only

Не переносить в repo как source:

```text
/usr/local/x-ui/x-ui
/usr/local/x-ui/bin/xray-linux-amd64.real
/usr/local/x-ui/bin/config.json
/etc/x-ui/x-ui.db
```

Для них достаточно:

```text
sha256
size
mtime
version
backup/rollback procedure before future writes
```

## Drift notes

Локальные backup-копии есть, но не равны текущему NL:

```text
backup-20260410-090811/scripts/check_bot_user_chains.py
backup-20260410-090811/scripts/run_vpn_delivery_canary.py
backup-20260410-090811/scripts/run_vpn_service_access_agent.py
backup-20260410-090811/scripts/xray_runtime_user_manager.py
backup-20260410-090811/scripts/xui_client_manager.py
backup-20260410-090811/scripts/health_check.sh
```

Совпадает только:

```text
backup-20260410-090811/scripts/run_telegram_bot_simple.sh
```

Вывод:

Старый backup нельзя считать актуальным source-of-truth. Он полезен только как история.

## Proposed local source layout

Рекомендуемая структура после ручного review:

```text
services/nl-server/
  README.md
  systemd/
    README.md
  mesh-runtime/
    build_runtime_state.py
    listener_loss_signal.py
    publish_client_profile_hint.py
    health_check.sh
  ghost-access/
    run_vpn_delivery_canary.py
    run_vpn_service_access_agent.py
    sync_xray_device_activity.py
    xray_runtime_user_manager.py
    xui_client_manager.py
  ghost-vpn/
    ghost_vpn_server.py
    ghost_vpn_client.py
    ghost_vpn_protocol.py
    ghost_tcp_bridge.py
  templates/
    nl-beta-2443.example.json
```

Почему не класть сразу в существующие `scripts/` и `src/network/`:

- текущий workspace уже содержит старые или отсутствующие пути;
- нужен review перед смешиванием production server-only code с local-client code;
- безопаснее сначала завести isolated source area и тесты.

## Current local source area

Создана локальная зона:

```text
services/nl-server/
  README.md
  manifest.json
  tools/pull_candidate_readonly.py
  .quarantine/README.md
  systemd/README.md
  mesh-runtime/README.md
  ghost-access/README.md
  ghost-vpn/README.md
  templates/README.md
```

Текущий статус:

```text
status: planning_only
NL write permission: false
local reviewed source promoted: 16 files
deployable to NL: false
manifest JSON validation: OK
quarantine tool dry-run: OK
redacted review status recognized by gap analyzer: OK
secret scan: only policy wording/path names, no real secret payloads
```

`manifest.json` связывает sanitized profile и gap-analysis с будущими локальными
путями для review. Это не deploy-manifest и не разрешение на запись в NL.

Sensitive Ghost Access files are tracked separately as redacted review material:

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
nl-diagnostics/nl-redacted-source-review-2026-05-27.md
nl-diagnostics/nl-ghost-access-ownership-map-2026-05-27.md
```

These files are not deployable. They exist only to map bot/control-plane
structure without storing raw VPN links, UUIDs, keys, or tokens locally.

Dry-run команда:

```bash
python3 services/nl-server/tools/pull_candidate_readonly.py --priority P1
```

Она сейчас показывает 13 P1-кандидатов и не читает NL без явного `--pull`.

P1 intake выполнен в локальную quarantine-зону:

```text
services/nl-server/.quarantine/incoming/20260527T055602Z
nl-diagnostics/nl-p1-quarantine-intake-2026-05-27.md
```

Результат:

```text
accepted: 13
blocked: 0
NL writes: 0
promoted to local source: partial
```

P2 intake выполнен тем же read-only способом:

```text
services/nl-server/.quarantine/incoming/20260527T060043Z
nl-diagnostics/nl-p2-quarantine-intake-2026-05-27.md
nl-diagnostics/nl-source-promotion-matrix-2026-05-27.md
```

Результат:

```text
accepted: 10
blocked: 2
NL writes: 0
promoted to local source: partial
```

Заблокированные файлы не сохранены как raw source, потому что в них найден
URI-шаблон. После этого они были обработаны отдельной redaction-процедурой:

```text
raw source saved locally: false
redacted review copies: present
deployable: false
```

Локально promoted:

```text
services/nl-server/mesh-runtime/build_runtime_state.py
services/nl-server/mesh-runtime/vps_build_runtime_state.py
services/nl-server/mesh-runtime/profile_status_api.py
services/nl-server/mesh-runtime/monitor.py
services/nl-server/ghost-access/check_bot_user_chains.py
services/nl-server/ghost-vpn/ghost_vpn_protocol.py
```

`vps_build_runtime_state.py` уже локально исправлен и покрыт тестами:

```text
python3 services/nl-server/tests/test_vps_build_runtime_state.py
Ran 7 tests: OK
python3 services/nl-server/tests/test_profile_status_and_ghost_protocol.py
Ran 6 tests: OK
python3 services/nl-server/tests/test_health_action_policy.py
Ran 6 tests: OK
python3 nl-diagnostics/test_analyze_nl_profile_gaps.py
Ran 1 test: OK
python3 services/nl-server/tools/validate_preflight_readiness.py
ok=true, deploy_status=local_ready_but_deploy_blocked
```

Следующий безопасный шаг:

```text
1. подготовить deploy preflight checklist для shell split;
2. перед любым deploy заново снять read-only profile и сравнить hash с NL;
3. только после явного approval готовить backup/rollback plan.
```

## Fresh profile refresh

Latest read-only profile:

```text
nl-diagnostics/nl-server-profile/20260527T173222Z
nl-diagnostics/nl-profile-gap-analysis-20260527T173222Z.md
nl-diagnostics/nl-current-state-refresh-20260527T072732Z.md
```

Fresh gap summary:

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

Interpretation:

```text
Several promoted files now match NL exactly.
listener_loss_signal.py, publish_client_profile_hint.py, auto_monitor.py, apply_config_auto.py, full_stealth_config.py, rotation_timer.sh, sync_xray_device_activity.py, ghost_tcp_bridge.py, ghost_vpn_server.py and ghost_vpn_client.py have now been promoted locally.
nl-beta-2443 has a redacted example template only; raw production config remains intentionally unsaved.
Two intentionally changed local files show as drift and are not deploy-ready:
services/nl-server/mesh-runtime/vps_build_runtime_state.py
services/nl-server/ghost-vpn/ghost_vpn_protocol.py
Two sensitive Ghost Access files now have redacted review copies only, not deployable source.
NL current boot also shows a recent boot gap and unclean previous shutdown.
```

## Redacted source review

Remaining gap risk details are tracked in:

```text
nl-diagnostics/nl-remaining-source-gap-risk-2026-05-27.md
```

The two previously blocked Ghost Access files now have redacted local review
copies:

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
nl-diagnostics/nl-redacted-source-review-2026-05-27.md
```

These are not deployable. Raw source was not saved locally.

## Acceptance gates before any NL write

Любое будущее изменение NL допустимо только после:

```text
fresh read-only nl-server-profile
fresh vpn snapshot classification
source hash comparison against intended deploy files
x-ui db backup command prepared
x-ui generated config backup command prepared
rollback command prepared
operator approval
maintenance window accepted
```

Для текущей фазы:

```text
NL write permission: false
remote mutation allowed: false
recommended action: continue local reconciliation
```
