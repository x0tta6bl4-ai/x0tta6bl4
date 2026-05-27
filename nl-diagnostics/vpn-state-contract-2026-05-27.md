# VPN state contract, 2026-05-27

## Назначение

Этот контракт нужен, чтобы все проверки VPN говорили одним языком.

Главное правило: `degraded` не всегда означает "VPN не работает". Нужно отдельно показывать:

- что именно сломалось;
- где находится проблема;
- можно ли лечить автоматически;
- нужно ли писать провайдеру;
- можно ли трогать NL.
- похоже ли событие на блокировку, а не на поломку сервера.

В текущей фазе NL read-only, поэтому любые действия на NL должны быть `mutation_allowed=false`.

## Поля состояния

Минимальный итоговый объект:

```json
{
  "overall_status": "ok",
  "transport_status": "healthy",
  "application_status": "healthy",
  "provider_status": "normal",
  "failure_domain": "none",
  "recommended_action": "observe",
  "blocking_assessment": {
    "category": "none",
    "confidence": "low",
    "nl_mutation_allowed": false,
    "auto_profile_switch_allowed": false
  },
  "mutation_allowed": false,
  "evidence": []
}
```

## Статусы

### `ok`

VPN работает без значимых предупреждений.

Условия:

```text
local vpn_status PASS
SOCKS healthy
exit IP == 89.125.1.107
route to 89.125.1.107 bypasses singbox_tun
packet loss == 0 or below advisory threshold
NL x-ui active
NL required listeners present
NL runtime transport healthy
```

Action:

```text
observe
```

### `advisory`

Есть предупреждение, но основной VPN transport работает.

Примеры:

```text
Telegram media latency spread high
secondary path slightly faster than main
health-check warning about missing TLS cert on Reality-only setup
old template drift exists but runtime is healthy
```

Action:

```text
observe
```

### `degraded`

VPN работает частично или нестабильно, но не полностью упал.

Примеры:

```text
one of several NL listeners missing
WARP unhealthy but direct transport still works
packet loss elevated but not total
SOCKS latency high across repeated checks
FIN-WAIT-2/CLOSE-WAIT elevated but below critical
```

Action:

```text
operator_review
local_soft_heal only if failure_domain=local_client and dry-run is clean
```

### `critical`

Основная функция VPN нарушена.

Примеры:

```text
local vpn_status FAIL
SOCKS unreachable
exit IP is not VPN server
route to VPN endpoint goes through singbox_tun
NL x-ui down
all required NL listeners missing
packet loss critical
```

Action:

```text
local_soft_heal if local_client
operator_review if nl_service
failover if secondary node exists
```

### `provider_outage`

Проблема похожа на хост/провайдера, а не на x-ui/Xray.

Примеры:

```text
server unreachable from network and no local route/proxy issue
hypervisor initiated shutdown in journal
CPU steal very high
disk await very high
load extreme on low CPU count
qemu guest-shutdown from hypervisor
```

Action:

```text
provider_ticket
failover if available
do not restart services during host overload
```

## Failure domains

### `none`

Нет активной проблемы.

### `local_client`

Проблема на локальной машине.

Signals:

```text
singbox_tun missing
SOCKS unreachable locally
local xray missing
route loop to 89.125.1.107
local watchdog metrics stale/unavailable
```

Allowed read/write:

```text
local reads: yes
local writes: only after explicit task
NL writes: no
```

### `nl_service`

Проблема внутри VPS или его сервисов.

Signals:

```text
x-ui inactive
warp-svc inactive
ghost-vpn inactive
required listeners missing
runtime-state transport unhealthy
subscription health unhealthy
```

Allowed read/write:

```text
NL reads: yes
NL writes: no until explicit permission
```

### `provider_host`

Проблема на стороне хоста провайдера.

Signals:

```text
hypervisor initiated shutdown
high %steal
high disk await with low guest workload
abrupt boot gap
server unreachable while local routing is healthy
```

Allowed actions:

```text
do not restart services as first response
prepare provider ticket
failover if available
```

Provider ticket evidence should be generated locally:

```text
python3 nl-diagnostics/build_provider_incident_packet.py
```

### `external_network`

Проблема между клиентом и сервером или на внешнем маршруте.

Signals:

```text
packet loss to 89.125.1.107
high RTT only from one client network
NL services healthy, but client cannot reach ports
```

Action:

```text
collect traceroute/mtr if available
try alternate local network
failover if needed
```

## Blocking Assessment

`blocking_assessment` объясняет, похоже ли событие на блокировку или
фильтрацию. Это подсказка для диагностики, а не разрешение что-то менять.

Категории:

```text
none
app_specific_degradation
anti_block_candidate
external_network_degradation
exit_ip_or_vpn_rejected
possible_local_isp_block
vpn_path_degraded
local_client_issue
nl_service_issue
provider_or_host_issue
```

Правило:

```text
blocking signal != restart signal
blocking signal != automatic profile switch
```

Например:

```text
core transport healthy + Telegram media degraded
= app_specific_degradation / observe / no NL mutation

runtime_mode=anti_block + recommended_action=switch_profile
= anti_block_candidate / manual review / no automatic switch
```

### `manual_profile_review`

Серверный runtime может предложить:

```text
recommended_action=switch_profile
runtime_mode=anti_block
```

Это не автоматическое действие.

Allowed actions:

