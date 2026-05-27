# Blocking Probe Snapshot

Status date: 2026-05-28 local time / 2026-05-27 UTC.

Snapshot:

```text
nl-diagnostics/snapshots/20260527T220219Z
```

## Result

```json
{
  "overall_status": "advisory",
  "transport_status": "healthy",
  "telegram_media_status": "degraded",
  "provider_status": "recent_boot_gap",
  "failure_domain": "external_network",
  "recommended_action": "observe",
  "blocking_probe_summary": {
    "assessment": "no_probe_evidence",
    "target_assessments": {
      "ok": 8
    },
    "target_count": 8
  },
  "blocking_assessment": {
    "category": "app_specific_degradation",
    "confidence": "medium",
    "mutation_allowed": false,
    "nl_mutation_allowed": false,
    "auto_profile_switch_allowed": false,
    "recommended_probe": "test Telegram media separately from core VPN; do not restart x-ui",
    "reason": "Telegram/media degraded while core transport is healthy/advisory"
  }
}
```

## Probe Groups

```text
baseline: ok 1
telegram: ok 2
telegram_media: ok 2
ai: ok 1
dev: ok 1
ru: ok 1
```

## Probe Targets

```text
connectivity: direct=204, socks=204
telegram_web: direct=200, socks=200
telegram_api: direct=200, socks=200
telegram_media_dc2_149_154_166_111_443: direct=tcp-ok, socks=tcp-ok
telegram_media_dc4_91_108_56_161_443: direct=tcp-ok, socks=tcp-ok
openai_api: direct=401, socks=401
github: direct=200, socks=200
russia_search: direct=200, socks=200
```

SOCKS proxy detected:

```text
127.0.0.1:10918
```

HTTP proxy was not configured, so only direct and SOCKS paths were compared.

## Interpretation

The expanded app/path probe found no obvious direct-vs-SOCKS blocking evidence
from the current local network at probe time.

The remaining degraded signal comes from NL runtime Telegram/media latency
spread. Because Telegram web/API and two Telegram media TCP endpoints were OK
from the local probe, this is still an advisory signal, not an `x-ui` outage.

No NL or SPB writes were performed.
