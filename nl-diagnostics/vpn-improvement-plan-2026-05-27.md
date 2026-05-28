# VPN improvement plan, 2026-05-27

## Статус

NL-сервер в этой фазе только read-only. План ниже не требует изменений на NL до отдельной явной команды.

Fresh execution plan:

```text
nl-diagnostics/nl-vpn-improvement-execution-plan-2026-05-27.md
```

Текущий VPN работает:

```text
local vpn_status: PASS, warnings=0
NL systemctl --failed: ifup@eth0.service only
NL x-ui: active
NL warp-svc: active
NL ghost-vpn: active
NL transport: listener 443/2083/39829 ok
NL provider_status: recent_boot_gap
```

Главная проблема не в текущей доступности, а в управляемости:

- локальный client-контур и NL server-контур развивались отдельно;
- локальный `x0tta6bl4-xray-vps/configs/server-config.json` не совпадает с реальным NL `x-ui` config;
- часть живых серверных скриптов есть только на NL;
- `degraded` в NL runtime-state сейчас смешивает разные смыслы: transport может быть healthy/advisory, но общий mode degraded из-за Telegram media latency;
- сегодня найден новый boot gap: предыдущий boot оборвался `2026-05-27 08:53:30 UTC`, текущий начался `2026-05-27 14:58:37 UTC`, текущий journal пишет `uncleanly shut down`;
- автолечение есть в нескольких местах, но включать его опасно без единой политики и dry-run gates.

## Ограничение

До команды на изменение NL:

```text
Разрешено:
- read-only SSH команды;
- чтение systemd, runtime-state, sqlite -readonly, ss, journalctl, df/free/sar;
- локальные документы, локальные проверки, локальные скрипты;
- локальные snapshot-отчёты без секретов.

Запрещено:
- systemctl restart/enable/disable на NL;
- запись в /etc, /usr/local, /opt, /var на NL;
- запуск health-check скриптов, которые пишут report на NL;
- scp на NL;
- изменение x-ui db/config.
```

## Текущая архитектура

### Локальный client contour

Источник истины:

```text
/mnt/projects/scripts/vpn_status.sh
/mnt/projects/scripts/vpn_heal.sh
/mnt/projects/src/network/vpn_watchdog.py
/mnt/projects/src/network/self_healing_daemon.py
/mnt/projects/scripts/apply_vpn_route_bypass.sh
/mnt/projects/scripts/vpn_boot_validate.sh
/mnt/projects/infra/systemd/x0tta-vpn-*.service|timer
```

Текущие факты:

```text
x0tta-node.service: active
x0tta-vpn-watchdog.service: active
x0tta-vpn-route-bypass.service: active
x0tta-vpn-boot-validate.timer: active/enabled
xray.service: active locally
VPN endpoint route: 89.125.1.107 via LAN gateway, not singbox_tun
Generic route: 1.1.1.1 via singbox_tun
watchdog heal: disabled
watchdog heals: 0
```

### NL server contour

Источник истины:

```text
NL:/etc/systemd/system/x-ui.service
NL:/usr/local/x-ui/bin/config.json
NL:/etc/x-ui/x-ui.db
NL:/opt/x0tta6bl4-mesh/state/runtime-state.json
NL:/opt/x0tta6bl4-mesh/scripts/
NL:/opt/ghost-access-bot/current/
NL:/mnt/projects/src/network/ghost_vpn_*.py
```

Текущие факты:

```text
x-ui.service: active
warp-svc.service: active
ghost-vpn.service: active
ghost-tcp-bridge.service: active
ghost-access-nl-beta.service: active
nginx.service: active
docker.service: active
systemctl --failed: ifup@eth0.service only
```

Порты:

```text
443/tcp    x-ui/Xray VLESS Reality
2083/tcp   x-ui/Xray VLESS Reality
39829/tcp  x-ui/Xray VLESS Reality, текущий локальный клиент
2443/tcp   ghost-access-nl-beta
4433/udp   ghost-vpn
4434/tcp   ghost-tcp-bridge
51820/udp  WARP/WireGuard-related
8443/tcp   nginx, не x-ui/Xray
62789/tcp  Xray API, localhost only
```

Runtime-state:

