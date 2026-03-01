# x0tta6bl4 Canonical Roadmap Status

**Date:** 2026-02-27  
**Purpose:** single live status table to remove roadmap conflicts and keep execution priorities aligned.

## Scope And Method

- Audited all active (non-archive) roadmap/plan/backlog files in `plans/`, root `ROADMAP.md`, and roadmap status entrypoints in `docs/`.
- Ignored `docs/archive/**` and legacy snapshots as non-authoritative history.
- Used latest local repository state as of 2026-02-27.
- Generated machine-audit report: `plans/ROADMAP_AUDIT_2026-02-27.md` using `python3 scripts/audit_roadmaps.py --out plans/ROADMAP_AUDIT_2026-02-27.md`.

## Source Precedence (When Statuses Conflict)

1. **Release Gate Truth:** `plans/MASTER_100_READINESS_TODOS_2026-02-26.md`
2. **Execution Truth:** `plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`
3. **Capability/Domain Truth:** active domain plans (`MAAS_*`, `SPIFFE_*`, `NEXT_PRIORITIES_*`, `TECH_DEBT_*`)
4. **Narrative/Snapshot Docs:** `docs/STATUS.md`, `plans/ACTION_PLAN_NOW.md` (informational, not release gate)
5. **Historical:** any file in `docs/archive/**` and legacy roadmap snapshots

**Canonical entrypoint for roadmap status:** `plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md` (this file).

## Top 10 Initiatives (Live Table)

| Initiative | Owner | Status | Next Milestone | Main Blocker |
|---|---|---|---|---|
| Release Readiness (P0/P1 gate) | Architect + Dev + QA | In Progress | Close top P0 checklist items by 2026-03-08 | Open P0 items in API/DB/security hardening |
| Golden Smoke Pre-Merge | Dev + QA | Operational | Keep quick gate stable each merge | None (currently green) |
| Nightly Golden Smoke (core/heavy + guardrails) | DevOps | Operational | Collect 2 weeks of duration baseline by 2026-03-13 | No historical trend baseline yet |
| MaaS Pivot Scope (Phases 1-5) | Product + Dev | Complete | Sustain and harden for pilots | Execution quality, not feature gap |
| MaaS W10-W12 Delivery | Dev | In Progress | Finish W12 (`multi-arch`, `dependabot`) by 2026-03-15 | Pending CI/container work |
| Security Gates In CI | DevOps + Security | In Progress | Enforce required branch checks on `main` by 2026-03-01 | Branch protection finalization |
| SPIFFE/SPIRE Production Integration | Security + Platform | Complete | Run periodic staging validation cycle | Need scheduled validation evidence |
| Mesh-FL + Swarm Consensus | ML + Core | In Progress | Close remaining P1 quality/perf issues by 2026-03-15 | Code quality/perf debt from review |
| Technical Debt Program | Core + Platform | In Progress | Close open TD items (006/007/008) by 2026-03-31 | Non-critical backlog still open |
| Commercial Readiness To Revenue | Product + GTM | In Progress | Convert technical readiness into paid pilots by 2026-04-25 | GTM pipeline + contracts/onboarding |

## Audited Roadmap/Plan Files (Active Set)

| File | Role | Authority | Current State |
|---|---|---|---|
| `plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md` | Canonical roadmap entrypoint | Authoritative | This file |
| `plans/ROADMAP_AUDIT_2026-02-27.md` | Automated consistency audit | Supporting | Generated matrix of status/checklist conflicts |
| `docs/roadmap.md` | Docs redirect/hub | Authoritative entrypoint | Redirects to tracked canonical file in `plans/` |
| `ROADMAP.md` | Local mirror | Informational | May be excluded from repository tracking |
| `docs/STATUS.md` | Capability snapshot | Informational | Strong claims; not release gate source |
| `docs/05-operations/project-status-report.md` | Legacy snapshot | Historical | Explicitly non-authoritative for current release |
| `plans/MASTER_100_READINESS_TODOS_2026-02-26.md` | Release readiness gate | Highest | Large P0/P1 backlog still open |
| `plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md` | Operational execution backlog | High | Mostly complete, some infra tasks open |
| `plans/MAAS_DEVELOPMENT_PLAN_W10_W12.md` | MaaS sprint roadmap | High | W10/W11 done, W12 pending items |
| `plans/MAAS_PIVOT_EXECUTION_TODO.md` | Product pivot roadmap | High | Feature roadmap complete; release-hardening active |
| `plans/NEXT_PRIORITIES_MESH_FL.md` | Mesh/FL priorities | Medium | P0 resolved; P1/P2 improvements remain |
| `plans/SPIFFE_SPIRE_INTEGRATION_PLAN.md` | Security/identity track | Medium | Subsystem production-capable; platform release-gated |
| `plans/TECH_DEBT_ELIMINATION_PLAN_2026-02-16.md` | Security debt elimination | Medium | P0-P2 security marked done, residual tasks open |
| `plans/TECH_DEBT_ROADMAP.md` | Long-term debt roadmap | Medium | Phased debt plan active |
| `plans/EBPF_INTEGRATION_NEXT_STEPS.md` | eBPF next steps | Medium | Baseline done, improvements planned |
| `plans/GOD_OBJECTS_REFACTORING_PLAN.md` | Refactor campaign | Medium | Marked complete |
| `plans/kimi_k2.5_integration_roadmap.md` | Research/AI roadmap | Planned | Mostly checklist/planning stage |
| `plans/parl_implementation_plan.md` | PARL plan | Planned | Design/implementation plan |
| `plans/vision_debugging_system.md` | Vision subsystem plan | Planned | Design/system plan |
| `plans/ACTION_PLAN_NOW.md` | Time-boxed action plan | Informational | Grant-era execution snapshot |
| `plans/ФСИ_ГРАНТЫ_ПЛАН_Q1_Q2_2026.md` | Grant timeline | Informational | Program timeline oriented |
| `plans/НИОКР_ОПИСАНИЕ_ДЛЯ_ГРАНТА.md` | R&D narrative | Informational | Grant evidence, not release gate |

## Conflict Resolution Decisions Applied

- Conflicting "100% ready" and "open critical backlog" statements are resolved in favor of `MASTER_100_READINESS...`.
- Any roadmap-like file with global readiness claims must include release-gate caveat in the header section.
- Domain plans may remain optimistic for their subsystem; release decision is always gated by readiness checklist + smoke/CI gates.
- Any future roadmap update must update:
  - this file
  - `docs/roadmap.md`
  - and (if relevant) `MASTER_100_READINESS_TODOS_2026-02-26.md`
