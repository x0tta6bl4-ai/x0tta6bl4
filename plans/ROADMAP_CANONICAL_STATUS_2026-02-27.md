# x0tta6bl4 Canonical Roadmap Status

**Date:** 2026-02-27 (Last updated: 2026-06-25)  
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
| Release Readiness (P0/P1 gate) | Architect + Dev + QA | ✅ **226/229 — все P0/P1 закрыты** | 3 operational metrics (reopen rate, MTTR, rollback) | Нет продакшн-деплоя для сбора метрик |
| Golden Smoke Pre-Merge | Dev + QA | ✅ **Стабилен** | Keep green | None |
| Nightly Golden Smoke | DevOps | ✅ **Работает** | Duration baseline collected | None |
| MaaS Pivot Scope (Phases 1-5) | Product + Dev | ✅ **Complete** | Harden for pilots | Execution quality, not feature gap |
| **God Object Refactoring** | Core | **9/10 done** | drift_detector.py (922 строк) | 1 оставшийся |
| **CodeQL gates** | Security | **0 critical/high** | Поддерживать | None |
| **requirements.txt cleanup** | Dev | **342→72 deps (-79%)** | Поддерживать | None |
| **Ghost Access Bot** | Ops | **Работает на NL** | 2 пользователя | Мало пользователей |
| **x402 API** | Dev | **Запущен на NL (8120)** | Привлечь пользователей | Продакшн-трафик |
| **First-party VPN** | Ops | **3 сервера на NL** | x0vpns0/1/2 active | None |
| **Revenue Sprint** | GTM | **НЕ ВЫПОЛНЕН** | 0 сообщений, 0 конверсий | Нет аутрич-активности |
| SPIFFE/SPIRE Production Integration | Security + Platform | ✅ **Complete** | Periodic staging validation | None |
| Technical Debt Program | Core + Platform | ✅ **Phase 2 complete** | drift_detector, DI, type hints | Не критично |
| Commercial Readiness To Revenue | Product + GTM | **🟡 Нет прогресса** | Convert technical readiness into paid pilots | GTM pipeline |

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
