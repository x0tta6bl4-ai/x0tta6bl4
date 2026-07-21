# Validation Report Template

This template defines the structure for every validation report.

---

## Report Structure

```
reports/
└── YYYY-MM-DD_commit-SHA/
    ├── metadata.json          # System info, git commit, timestamp
    ├── invariants.json        # Invariant check results
    ├── latency.json           # Latency measurements + CI
    ├── recovery.json          # Recovery time measurements
    ├── regression.json        # Comparison with baseline
    ├── summary.json           # PASS/FAIL/WARN verdicts
    ├── metrics.prom           # Prometheus format
    └── report.md              # Human-readable summary
```

---

## metadata.json

```json
{
  "report_version": "1.0",
  "git_commit": "518b1052",
  "git_branch": "main",
  "timestamp": "2026-07-21T16:00:00Z",
  "system": {
    "kernel": "6.14.0-37-generic",
    "cpu": "AMD Athlon 3000G",
    "ram_gb": 13,
    "tcp_cc": "bbr",
    "provider": "HOSTKEY NL AS57043"
  },
  "methodology": {
    "bootstrap_method": "percentile",
    "bootstrap_resamples": 1000,
    "random_seed": 42,
    "min_samples": 30,
    "confidence_level": 0.95
  }
}
```

---

## invariants.json

```json
{
  "invariants": [
    {
      "id": "I1",
      "name": "No Routing Loops",
      "status": "VERIFIED",
      "method": "DFS cycle detection on captured packet flow graph",
      "evidence": "proofs/i1_loop_check.json",
      "timestamp": "2026-07-21T16:05:00Z"
    }
  ],
  "overall": "VERIFIED"
}
```

---

## latency.json

```json
{
  "targets": [
    {
      "name": "direct_google",
      "n": 30,
      "median_ms": 810.2,
      "ci_lower_ms": 795.1,
      "ci_upper_ms": 825.3,
      "ci_method": "bootstrap_percentile_B=1000",
      "stdev_ms": 231.1,
      "success_count": 30,
      "success_rate": "30/30 requests completed successfully"
    }
  ]
}
```

---

## regression.json

```json
{
  "baseline_commit": "abc1234",
  "current_commit": "518b1052",
  "baseline_date": "2026-07-20",
  "comparisons": [
    {
      "metric": "latency_direct_median_ms",
      "baseline": 795.0,
      "current": 810.2,
      "change_pct": 1.9,
      "severity": "none",
      "verdict": "PASS"
    }
  ]
}
```

---

## summary.json

```json
{
  "overall_verdict": "PASS",
  "invariants": {
    "verified": 7,
    "violated": 0,
    "skipped": 0
  },
  "sla_results": [
    {"rule": "Node Failure Recovery", "verdict": "PASS", "measured": "1.2s"},
    {"rule": "Session Survival", "verdict": "PASS", "measured": "100% (30/30)"},
    {"rule": "Latency Direct", "verdict": "PASS", "measured": "810ms [795, 825]"},
    {"rule": "Latency VPN", "verdict": "PASS", "measured": "620ms [580, 660]"}
  ],
  "regression": {
    "regressions_detected": 0,
    "improvements_detected": 1
  }
}
```

---

## report.md

```markdown
# Validation Report — 2026-07-21

**Commit:** 518b1052
**System:** AMD Athlon 3000G, 13GB RAM, kernel 6.14.0-37

## Invariants
All 7 invariants VERIFIED.

## Latency
| Target | Median | 95% CI | N |
|--------|--------|--------|---|
| Direct Google | 810ms | [795, 825] | 30 |
| VPN Telegram | 620ms | [580, 660] | 30 |

## Regression
No regressions detected vs baseline (abc1234).

## Verdict: PASS
```