```text
mode: degraded
reason: telegram media edges are slow from the current egress path
transport path main/443: healthy
transport path secondary/2083: healthy
subscription health: healthy
warp: healthy
ghost: ready
recommended action: observe
```

Provider/boot evidence:

```text
previous boot last entry: 2026-05-27 08:53:30 UTC
current boot first entry: 2026-05-27 14:58:37 UTC
gap: 21907 seconds
current boot journal: previous journal corrupted or uncleanly shut down
no current explicit "hypervisor initiated shutdown" line found
```

### Drift между шаблоном и реальностью

Локальный `x0tta6bl4-xray-vps/configs/server-config.json`:

```text
api 10085
443 vless reality
9443 trojan reality
8443 vless splithttp tls
8388 shadowsocks
8080 vless tls
```

Реальный NL:

```text
api 62789
39829 vless reality
443 vless reality
2083 vless reality
2443 separate nl-beta xray config
```

Вывод: `x0tta6bl4-xray-vps` можно использовать как диагностический toolkit, но не как production source of truth для NL.

## Целевая модель

Цель: сделать VPN предсказуемым, проверяемым и устойчивым к трём разным классам отказов.

Классы отказов:

1. Local client failure:
   - `singbox_tun` не поднят;
   - local xray/v2rayN/socks не отвечает;
   - route loop до `89.125.1.107`;
   - stale TCP states `FIN-WAIT-2` / `CLOSE-WAIT`.
2. NL service failure:
   - `x-ui` не active;
   - listener `443/2083/39829` пропал;
   - WARP сломан;
   - Ghost VPN/bridge сломан;
   - subscription/canary checks failing.
3. Provider/host failure:
   - high CPU steal;
   - disk await spike;
   - abrupt hypervisor shutdown;
   - server unreachable from outside.

Нужное состояние:

```text
health_state: ok | advisory | degraded | critical | provider_outage
failure_domain: local_client | nl_service | provider_host | external_network | unknown
recommended_action: observe | local_heal | operator_review | provider_ticket | failover
mutation_allowed: false by default
```

## План работ

### P0. Read-only stabilization and source-of-truth map

Цель: убрать путаницу без изменения NL.

Работы:

1. Зафиксировать локальный read-only inventory script:
   - локально запускает SSH read-only команды;
   - читает `runtime-state.json`, `x-ui db`, systemd, timers, listeners;
   - пишет результат только локально в `nl-diagnostics/snapshots/`.
2. Сформировать sanitized snapshot текущего NL:
   - без UUID, private keys, subscription links, bot tokens;
   - с хешами файлов и списком systemd units.
3. Обновить локальную документацию:
   - `x0tta6bl4-xray-vps` = toolkit/template, не production truth;
   - production truth = NL `x-ui db/config` + `/opt/x0tta6bl4-mesh` + `/opt/ghost-access-bot/current`.
4. Завести локальный `vpn-state-contract.md`:
   - что означает `ok`, `advisory`, `degraded`, `critical`, `provider_outage`;
   - какие checks входят в каждый статус.

Acceptance:

```text
read-only snapshot создаётся локально;
в snapshot нет секретов;
документ явно различает local-client-profile и nl-server-profile;
нет команд записи на NL.
```

### P1. Health semantics cleanup

Цель: `degraded` больше не должен пугать, если transport healthy.

Работы:

1. Разделить статусы:
   - `transport_status`;
   - `application_status`;
   - `telegram_media_status`;
   - `provider_status`;
   - `overall_status`.
2. Для локального `vpn_status.sh` показывать не только PASS/FAIL, но и failure domain:
   - local route;
   - local socks;
   - NL reachability;
   - NL runtime advisory.
3. В read-only reporter добавить правило:
   - если `transport healthy/advisory`, `x-ui active`, listener ok, packet loss 0, то итог не critical;
   - Telegram media latency становится `advisory`, а не VPN outage.
4. Добавить локальные тестовые fixtures с примерами `runtime-state.json`.

Acceptance:

```text
Telegram-only degradation не классифицируется как VPN outage;
provider/hypervisor outage классифицируется отдельно;
vpn_status output даёт понятное "что делать дальше".
vpn_status --json выдаёт state-contract поля для evidence bundle.
```

### P2. Observability and local evidence

Цель: быстро отвечать на вопрос "что именно не работает".

