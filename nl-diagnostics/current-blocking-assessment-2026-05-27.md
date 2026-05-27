# Current Blocking Assessment

Status date: 2026-05-28 local time / 2026-05-27 UTC.

Snapshot:

```text
nl-diagnostics/snapshots/20260527T220219Z
```

Current classification:

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
    "group_assessments": {
      "ai": {"ok": 1},
      "baseline": {"ok": 1},
      "dev": {"ok": 1},
      "ru": {"ok": 1},
      "telegram": {"ok": 2},
      "telegram_media": {"ok": 2}
    },
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

## Interpretation

The current evidence does not point to an active `x-ui` outage.

The expanded local blocking probe did not find an obvious block for the tested
targets:

```text
connectivity: direct ok, SOCKS ok
telegram_web: direct ok, SOCKS ok
telegram_api: direct ok, SOCKS ok
telegram_media_dc2_149_154_166_111_443: direct tcp ok, SOCKS tcp ok
telegram_media_dc4_91_108_56_161_443: direct tcp ok, SOCKS tcp ok
openai_api: direct ok, SOCKS ok
github: direct ok, SOCKS ok
russia_search: direct ok, SOCKS ok
```

History across saved probe snapshots now says the same thing:

```text
report: nl-diagnostics/blocking-probe-history-2026-05-28.md
snapshot_count: 2
trend: stable_no_probe_evidence
latest snapshot: 20260527T220219Z
latest targets: 8/8 ok
degraded targets: 0
```

The remaining active symptom is NL-side Telegram/media path degradation:
Telegram/media edges are slow while the core VPN transport is healthy.

Do not restart `x-ui` for this signal. Do not auto-switch profile. Do not use
SPB while SPB is disabled.

## Watch Items

```text
ifup@eth0.service is a known non-critical failed unit
recent boot gap remains provider-watch evidence
previous boot ended uncleanly
```

## Next Probe

Run app-specific checks separately from core VPN health:

```text
core VPN transport
Telegram web/calls/media path
Russian sites that may reject VPN exits
mobile ISP vs fixed-line ISP path
direct/http/socks comparison when available
```

No NL or SPB writes were performed.
