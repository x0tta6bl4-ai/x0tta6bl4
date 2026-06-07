# Blocking Probe History

generated_at: `2026-06-06T12:58:03.213532+00:00`
snapshots_dir: `nl-diagnostics/snapshots`

## Summary

```json
{
  "snapshot_count": 15,
  "trend": "has_degradation",
  "assessment_counts": {
    "no_probe_evidence": 13,
    "possible_local_isp_block": 2
  },
  "degraded_by_target": {
    "connectivity": 2,
    "github": 2,
    "openai_api": 2,
    "russia_search": 2,
    "telegram_api": 2,
    "telegram_media_dc2_149_154_166_111_443": 1,
    "telegram_media_dc4_91_108_56_161_443": 1,
    "telegram_web": 2
  },
  "degraded_by_group": {
    "ai": 2,
    "baseline": 2,
    "dev": 2,
    "ru": 2,
    "telegram": 4,
    "telegram_media": 2
  },
  "latest": {
    "snapshot": "20260606T125103Z",
    "generated_at": "2026-06-06T12:51:48.749272+00:00",
    "assessment": "possible_local_isp_block",
    "target_count": 8,
    "ok_count": 0,
    "degraded_count": 8,
    "group_assessments": {
      "ai": {
        "possible_local_isp_block": 1
      },
      "baseline": {
        "possible_local_isp_block": 1
      },
      "dev": {
        "possible_local_isp_block": 1
      },
      "ru": {
        "target_or_global_unreachable": 1
      },
      "telegram": {
        "possible_local_isp_block": 2
      },
      "telegram_media": {
        "possible_local_isp_block": 2
      }
    },
    "degraded_targets": [
      {
        "label": "connectivity",
        "kind": "http",
        "group": "baseline",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": 0,
        "socks_http_code": 204
      },
      {
        "label": "telegram_web",
        "kind": "http",
        "group": "telegram",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": 0,
        "socks_http_code": 200
      },
      {
        "label": "telegram_api",
        "kind": "http",
        "group": "telegram",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": 0,
        "socks_http_code": 200
      },
      {
        "label": "telegram_media_dc2_149_154_166_111_443",
        "kind": "tcp",
        "group": "telegram_media",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": null,
        "socks_http_code": null
      },
      {
        "label": "telegram_media_dc4_91_108_56_161_443",
        "kind": "tcp",
        "group": "telegram_media",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": null,
        "socks_http_code": null
      },
      {
        "label": "openai_api",
        "kind": "http",
        "group": "ai",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": 0,
        "socks_http_code": 401
      },
      {
        "label": "github",
        "kind": "http",
        "group": "dev",
        "assessment": "possible_local_isp_block",
        "direct_ok": false,
        "socks_ok": true,
        "direct_http_code": 0,
        "socks_http_code": 200
      },
      {
        "label": "russia_search",
        "kind": "http",
        "group": "ru",
        "assessment": "target_or_global_unreachable",
        "direct_ok": false,
        "socks_ok": false,
        "direct_http_code": 0,
        "socks_http_code": 0
      }
    ],
    "socks_proxy_detected": true,
    "socks_port": 7890,
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

## Interpretation

At least one snapshot has degraded probe targets. Check repeated targets/groups before changing profiles.

No NL or SPB writes were performed by this history summary.