Работы:

1. Единый локальный evidence bundle:
   - `vpn_status`;
   - watchdog metrics;
   - route checks;
   - NL read-only runtime-state;
   - NL listeners and active services;
   - last boot and failed units;
   - provider symptoms: steal/load/disk await if `sar` exists.
2. Локальный lightweight dashboard или markdown status:
   - current status;
   - last good;
   - last provider incident;
   - current recommended action.
3. Добавить пороги:
   - packet loss critical;
   - high latency advisory/critical;
   - CPU steal on NL advisory/critical;
   - disk await advisory/critical;
   - missing listener critical.
4. Сделать команды copy-paste safe:
   - никакой записи на NL;
   - `sqlite3 -readonly`;
   - `journalctl` only;
   - `ssh -o BatchMode=yes`.

Acceptance:

```text
одна команда локально создаёт evidence bundle;
bundle объясняет failure domain;
bundle можно отправить провайдеру без секретов.
```

### P3. Safe healing policy

Цель: автолечение не должно превращать деградацию провайдера в restart storm.

Текущий риск:

```text
vpn_watchdog.py HEAL_COOLDOWN_SEC = 60
self_healing_daemon.py _HEAL_COOLDOWN = 60
NL proactive_auditor/auto-port-fallback уже исправлены на 1800 sec cooldown
```

Работы:

1. Унифицировать cooldown policy:
   - local gentle action cooldown: 5 min;
   - local destructive action cooldown: 30 min;
   - NL service restart cooldown: 30 min minimum.
2. Добавить dry-run/preflight в локальные heal-команды:
   - показать planned actions;
   - требовать `VPN_HEAL_FORCE=1` для reload;
   - не делать SIGTERM без отдельного флага.
3. Разделить действия:
   - `observe`: только метрики;
   - `local_soft_heal`: route refresh, socks detection, maybe SIGHUP local xray;
   - `local_hard_heal`: SIGTERM local xray;
   - `remote_soft_heal`: пока forbidden;
   - `remote_restart`: forbidden until explicit NL write permission.
4. Добавить "provider guard":
   - если NL steal/load/disk wait high, не рестартовать сервисы;
   - recommended action = provider_ticket / observe / failover.
5. Требовать свежий read-only snapshot перед forced heal:
   - обычный guard предупреждает о старом snapshot;
   - `VPN_HEAL_FORCE=1` по умолчанию добавляет `--require-fresh`;
   - stale/missing/unknown snapshot блокирует до `ss -K`/SIGHUP.

Acceptance:

```text
активное лечение по умолчанию выключено;
heal dry-run показывает действия без выполнения;
provider degradation блокирует restart policy;
forced heal не использует старые NL/provider evidence;
документирован откат.
```

### P4. Config and code reconciliation

Цель: локальные разработки снова должны соответствовать тому, что реально живёт на NL.

Read-only фаза:

1. Создать локальный sanitized mirror структуры:
   - systemd units без секретов;
   - `x-ui` inbound summary;
   - `/opt/x0tta6bl4-mesh/scripts` хеши и безопасные summary;
   - `/opt/ghost-access-bot/current/scripts` хеши и безопасные summary.
2. Определить ownership:
   - что принадлежит local client;
   - что принадлежит NL server;
   - что является deprecated template.
3. Подготовить migration plan:
   - куда вернуть отсутствующие локальные server scripts;
   - какие тесты нужны перед любым deploy;
   - как сравнивать production hash с repo hash.

После разрешения на запись NL:

1. Сначала только deploy read-only-friendly scripts.
2. Потом systemd changes через staged rollout.
3. Потом x-ui changes только после backup db/config and rollback command.

Acceptance:

```text
есть локальный профиль nl-server-profile;
устаревший server-config не используется как production config;
для каждого production script есть repo source или явная пометка "server-only".
```

### P5. Failover and provider resilience

Цель: падение хоста провайдера больше не должно означать долгий простой.

Работы:

1. Подготовить второй exit node:
   - другой провайдер;
   - другой регион;
   - минимальный x-ui/VLESS Reality профиль;
   - отдельный health endpoint.
2. Клиентская failover-логика:
   - primary NL `39829/443/2083`;
   - secondary node;
   - ручной switch first, automatic later.
