# Validation Framework — How to Run

## Quick Start

```bash
# Clone and enter project
git clone <repo>
cd x0tta6bl4

# Run full validation (N=30, ~2 minutes)
make -f Makefile.validation validate

# Check results
ls results/*/
```

## What You Get

After `make validate`, you get:

```
results/
└── 2026-07-21_16-00-00_sha-518b1052/
    ├── metadata.json     # System info, git commit, timestamp
    ├── raw.json          # All measurements (N=30 per target)
    ├── summary.json      # PASS/FAIL/WARN verdicts
    ├── metrics.prom      # Prometheus format
    └── report.html       # Human-readable report
```

## Understanding the Output

### summary.json

```json
{
  "overall_verdict": "PASS",
  "invariants": {"verified": 7, "violated": 0, "skipped": 0},
  "sla_results": [
    {"rule": "Latency Median (Direct)", "verdict": "PASS", "measured": "810ms"}
  ]
}
```

### Verdict Meanings

| Verdict | Meaning |
|:--------|:--------|
| **PASS** | Metric within SLA threshold |
| **WARNING** | Metric degraded but within tolerance |
| **FAIL** | Metric outside SLA, requires investigation |

## Commands

| Command | Description |
|:--------|:------------|
| `make -f Makefile.validation validate` | Full validation (N=30) |
| `make -f Makefile.validation validate-fast` | Quick validation (N=10) |
| `make -f Makefile.validation meta-test` | Meta-tests only |
| `make -f Makefile.validation property-test` | Property-based tests |
| `make -f Makefile.validation test` | All tests |
| `make -f Makefile.validation report` | Generate HTML report |
| `make -f Makefile.validation compare` | Compare last two runs |
| `make -f Makefile.validation clean` | Remove old results |

## Reproducibility

Every run records:
- **Git commit SHA** — exact code version
- **Kernel version** — OS environment
- **TCP congestion control** — network behavior
- **Random seed** — for bootstrap CI reproducibility
- **Hypothesis version** — for property test reproducibility

To reproduce a specific run:

```bash
git checkout <commit-sha>
make -f Makefile.validation validate
# Compare results with original run
```

## CI Integration

Add to `.github/workflows/ci.yml`:

```yaml
- name: Run Validation
  run: make -f Makefile.validation validate

- name: Upload Results
  uses: actions/upload-artifact@v4
  with:
    name: validation-results
    path: results/
```

## What Validated

| Check | What It Verifies |
|:------|:-----------------|
| **Meta-tests (16)** | Framework self-consistency |
| **Property tests** | Invariants hold across random inputs |
| **Latency baseline** | Network characteristics |
| **SLA evaluation** | Metrics vs thresholds |

## Limitations

This validation does NOT prove:
- Security or anonymity
- Censorship resistance
- Production readiness for N > 100 nodes
- Scalability beyond tested topology

It DOES verify:
- Measurement methodology is sound
- Statistics are correctly computed
- Regression detection works
- Invariant definitions are complete
