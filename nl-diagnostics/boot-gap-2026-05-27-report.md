# NL boot gap report, 2026-05-27

## Статус

NL был проверен read-only. На сервере не выполнялись restart, deploy, запись в
config/db или изменение systemd.

Свежий snapshot:

```text
/mnt/projects/nl-diagnostics/snapshots/20260527T154832Z
```

Итог классификации:

```text
overall_status: advisory
failure_domain: external_network
recommended_action: observe
transport_status: advisory
telegram_media_status: degraded
provider_status: recent_boot_gap
problems: []
NL writes: 0
```

## Что доказано

Гостевой журнал NL показывает разрыв между двумя загрузками:

```text
previous boot last entry: Wed 2026-05-27 08:53:30 UTC
current boot first entry:  Wed 2026-05-27 14:58:37 UTC
gap: 21907 seconds, about 6h 05m 07s
```

В локальном времени `Europe/Simferopol` это примерно:

```text
2026-05-27 11:53:30 -> 2026-05-27 17:58:37
```

После текущей загрузки journald зафиксировал нечистое завершение предыдущего
boot:

```text
May 27 14:58:38 01164.com systemd-journald[302]: File /var/log/journal/.../system.journal corrupted or uncleanly shut down, renaming and replacing.
```

`last -x -F` не показывает штатную строку `shutdown system down` для этого
разрыва. Это отличается от обычного чистого выключения, где systemd успевает
записать shutdown-событие.

## Что было перед обрывом

В последние минуты предыдущего boot видны признаки зависания/просадки хоста:

```text
08:51:29-08:53:30 WARP watchdog reports hung daemon
08:51:35 and 08:53:19 kernel: clocksource Long readout interval
08:51:18-08:53:30 kernel: workqueue ... hogged CPU
08:53:21 ghost-access-bot: device activity sync timed out
```

При этом перед обрывом runtime-state не показывал падение x-ui:

```text
xui_service_ok: true
listener_443_ok: true
transport path 443: healthy
transport path 2083: healthy
subscription_health_status: healthy
warp_status: healthy
```

## Что сейчас

На свежем snapshot:

```text
local vpn_status: ok
exit IP: 89.125.1.107
packet_loss_percent: 0
x-ui: active
warp-svc: active
ghost-vpn: active
ghost-tcp-bridge: active
ghost-access-nl-beta: active
nginx: active
docker: active
listeners: 443, 2083, 39829 present
```

Единственный failed unit:

```text
ifup@eth0.service
```

Он сейчас классифицирован как non-critical для VPN, потому что основные
сервисы, маршруты и listener ports работают.

## Вывод

Наиболее вероятная причина пользовательского "VPN снова не работал" сегодня:
NL фактически отсутствовал между `2026-05-27 08:53:30 UTC` и
`2026-05-27 14:58:37 UTC`. Это похоже не на сбой x-ui config и не на локальный
client route loop, а на нечистую остановку/зависание ВМ или хостовой стороны.

В гостевом журнале для этого нового разрыва нет явной строки
`hypervisor initiated shutdown`. Поэтому корректная формулировка сейчас:

```text
provider_watch, not confirmed provider_outage
```

Провайдеру нужно подтвердить со своей стороны, было ли host maintenance,
node overload, storage degradation или automated power action.

## Артефакты

```text
snapshot: /mnt/projects/nl-diagnostics/snapshots/20260527T154832Z
provider packet: /mnt/projects/nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T154832Z.md
boot-gap raw bundle: /mnt/projects/nl-diagnostics/boot-gap/20260527T153158Z
```