3. Provider incident automation:
   - если гипервизор shutdown или high steal/disk await, собрать ticket text;
   - хранить incident timeline локально.
4. Subscription/profile strategy:
   - один стабильный profile для daily use;
   - один emergency profile;
   - не смешивать canary/advisory paths с daily path.

Acceptance:

```text
есть второй маршрут;
есть ручной переключатель;
provider outage классифицируется за минуты, а не после ручной расшифровки журналов.
```

### P6. Security and leak controls

Цель: улучшать устойчивость без утечки ключей и без случайной публикации секретов.

Работы:

1. Secret hygiene:
   - snapshot redaction;
   - no tokens in reports;
   - no private keys in git.
2. Local leak checks:
   - exit IP expected;
   - DNS route expected;
   - WebRTC guidance as separate client hardening.
3. NL exposure review, read-only:
   - public listeners vs intended public listeners;
   - localhost-only API;
   - management UI path and port summary without secrets.
4. Backup policy:
   - x-ui db/config backup before any future write;
   - restore command documented, not executed in read-only phase.

Acceptance:

```text
reports are safe to share;
API remains localhost-only;
public ports are intentional and documented.
```

## Immediate next steps while NL is read-only

1. Build local read-only snapshot command.
2. Add local `vpn-state-contract.md`.
3. Update `docs/runbooks/NL_VPN_HEALTH.md` with:
   - local-client-profile;
   - nl-server-profile;
   - degraded/advisory distinction;
   - explicit "do not use standalone xray.service as NL truth".
4. Add tests for status classification using sample runtime-state JSON.
5. Prepare provider-outage classifier from the 2026-05-26 incident data.

## Progress 2026-05-27

Done locally, without changing NL:

```text
nl-diagnostics/collect_vpn_readonly_snapshot.sh
nl-diagnostics/classify_vpn_snapshot.py
nl-diagnostics/test_classify_vpn_snapshot.py
nl-diagnostics/vpn-state-contract-2026-05-27.md
docs/runbooks/NL_VPN_HEALTH.md updated with read-only snapshot flow
```

Validation:

```text
python3 nl-diagnostics/test_classify_vpn_snapshot.py
Ran 6 tests: OK

bash -n nl-diagnostics/collect_vpn_readonly_snapshot.sh
python3 -m py_compile nl-diagnostics/classify_vpn_snapshot.py nl-diagnostics/test_classify_vpn_snapshot.py
OK
```

Latest read-only snapshot:

```text
nl-diagnostics/snapshots/20260527T052827Z
```

Current classification:

```json
{
  "overall_status": "advisory",
  "transport_status": "healthy",
  "telegram_media_status": "degraded",
  "provider_status": "historical_incident",
  "failure_domain": "external_network",
  "recommended_action": "observe",
  "mutation_allowed": false,
  "nl_mutation_allowed": false
}
```

Interpretation:

```text
VPN transport is healthy.
Telegram media edge latency is advisory, not a VPN outage.
Provider shutdown evidence is historical from 2026-05-26, not an active outage now.
No NL writes were performed.
```

Additional server-profile mirror:

```text
nl-diagnostics/nl-server-profile/20260527T053614Z
nl-diagnostics/nl-server-profile/latest
nl-diagnostics/collect_nl_server_profile_readonly.sh
```

This mirror stores only sanitized summaries, file metadata, and hashes:

```text
x-ui inbounds/config shape
systemd unit definitions with Environment/LoadCredential redacted
/opt/x0tta6bl4-mesh script hashes
/opt/ghost-access-bot/current script hashes
Ghost VPN file hashes
listener/timer/cron/resource/provider evidence
```

Redaction check:

```text
webBasePath is stored as REDACTED
secret-marker scan returned only command headers and README wording, not actual secret values
```

Gap-analysis from the sanitized profile:

```text
nl-diagnostics/analyze_nl_profile_gaps.py
nl-diagnostics/nl-profile-gap-analysis-2026-05-27.md
nl-diagnostics/nl-profile-gap-analysis-2026-05-27.json
nl-diagnostics/nl-source-reconciliation-plan-2026-05-27.md
```

Result:

