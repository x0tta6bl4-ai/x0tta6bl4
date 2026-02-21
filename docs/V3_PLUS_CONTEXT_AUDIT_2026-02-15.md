# V3+ Context Audit (2026-02-15)

## Scope

Deep version-context audit for `x0tta6bl4` v3+ after baseline sync pass.

## Release channels detected

| Channel | Evidence | State |
| --- | --- | --- |
| Stable | `VERSION=3.2.1`, git tag `v3.2.1` | Active |
| RC | `CHANGELOG.md` contains `3.3.0-rc1` | Documented |
| Alpha/experimental | scattered `v3.4` references | Mixed |

Primary release tags present in repo:
- `v3.0.0`
- `v3.2.0`
- `v3.2.1`

## What is already synchronized to 3.2.1

- Runtime/API surface:
  - `libx0t/core/app.py`
  - `libx0t/core/health.py`
  - `libx0t/core/health_check.py`
  - `libx0t/core/status_collector.py`
- Container build/deploy:
  - `Dockerfile.app`
  - `Dockerfile.production`
  - `Dockerfile.healing`
- Docs:
  - `docs/api/openapi.yaml`
  - `docs/DEMO_SCRIPT.md`
  - `docs/operations/OPERATIONS_GUIDE.md`
- Version tooling:
  - `scripts/sync_version.py` expanded to multi-target sync
  - fixed pyproject regex to avoid touching `minversion`

## Remaining version gaps (v3+)

### P0 - API/observability semantic drift

1. V3 endpoints report `3.0.0`:
   - `src/api/v3_endpoints.py:99`

2. V3 metrics info reports `3.0.0`:
   - `src/monitoring/v3_metrics.py:112`

3. ML package version advertises `3.3.0`:
   - `src/ml/__init__.py:114`

4. Production-simple Dockerfile still `3.4.0`:
   - `Dockerfile.production-simple:6`
   - `Dockerfile.production-simple:31`

5. Runtime log strings mark MaaS as `v3.4-alpha`:
   - `libx0t/core/app.py:153`
   - `libx0t/core/app.py:157`

### P1 - tests hardcoded to legacy version contracts

If runtime versions are unified further, these tests will need updates:
- `tests/integration/test_v3_api.py:47` expects `3.0.0`
- `tests/unit/api/test_v3_endpoints_unit.py:27` expects `3.0.0`
- `tests/core/test_health_check.py:224` expects `3.0.0`
- `tests/unit/core/test_health.py:39` expects `2.0.0`
- `tests/unit/core/test_health.py:57` expects `3.4.0`

## Strengths observed

- Clear tagged stable line up to `v3.2.1`.
- Production baseline now coherent across major runtime/container/docs files.
- Sync automation significantly improved; dry-run now clean for configured targets.
- Core runtime health/status paths now read `3.2.1` via env-aware defaults.

## Recommended next patch set

1. Decide explicit policy for `v3` API semantic version field:
   - keep as component epoch (`3.0.0`) or align to release (`3.2.1`)
2. If aligned, update coupled tests listed above in one atomic patch.
3. Either:
   - mark `Dockerfile.production-simple` as experimental, or
   - sync it to stable channel.