```text
fresh read-only snapshot
manual review of profile switch signal
no automatic switch
no NL write
```

### `unknown`

Данных недостаточно.

Action:

```text
collect read-only evidence bundle
do not mutate NL
```

## Recommended actions

### `observe`

Ничего не менять. Продолжать мониторинг.

### `local_soft_heal`

Только локальные мягкие действия:

```text
refresh route bypass
re-detect SOCKS port
clear local stale TCP states if explicitly approved
SIGHUP local xray only after preflight
```

### `local_hard_heal`

Локальные разрушительные действия:

```text
SIGTERM local xray
restart local x0tta-node
restart local xray.service
```

Требует отдельного подтверждения или явного флага. Для watchdog это:

```text
VPN_WATCHDOG_ALLOW_HARD_HEAL=1
fresh provider-guard snapshot required before SIGTERM
```

### `operator_review`

Показать человеку конкретную причину и команды read-only.

### `provider_ticket`

Собрать:

```text
journal boot gap
qemu-ga / hypervisor shutdown lines
sar CPU steal
sar disk await
uptime/boot time
server IP and hostname
```

### `failover`

Переключиться на второй exit node, когда он будет подготовлен.

## Mutation policy

До отдельной команды:

```text
mutation_allowed=false
remote_mutation_allowed=false
nl_mutation_allowed=false
```

Даже если статус `critical`, NL нельзя менять без явной команды.

## Classification rules

Правила применяются сверху вниз.

| Rule | Condition | overall_status | failure_domain | recommended_action |
|---|---|---|---|---|
| R1 | journal has hypervisor shutdown or boot gap with high steal/disk wait | provider_outage | provider_host | provider_ticket |
| R2 | local route to VPN server goes through `singbox_tun` | critical | local_client | local_soft_heal |
| R3 | local SOCKS unreachable and local xray missing | critical | local_client | local_soft_heal |
| R4 | exit IP is not `89.125.1.107` | critical | local_client | operator_review |
| R5 | NL `x-ui` inactive or all x-ui listeners missing | critical | nl_service | operator_review |
| R6 | NL transport healthy but Telegram media degraded | advisory | external_network | observe |
| R7 | one reserve path degraded but primary healthy | advisory | nl_service | observe |
| R8 | packet loss high from local to NL, NL healthy | degraded | external_network | operator_review |
| R9 | all core checks pass | ok | none | observe |
| R10 | evidence incomplete | degraded | unknown | operator_review |

Additional blocking labels:

| Condition | blocking_assessment.category | Meaning |
|---|---|---|
| Core transport healthy, one app/media path degraded | `app_specific_degradation` | Test the app path separately; do not restart NL |
| Runtime says `anti_block` or `switch_profile` | `anti_block_candidate` | Manual profile review only |
| Direct path works, SOCKS/VPN path gets 403/451 | `exit_ip_or_vpn_rejected` | Site may reject VPN/proxy exit IP |
| Direct path fails, SOCKS/VPN path works | `possible_local_isp_block` | Local ISP/path may be filtering direct access |
| Direct path works, SOCKS/VPN path fails | `vpn_path_degraded` | VPN/proxy path needs review; not automatically NL restart |
| Provider/host evidence present | `provider_or_host_issue` | Build provider packet first |
| Local route/SOCKS broken | `local_client_issue` | Fix local client first |
| NL service/listener broken | `nl_service_issue` | Read-only NL inspection first |

## Current expected classification

На 2026-05-27 текущий expected state:

```text
overall_status: advisory
transport_status: healthy/advisory
application_status: healthy
provider_status: normal
failure_domain: external_network
recommended_action: observe
mutation_allowed: false
```

Почему не `critical`:

```text
local vpn_status PASS
SOCKS healthy
exit IP correct
NL x-ui active
NL listeners present
NL runtime paths main/443 and secondary/2083 healthy
packet loss 0
```

Почему не чистый `ok`:

```text
NL runtime mode reports degraded/advisory because Telegram media edge latency spread is high.
```

## Read-only evidence commands

Local:

```bash
bash scripts/vpn_status.sh --check --no-color
systemctl is-active x0tta-node.service x0tta-vpn-watchdog.service x0tta-vpn-route-bypass.service x0tta-vpn-boot-validate.timer xray.service
ip route get 89.125.1.107
ip route get 1.1.1.1
curl -fsS --max-time 3 http://127.0.0.1:9091/metrics
```

NL read-only:

```bash
ssh nl 'hostname; who -b; uptime; systemctl --failed --no-pager'
ssh nl 'systemctl is-active x-ui warp-svc ghost-vpn ghost-tcp-bridge ghost-access-nl-beta nginx docker'
ssh nl 'ss -lntup | egrep ":(443|2083|39829|2443|4433|4434|51820|8443|62789)" || true'
ssh nl 'sqlite3 -readonly /etc/x-ui/x-ui.db "select id,port,protocol,enable,remark from inbounds order by port;"'
ssh nl 'cat /opt/x0tta6bl4-mesh/state/runtime-state.json'
```

Do not run on NL in read-only phase:

```bash
systemctl restart ...
systemctl enable/disable ...
sqlite3 /etc/x-ui/x-ui.db "update ..."
scp ... nl:...
LOG_DIR=/tmp bash -s < x0tta6bl4-xray-vps/scripts/health-check.sh
```
