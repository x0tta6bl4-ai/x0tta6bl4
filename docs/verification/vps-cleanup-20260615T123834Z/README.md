# VPS Cleanup Artifact — 20260615T123834Z

## Status: ✅ CLEANED

### Disk Usage Before/After

| Metric | Before | After | Freed |
|--------|--------|-------|-------|
| Used | 33G (88%) | 31G (83%) | 2G |
| Free | 4.8G | 6.5G | +1.7G |

### What Was Cleaned

1. **android-sdk/** — 148M (Android SDK, not needed for server)
2. **archives/personal/** — 130M (old personal archives)
3. **archive/** — 5.1M (old docs/roadmaps)
4. **artifacts/** — 51M (old artifacts, testdb, etc)
5. **backup-20260410-090811/** — 2.5M (old backup from April)
6. **build/** — 1.1M (old build artifacts)
7. **site/** — 2.7M (old mkdocs site)
8. **deploy_bundle.tar.gz** — deployment bundle archive
9. **другие проекты.zip** — zip archive of other projects
10. **go-build-cache/** — Go build cache
11. **go-mod-cache/** — Go module cache (large)
12. **dao/contracts/node_modules/** — Node.js dependencies (large)
13. **\_\_pycache\_\_/** — Python cache directories
14. **\*.pyc** — Python compiled files
15. **.pytest_cache/** — Pytest cache
16. **.mypy_cache/** — Mypy cache
17. **.ruff_cache/** — Ruff cache

### What Was Preserved

- `src/` — Core application code (474M)
- `security/` — Security tools (549M)
- `venv/` — Python virtual environment (120M)
- `tests/` — Test files (43M)
- `scripts/` — Operations scripts (5.9M)
- `ebpf/` — eBPF tools (16M)
- `docs/` — Documentation (9.2M)

### Verification

- App health: HTTP 200 OK
- Version: 3.4.0
- Services: All running (app, Open5GS, x402 API)

### Artifacts

- This document: `docs/verification/vps-cleanup-20260615T123834Z/README.md`
