# Blocking Probe History

generated_at: `2026-07-02T13:55:13.696268+00:00`
snapshots_dir: `nl-diagnostics/snapshots`

## Summary

```json
{
  "snapshot_count": 22,
  "trend": "has_degradation",
  "assessment_counts": {
    "no_probe_evidence": 18,
    "possible_local_isp_block": 2,
    "vpn_path_degraded": 2
  },
  "degraded_by_target": {
    "connectivity": 4,
    "github": 4,
    "openai_api": 4,
    "russia_search": 4,
    "telegram_api": 4,
    "telegram_media_dc2_149_154_166_111_443": 3,
    "telegram_media_dc4_91_108_56_161_443": 3,
    "telegram_web": 4
  },
  "degraded_by_group": {
    "ai": 4,
    "baseline": 4,
    "dev": 4,
    "ru": 4,
    "telegram": 8,
    "telegram_media": 6
  },
  "latest": {
    "snapshot": "20260702T135431Z",
    "generated_at": "2026-07-02T13:54:49.174170+00:00",
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
    "socks_port": 10808,
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
| `20260528T025444Z` | `no_probe_evidence` | 8/8 | - |
| `20260528T031418Z` | `no_probe_evidence` | 8/8 | - |
| `20260528T032605Z` | `no_probe_evidence` | 8/8 | - |
| `20260528T034120Z` | `no_probe_evidence` | 8/8 | - |
| `20260531T134449Z` | `no_probe_evidence` | 8/8 | - |
| `20260601T191625Z` | `no_probe_evidence` | 8/8 | - |
| `20260606T061939Z` | `possible_local_isp_block` | 2/8 | connectivity=possible_local_isp_block, telegram_web=possible_local_isp_block, telegram_api=possible_local_isp_block, openai_api=possible_local_isp_block, github=possible_local_isp_block, russia_search=target_or_global_unreachable |
| `20260606T125103Z` | `possible_local_isp_block` | 0/8 | connectivity=possible_local_isp_block, telegram_web=possible_local_isp_block, telegram_api=possible_local_isp_block, telegram_media_dc2_149_154_166_111_443=possible_local_isp_block, telegram_media_dc4_91_108_56_161_443=possible_local_isp_block, openai_api=possible_local_isp_block, github=possible_local_isp_block, russia_search=target_or_global_unreachable |
| `20260616T122725Z` | `vpn_path_degraded` | 0/8 | connectivity=vpn_path_degraded, telegram_web=vpn_path_degraded, telegram_api=vpn_path_degraded, telegram_media_dc2_149_154_166_111_443=vpn_path_degraded, telegram_media_dc4_91_108_56_161_443=vpn_path_degraded, openai_api=vpn_path_degraded, github=vpn_path_degraded, russia_search=vpn_path_degraded |
| `20260702T132514Z` | `vpn_path_degraded` | 0/8 | connectivity=vpn_path_degraded, telegram_web=vpn_path_degraded, telegram_api=vpn_path_degraded, telegram_media_dc2_149_154_166_111_443=vpn_path_degraded, telegram_media_dc4_91_108_56_161_443=vpn_path_degraded, openai_api=vpn_path_degraded, github=vpn_path_degraded, russia_search=vpn_path_degraded |
| `20260702T134728Z` | `no_probe_evidence` | 8/8 | - |
| `20260702T134835Z` | `no_probe_evidence` | 8/8 | - |
| `20260702T135036Z` | `no_probe_evidence` | 8/8 | - |
| `20260702T135211Z` | `no_probe_evidence` | 8/8 | - |
| `20260702T135431Z` | `no_probe_evidence` | 8/8 | - |

## Interpretation

At least one snapshot has degraded probe targets. Check repeated targets/groups before changing profiles.

No NL or SPB writes were performed by this history summary.