```json
{
  "local_name_drift": 6,
  "missing_local_source": 19,
  "same_hash_elsewhere": 1,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Interpretation:

```text
The real NL runtime is not fully represented as local source.
Old local backup files exist for several Ghost Access scripts, but their hashes differ.
x-ui binaries/db/generated config are runtime artifacts and should remain runtime-only.
Next local-safe work is source reconciliation in an isolated nl-server source area.
```

Isolated local source area prepared:

```text
services/nl-server/README.md
services/nl-server/manifest.json
services/nl-server/tools/pull_candidate_readonly.py
services/nl-server/.quarantine/README.md
services/nl-server/systemd/README.md
services/nl-server/mesh-runtime/README.md
services/nl-server/ghost-access/README.md
services/nl-server/ghost-vpn/README.md
services/nl-server/templates/README.md
```

Status:

```text
planning_only
nl_write_allowed: false
manifest JSON: valid
local reviewed source promoted: 16 files
deployable_to_nl: false
secret scan: wording-only hits, no actual keys/URLs/tokens found in this area
quarantine intake tool: dry-run OK, listed 13 P1 source candidates
P1 quarantine intake: 13 accepted, 0 blocked, no NL writes
P2 quarantine intake: 10 accepted, 2 blocked, no NL writes
runtime-state tests: 7 passed
profile/status + ghost protocol tests: 6 passed
listener/profile-hint tests: 8 passed
activity sync + TCP bridge tests: 6 passed
GhostVPN runtime source tests: 5 passed
auto_monitor source tests: 3 passed
apply_config_auto source tests: 5 passed
full_stealth_config source tests: 3 passed
rotation_timer source tests: 2 passed
template tests: 2 passed
health action policy tests: 6 passed
preflight validator: ok=true, deploy blocked
```

Interpretation:

```text
services/nl-server is a quarantine-ready ownership area, not a deploy package.
Its manifest maps missing or drifted NL runtime files to intended reviewed local paths.
The quarantine intake flow has been used once for P1 read-only intake.
It read files from NL, scanned locally, and kept accepted files only under the
git-ignored services/nl-server/.quarantine/incoming tree.
```

P1 intake report:

```text
nl-diagnostics/nl-p1-quarantine-intake-2026-05-27.md
nl-diagnostics/nl-p2-quarantine-intake-2026-05-27.md
nl-diagnostics/nl-source-promotion-matrix-2026-05-27.md
```

Key new findings:

```text
real NL health_check.sh can restart x-ui and uses 600 sec cooldown;
real run_vpn_service_access_agent.py can mark Telegram-only media degradation as overall degraded;
real vps_build_runtime_state.py also maps Telegram media degraded to general mode=degraded;
runtime-state source uses stale assumptions: /usr/local/etc/xray/config.json and auxiliary ports 9443/8388/2096/628;
Ghost Access canary/user-manager scripts are mutating tools, not read-only diagnostics;
Ghost VPN source changes TUN/routes/iptables and needs separate preflight/rollback;
two P2 files were blocked by URI scan and need manual redaction.
```

Local source fix prepared:

```text
services/nl-server/mesh-runtime/vps_build_runtime_state.py
services/nl-server/mesh-runtime/listener_loss_signal.py
services/nl-server/mesh-runtime/publish_client_profile_hint.py
services/nl-server/mesh-runtime/health_action_policy.py
services/nl-server/mesh-runtime/health_check_readonly.sh
services/nl-server/mesh-runtime/health_heal_xui.sh
services/nl-server/ghost-vpn/ghost_vpn_protocol.py
services/nl-server/tests/test_vps_build_runtime_state.py
services/nl-server/tests/test_profile_status_and_ghost_protocol.py
services/nl-server/tests/test_health_action_policy.py
services/nl-server/tools/validate_preflight_readiness.py
```

Local behavior now covered by tests:

```text
transport healthy + telegram_media degraded -> mode advisory, action observe
telegram_media degraded + unknown transport -> mode degraded, action operator_review
x-ui inactive + ghost ready -> fallback/switch_fallback
x-ui inactive + ghost not ready -> degraded/restart_primary
default/current NL x-ui public ports -> 443,2083,39829
nl-beta fallback port -> 2443
profile_status_api reads sanitized state files without exposing secrets
ghost_vpn_protocol round trips key wire messages locally
future x-ui restart policy blocks by default, requires mutation flag, 30 min cooldown, and provider guard
listener-loss signal scoring classifies missing/degraded/healthy primary listener symptoms
client profile hint keeps advisory mode on stable-primary and reserves anti-block profile for degraded/anti_block mode
local client heal cooldown defaults to 30 min; current local client port defaults to 39829
vpn_status --json maps healthy local status to ok/none/observe and route loop to critical/local_client/local_soft_heal
provider guard blocks local heal on provider_outage/provider_host/provider_ticket/failover and critical nl_service
provider guard tracks snapshot age, warns when stale, and blocks stale/missing evidence when --require-fresh is set
VPN_HEAL_FORCE=1 passes --require-fresh to provider guard before ss -K/SIGHUP
watchdog hard-heal is blocked by default; SIGTERM local xray requires VPN_WATCHDOG_ALLOW_HARD_HEAL=1
watchdog hard-heal calls provider guard with --require-fresh before SIGTERM
provider incident packet generator builds local JSON/Markdown evidence for provider tickets
classifier preserves NL runtime recommended_action=switch_profile as an advisory warning
profile-switch policy blocks automatic switching and requires fresh snapshot plus manual review
```

Mutation-gate design:

```text
nl-diagnostics/nl-mutation-gate-design-2026-05-27.md
nl-diagnostics/nl-deploy-preflight-checklist-2026-05-27.md
nl-diagnostics/nl-current-state-refresh-20260527T072732Z.md
nl-diagnostics/nl-redacted-source-review-2026-05-27.md
nl-diagnostics/nl-ghost-access-ownership-map-2026-05-27.md
nl-diagnostics/local-client-healing-audit-2026-05-27.md
nl-diagnostics/local-provider-guard-audit-2026-05-27.md
nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T150900Z.md
nl-diagnostics/profile-switch-policy-2026-05-27.md
nl-diagnostics/blocking-landscape-2026-05-27.md
nl-diagnostics/blocking-response-policy-2026-05-27.md
```

Latest provider packet:

```text
snapshot: nl-diagnostics/snapshots/20260528T021824Z
packet: nl-diagnostics/provider-incident-packets/provider-incident-packet-20260528T021824Z.md
packet_type: provider_watch
snapshot_stale: false
current_cpu_steal_percent: 0.0
current classification: advisory / external_network / observe
provider_status: recent_boot_gap
warnings: ifup@eth0.service non-critical failed unit; NL boot gap seconds=21907; previous boot ended uncleanly
NL writes: 0
```

Profile switch policy:

```text
switch_profile is not a restart signal;
automatic_allowed=false;
stale snapshot -> blocked_stale_snapshot;
fresh healthy/advisory transport -> manual_profile_review;
provider outage and local client critical failures take priority.
```

Blocking policy:

```text
blocking signal is not a restart signal
blocking signal is not an automatic profile switch
SPB is disabled and not part of the current fallback path
classifier now emits blocking_assessment
latest snapshot category: app_specific_degradation
app/path probe command added: nl-diagnostics/probe_blocking_paths.py
default target config: nl-diagnostics/blocking_probe_targets.json
fresh probe snapshot: nl-diagnostics/snapshots/20260528T021824Z
fresh probe summary: no_probe_evidence, 8/8 targets ok direct and SOCKS
probe history command added: nl-diagnostics/summarize_blocking_probe_history.py
probe history report: nl-diagnostics/blocking-probe-history-2026-05-28.md
probe history trend: stable_no_probe_evidence across 6 snapshots
incident entrypoint added: nl-diagnostics/run_vpn_incident_readonly_refresh.sh
incident entrypoint behavior: collect read-only snapshot with blocking probes, then refresh local reports
decision report command added: nl-diagnostics/build_vpn_decision_report.py
current decision report: nl-diagnostics/current-vpn-decision-2026-05-28.md
current decision: observe, high confidence, no NL/SPB writes
boot-gap watch command added: nl-diagnostics/build_boot_gap_watch_report.py
boot-gap watch report: nl-diagnostics/boot-gap-watch-2026-05-28.md
boot-gap watch status: watch, boot_gap_seconds=21907
provider packet refresh added: nl-diagnostics/build_provider_incident_packet.py
provider packet report: nl-diagnostics/provider-incident-packets/provider-incident-packet-20260528T021824Z.md
provider packet status: provider_watch, snapshot_stale=false
freshness gate added: snapshot_age_seconds <= 3600 is fresh; older evidence becomes watch
planning refresh command added: nl-diagnostics/refresh_vpn_planning_reports.py
planning refresh report: nl-diagnostics/vpn-planning-refresh-2026-05-28.md
planning refresh status: ok=true
incident timeline recorder added: nl-diagnostics/record_vpn_incident_timeline.py
incident timeline report: nl-diagnostics/vpn-incident-timeline-2026-05-28.md
incident timeline status: event_count=17, latest_type=provider_watch
manual failover readiness gate added: nl-diagnostics/audit_manual_failover_readiness.py
manual failover readiness report: nl-diagnostics/manual-failover-readiness-2026-05-28.md
manual failover readiness status: blocked_no_incident_trigger, manual_switch_allowed=false
secondary candidate scorer added: nl-diagnostics/score_secondary_exit_candidates.py
secondary candidate example list: nl-diagnostics/secondary-exit-candidates.example.json
secondary candidate score report: nl-diagnostics/secondary-exit-candidate-score-2026-05-28.md
secondary candidate score status: missing_candidates, viable_count=0
secondary exit requirements command added: nl-diagnostics/build_secondary_exit_requirements.py
secondary exit requirements report: nl-diagnostics/secondary-exit-requirements-2026-05-28.md
secondary exit requirements status: requirements_ready_no_candidate, missing=NET-01
secondary provider shortlist command added: nl-diagnostics/build_secondary_exit_provider_shortlist.py
secondary provider shortlist report: nl-diagnostics/secondary-exit-provider-shortlist-2026-05-28.md
secondary provider shortlist status: shortlist_ready_no_endpoint, count=5, endpoint_count=0
secondary provisioning plan command added: nl-diagnostics/build_secondary_exit_provisioning_plan.py
secondary provisioning plan report: nl-diagnostics/secondary-exit-provisioning-plan-2026-05-28.md
secondary provisioning plan status: provisioning_plan_ready_no_endpoint, external_action_required=true, endpoint_count=0
secondary candidate intake command added: nl-diagnostics/build_secondary_exit_candidate_intake.py
secondary candidate intake report: nl-diagnostics/secondary-exit-candidate-intake-2026-05-28.md
secondary candidate intake status: awaiting_public_candidate_metadata, allowed_fields=7
secondary exit flow command added: nl-diagnostics/build_secondary_exit_flow.py
secondary exit flow report: nl-diagnostics/secondary-exit-flow-2026-05-28.md
secondary exit flow status: blocked_missing_candidate, candidate_configured=false, manual_switch_allowed=false
secondary manual drill command added: nl-diagnostics/build_secondary_exit_manual_drill.py
secondary manual drill report: nl-diagnostics/secondary-exit-manual-drill-2026-05-28.md
secondary manual drill status: drill_plan_ready_blocked_no_endpoint, test_scope=single_client, rollback_required=true
outside-in NL transport probe added: nl-diagnostics/probe_nl_transport_ports.py
outside-in NL transport probe report: nl-diagnostics/nl-transport-probe-2026-05-28.md
outside-in NL transport status: healthy, 3/3 ports ok
outside-in NL transport uptime recorder added: nl-diagnostics/record_nl_transport_uptime.py
outside-in NL transport uptime summary: nl-diagnostics/nl-transport-uptime-summary-2026-05-28.md
outside-in NL transport uptime status: stable_healthy, samples=19, bad_streak=0
local uptime scheduler service template: infra/systemd/x0tta-vpn-nl-transport-uptime.service
local uptime scheduler timer template: infra/systemd/x0tta-vpn-nl-transport-uptime.timer
local uptime scheduler status: prepared only, not installed, no systemd command run
local diagnostic environment audit added: nl-diagnostics/audit_local_diagnostic_environment.py
local diagnostic environment report: nl-diagnostics/local-diagnostic-environment-2026-05-28.md
local diagnostic environment status: watch_root_full_tmpdir_available, root_status=critical_full, TMPDIR=/mnt/projects/.tmp writable
refresh TMPDIR guard added: refresh runner passes TMPDIR=/mnt/projects/.tmp to child commands when unset
local root cleanup planner added: nl-diagnostics/plan_local_root_cleanup.py
local root cleanup plan report: nl-diagnostics/local-root-cleanup-plan-2026-05-28.md
local root cleanup plan status: manual_cleanup_plan_ready, estimated_reclaim_gib=3.26, cleanup_execute_allowed=false
readiness audit command added: nl-diagnostics/audit_vpn_plan_readiness.py
readiness audit report: nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md
readiness audit status: ready_local_with_future_blocks, ready_local=19, blocked_future_approval=4, watch=3, missing=0
readiness watch items: BOOT-01, LOCALENV-01, LOCALCLEAN-01
readiness blocked items include: FAILOVER-03, FAILOVER-06, GATE-01, FAILOVER-02
operator card added: nl-diagnostics/build_vpn_operator_card.py
operator card report: nl-diagnostics/vpn-operator-card-2026-05-28.md
operator status: observe
improvement backlog command added: nl-diagnostics/build_vpn_improvement_backlog.py
improvement backlog report: nl-diagnostics/vpn-improvement-backlog-2026-05-28.md
local_now backlog: LOCAL-01, LOCAL-02, LOCAL-03, LOCAL-04
future_nl_write backlog: NL-FUTURE-01, NL-FUTURE-02
future_resilience backlog: FUTURE-RESILIENCE-01
manual failover plan: nl-diagnostics/manual-failover-plan-2026-05-28.md
manual failover status: planning_not_active
secondary exit node: must be new provider/region, not SPB
secondary config generator added: nl-diagnostics/create_secondary_exit_config.py
secondary probe command added: nl-diagnostics/probe_secondary_exit.py
secondary probe example config: nl-diagnostics/manual-failover-secondary.example.json
secondary probe placeholder result: planning_template
```

This is only a local reviewed-source patch. It has not been copied to NL.

Fresh read-only refresh:

```text
snapshot: nl-diagnostics/snapshots/20260528T021824Z
profile: nl-diagnostics/nl-server-profile/20260527T173222Z
overall_status: advisory
transport_status: advisory
telegram_media_status: degraded
failure_domain: external_network
recommended_action: observe
nl_mutation_allowed: false
```

Fresh source reconciliation summary:

```json
{
  "accepted_local_delta": 5,
  "redacted_review_only": 2,
  "redacted_template_only": 1,
  "same_hash_elsewhere": 18,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Interpretation:

```text
Current NL is not in an x-ui outage.
Core listeners 443/2083/39829 are present.
The remaining current degraded signal is Telegram media/external network behavior.
Local semantic fix is prepared but not deployed.
Current NL source reconciliation is locally closed:
missing_local_source=0 and local_name_drift=0.
sync_xray_device_activity.py and ghost_tcp_bridge.py now match current NL hashes locally.
ghost_vpn_client.py also matches current NL hash locally; ghost_vpn_server.py is now an accepted local formatting delta with the remote hash still recorded.
auto_monitor.py also matches current NL hash locally and is covered without importing its /opt log side effects.
apply_config_auto.py also matches current NL hash locally, but is class C/not deployable because it writes x-ui config.
full_stealth_config.py also matches current NL hash locally, but is class C/not deployable because it writes x-ui config and rotation metadata.
rotation_timer.sh also matches current NL hash locally, but is class C/not deployable because it runs config rotation and signals Xray.
nl-beta-2443 has a redacted example template; raw production config is still intentionally not stored.
Two sensitive Ghost Access files have redacted review copies only, not deployable source.
Local vpn_status JSON reports ok/none/observe and is now part of snapshots.
```

## Work not allowed yet

These are intentionally deferred until explicit write permission for NL:

```text
systemctl changes on NL
x-ui db/config edits
copying scripts to NL
restarting x-ui/warp/ghost services
changing cron/timers on NL
```

## Recommended priority

Do first:

```text
P0 + P1 + P2
```

Reason: they improve diagnosis and reduce false alarms without touching production.

Do next:

```text
P3 + P4
```

Reason: they make future changes safer and reduce drift.

Do after:

```text
P5 + P6
```

Reason: second node and full hardening matter, but only after the current single-node system is observable and documented.
