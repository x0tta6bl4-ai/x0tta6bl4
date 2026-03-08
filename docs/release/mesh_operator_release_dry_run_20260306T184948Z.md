# Mesh Operator Release Dry-Run Report

- **Start (UTC):** 2026-03-06T18:49:48Z
- **End (UTC):** 2026-03-06T18:54:57Z
- **Duration:** 309s
- **Overall:** FAIL

| Checkpoint | Status | Duration (s) |
|---|---|---:|
| CP-01 — Toolchain preflight | PASS | 1 |
| CP-02 — Version contract validation | PASS | 0 |
| CP-03 — Mesh operator unit tests | PASS | 5 |
| CP-04 — Fallback image reproducibility | PASS | 64 |
| CP-05 — Helm lint and webhook render | PASS | 0 |
| CP-06 — Git release promotion dry-run | PASS | 0 |
| CP-07 — Kind smoke e2e | PASS | 75 |
| CP-08 — Webhook admission e2e | FAIL | 42 |
| CP-09 — Helm lifecycle e2e | PASS | 48 |
| CP-10 — Canary rollout + rollback e2e | PASS | 74 |
