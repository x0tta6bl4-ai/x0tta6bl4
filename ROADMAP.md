# x0tta6bl4 Roadmap

**Version:** 3.5.0
**Last Updated:** 2026-06-26
**Status:** Pre-Production (Release Hardening)

## Current State (As Of 2026-06-26)

### ✅ Completed (this session, June 26)

| Area | Detail |
|:-----|:-------|
| **Tech debt** | `__init__.py` 930→0, `from __future__ import annotations` 100%, subprocess safety 200+→0 |
| **subprocess hardening** | All `subprocess.run()` → `safe_run()` (54 files), `Popen` → `safe_popen` (3 calls) |
| **Allowlist** | 65 commands across both validators, `sudo`/`sysctl`/`iptables`/`nft`/`pgrep`/`ethtool` added |
| **Dead code** | `charter_client.py` deleted, `algorithm_update.py` deduped |
| **CVE patching** | yt-dlp: CVE-2026-26331 fixed, starlette 0.52.1→1.3.1 (5 CVEs), PyJWT 2.12.0→2.13.0 (5 CVEs) |
| **Import fix** | `_legacy/__init__.py` shadow bug resolved |
| **PRs closed** | #156 (docs cleanup), #155 (refactor — superseded) |
| **CI** | Green Baseline ✅, CodeQL ✅, `import src` ✅ |
| **Git hygiene** | 27 old stashes dropped, .gitignore extended, 92 untracked files handled |

### Remaining Tech Debt

| Category | Status | Priority |
|:---------|:------:|:---------|
| CVE/dependabot (~40 alerts) | 🟡 Pending rescan after starlette/PyJWT bump | High |
| 68 files > 1000 lines refactor | 🟡 Low risk — active code | Low |
| 14 diverged libx0t vs src/network files | 🟡 Both versions live | Low |
| 199 suppressed lints | 🟢 All intentional (shims, lazy imports, defensive) | None |
| 14 wildcard imports | 🟢 All re-export shims for BC | None |

## Next Milestones (v3.5.0 → Production)

### Phase 1: Dependency Security (Days 1-3)
- [x] yt-dlp: CVE-2026-26331
- [x] starlette 0.52.1→1.3.1 (+5 CVEs patched)
- [x] PyJWT 2.12.0→2.13.0 (+5 CVEs patched)
- [ ] Verify dependabot rescan results (pending GitHub schedule)
- [ ] Fix remaining high-severity CVEs if any

### Phase 2: Infrastructure (Week 1-2)
- [ ] Deploy HashiCorp Vault (HA, 3 replicas, Raft, KMS) — config ready
- [ ] Wire sealed secrets for production K8s
- [ ] Run Stripe e2e tests
- [ ] Validate Ghost Transport deployment

### Phase 3: Visibility & Release (Week 2-3)
- [ ] Bump VERSION → v3.5.0
- [ ] Release notes
- [ ] Portfolio/README update for job search
- [ ] Open source outreach (issues, discussions)

## Constraints

- **Zero budget** — solo developer under sanctions (Crimea)
- **No cloud infra available** — Vault, Stripe, K8s require external infrastructure
- **Target:** survival infrastructure for sanctioned people, journalists, activists
