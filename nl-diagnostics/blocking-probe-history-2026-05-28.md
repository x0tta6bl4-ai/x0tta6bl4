# Blocking Probe History

generated_at: `2026-05-28T02:35:31.781331+00:00`
snapshots_dir: `nl-diagnostics/snapshots`

## Summary

```json
{
  "snapshot_count": 7,
  "trend": "stable_no_probe_evidence",
  "assessment_counts": {
    "no_probe_evidence": 7
  },
  "degraded_by_target": {},
  "degraded_by_group": {},
  "latest": {
    "snapshot": "20260528T021824Z",
    "generated_at": "2026-05-28T02:18:45.535852+00:00",
    "assessment": "no_probe_evidence",
    "target_count": 8,
    "ok_count": 8,
    "degraded_count": 0,
    "group_assessments": {
      "ai": {
        "ok": 1
      },
      "baseline": {
        "ok": 1
      },
      "dev": {
        "ok": 1
      },
      "ru": {
        "ok": 1
      },
      "telegram": {
        "ok": 2
      },
      "telegram_media": {
        "ok": 2
      }
    },
    "degraded_targets": [],
    "socks_proxy_detected": true,
    "socks_port": 10918,
    "http_proxy_configured": false,
    "targets_source": "/mnt/projects/nl-diagnostics/blocking_probe_targets.json"
  }
}
```

## Timeline

| Snapshot | Assessment | OK/Total | Degraded targets |
|---|---|---:|---|
| `20260527T210659Z` | `no_probe_evidence` | 4/4 | - |
| `20260527T220219Z` | `no_probe_evidence` | 8/8 | - |
| `20260527T221810Z` | `no_probe_evidence` | 8/8 | - |
| `20260527T230246Z` | `no_probe_evidence` | 8/8 | - |
| `20260528T000600Z` | `no_probe_evidence` | 8/8 | - |
| `20260528T011622Z` | `no_probe_evidence` | 8/8 | - |
| `20260528T021824Z` | `no_probe_evidence` | 8/8 | - |

## Interpretation

All available blocking probes report no direct-vs-SOCKS blocking evidence.

No NL or SPB writes were performed by this history summary.
