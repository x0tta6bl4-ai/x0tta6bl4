# x0tta6bl4 Roadmap

**Version:** 3.4.0  
**Last Updated:** 2026-02-27  
**Status:** Pre-Production (Release Hardening + Pilot Preparation)

> **Canonical source of truth:** this file + [`plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md`](plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md)

---

## Source Precedence (When Files Conflict)

1. **Release gate truth:** [`plans/MASTER_100_READINESS_TODOS_2026-02-26.md`](plans/MASTER_100_READINESS_TODOS_2026-02-26.md)
2. **Execution truth:** [`plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`](plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md)
3. **Domain/capability plans:** MaaS, SPIFFE/SPIRE, Mesh-FL, Tech Debt plans
4. **Informational snapshots:** `docs/STATUS.md`, grant/action docs
5. **Historical only:** `docs/archive/**`

---

## Current State (As Of 2026-02-27)

- `quick` smoke gate: **PASS (11/11)**
- `full` smoke gate: **PASS (22/22)**
- Nightly lanes split: `full-core` + `full-heavy`
- Nightly duration guardrails: enabled (`PASS/WARN/FAIL` status in summary)
- Product capability: broad feature set implemented
- Primary risk: open P0/P1 readiness backlog before production go-live

---

## Live Initiative Table

| Initiative | Status | Next Milestone | Target Date | Main Blocker |
|---|---|---|---|---|
| Release readiness (P0/P1) | In Progress | Close top P0 items | 2026-03-08 | Open API/DB/security hardening tasks |
| Golden smoke pre-merge | Operational | Keep green on all merges | Ongoing | None |
| Nightly smoke + guardrails | Operational | Build 2-week runtime baseline | 2026-03-13 | No trend baseline yet |
| MaaS pivot feature scope | Complete | Pilot hardening + onboarding | 2026-03-15 | Go-to-market execution |
| MaaS W10-W12 sprint | In Progress | Finish multi-arch + dependabot | 2026-03-15 | CI/container backlog |
| CI security governance | In Progress | Enforce required checks on `main` | 2026-03-01 | Branch protection finalization |
| SPIFFE/SPIRE integration | Complete | Scheduled staging re-validation | 2026-03-10 | Evidence cadence |
| Mesh-FL + consensus quality | In Progress | Close remaining P1 quality/perf items | 2026-03-15 | Technical debt |
| Tech debt program | In Progress | Close open TD-006/007/008 | 2026-03-31 | Capacity vs priorities |
| Revenue readiness | In Progress | Convert to paid pilots | 2026-04-25 | Sales pipeline and contracts |

---

## Milestones

| Milestone | Date | Exit Criteria |
|---|---|---|
| Readiness stabilization checkpoint | 2026-03-08 | Top P0 readiness items closed + smoke stable |
| W12 engineering completion | 2026-03-15 | Multi-arch/dependabot + P1 hardening done |
| Pilot launch window (paid) | 2026-03-25 to 2026-04-25 | Customer onboarding + billing + SLA runbooks |
| MRR stabilization window | 2026-05-01 to 2026-06-30 | Repeatable conversion from pilot to subscription |

---

## Related Documents

| Document | Role |
|---|---|
| [`plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md`](plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md) | Canonical live status table |
| [`plans/MASTER_100_READINESS_TODOS_2026-02-26.md`](plans/MASTER_100_READINESS_TODOS_2026-02-26.md) | Release gating checklist |
| [`plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`](plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md) | Current execution sequencing |
| [`plans/MAAS_DEVELOPMENT_PLAN_W10_W12.md`](plans/MAAS_DEVELOPMENT_PLAN_W10_W12.md) | Current MaaS sprint roadmap |
| [`plans/MAAS_PIVOT_EXECUTION_TODO.md`](plans/MAAS_PIVOT_EXECUTION_TODO.md) | Product pivot completion map |
| [`docs/roadmap.md`](docs/roadmap.md) | Documentation entrypoint redirect |

---

## Update Cadence

- Weekly: live status sync in canonical table file
- Bi-weekly: milestone and blocker review
- Monthly: roadmap version bump and priority reset
