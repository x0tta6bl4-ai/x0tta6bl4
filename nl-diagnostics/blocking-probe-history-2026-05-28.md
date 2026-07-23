# Blocking Probe History

generated_at: `2026-07-17T18:26:19.385558+00:00`
snapshots_dir: `nl-diagnostics/snapshots`

## Summary

```json
{
  "snapshot_count": 23,
  "trend": "has_degradation",
  "assessment_counts": {
    "no_probe_evidence": 18,
    "possible_local_isp_block": 2,
    "vpn_path_degraded": 3
  },
  "degraded_by_target": {
    "connectivity": 5,
    "github": 5,
    "openai_api": 5,
    "russia_search": 5,
    "telegram_api": 5,
    "telegram_media_dc2_149_154_166_111_443": 4,
    "telegram_media_dc4_91_108_56_161_443": 4,
    "telegram_web": 5
  },
  "degraded_by_group": {
    "ai": 5,
    "baseline": 5,
    "dev": 5,
    "ru": 5,
    "telegram": 10,
    "telegram_media": 8
  },
  "latest": {
    "snapshot": "20260717T182536Z",
    "generated_at": "2026-07-17T18:25:57.005779+00:00",
    "assessment": "vpn_path_degraded",
    "target_count": 8,
    "ok_count": 0,
    "degraded_count": 8,
    "group_assessments": {
      "ai": {
        "vpn_path_degraded": 1
      },
      "baseline": {
        "vpn_path_degraded": 1
      },
      "dev": {
        "vpn_path_degraded": 1
      },
      "ru": {
        "vpn_path_degraded": 1
      },
      "telegram": {
        "vpn_path_degraded": 2
      },
      "telegram_media": {
        "vpn_path_degraded": 2
      }
    },
    "degraded_targets": [
      {
        "label": "connectivity",
        "kind": "http",
        "group": "baseline",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": 204,
        "socks_http_code": null
      },
      {
        "label": "telegram_web",
        "kind": "http",
        "group": "telegram",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": 200,
        "socks_http_code": null
      },
      {
        "label": "telegram_api",
        "kind": "http",
        "group": "telegram",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": 200,
        "socks_http_code": null
      },
      {
        "label": "telegram_media_dc2_149_154_166_111_443",
        "kind": "tcp",
        "group": "telegram_media",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": null,
        "socks_http_code": null
      },
      {
        "label": "telegram_media_dc4_91_108_56_161_443",
        "kind": "tcp",
        "group": "telegram_media",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": null,
        "socks_http_code": null
      },
      {
        "label": "openai_api",
        "kind": "http",
        "group": "ai",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": 401,
        "socks_http_code": null
      },
      {
        "label": "github",
        "kind": "http",
        "group": "dev",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": 200,
        "socks_http_code": null
      },
      {
        "label": "russia_search",
        "kind": "http",
        "group": "ru",
        "assessment": "vpn_path_degraded",
        "direct_ok": true,
        "socks_ok": false,
        "direct_http_code": 200,
        "socks_http_code": null
      }
    ],
    "socks_proxy_detected": false,
    "socks_port": null,
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
| `20260717T182536Z` | `vpn_path_degraded` | 0/8 | connectivity=vpn_path_degraded, telegram_web=vpn_path_degraded, telegram_api=vpn_path_degraded, telegram_media_dc2_149_154_166_111_443=vpn_path_degraded, telegram_media_dc4_91_108_56_161_443=vpn_path_degraded, openai_api=vpn_path_degraded, github=vpn_path_degraded, russia_search=vpn_path_degraded |

## Interpretation

At least one snapshot has degraded probe targets. Check repeated targets/groups before changing profiles.

No NL or SPB writes were performed by this history summary.
