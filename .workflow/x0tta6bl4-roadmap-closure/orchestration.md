# Orchestration: x0tta6bl4 roadmap closure

## Execution Rules

- Keep the original objective intact.
- Ask for approval before risky, expensive, external, or destructive actions.
- Keep immediate blocking work local.
- Delegate only bounded, disjoint, materially useful packets.
- Integrate packet results before final verification.

## Branching Rules

1. Start every tranche with current-state inspection:
   - `python3 scripts/gitmark_memory_bank.py context "<topic>" --limit 10`
   - `python3 scripts/ops/summarize_dirty_worktree_review.py --json`
   - focused `git diff -- <packet-files>`
2. Prefer packages already listed by the dirty-worktree owner review.
3. If a task requires external/user action, create a safe operator handoff and
   do not mark the task complete.
4. If a task requires production writes or outreach, stop at the approval gate.
5. After implementation, run the smallest check that proves the exact package,
   then broaden only if the blast radius requires it.
6. Update this workflow's state/result notes before ending a tranche.

## Packet Prompts

### Packet: security_identity_runtime

Objective: verify the PQC compatibility refactor and prevent regressions in
legacy import behavior.

Files:
- `src/libx0t/security/post_quantum.py`
- `src/libx0t/security/pqc_core.py`
- `src/security/pqc/compat.py`
- `tests/unit/security/test_pqc_compat_unit.py`

Do: run compile plus focused tests; fix only compatibility/import behavior.
Do not: restore duplicated legacy implementations or weaken fail-closed
availability checks.

### Packet: maas_api_compat

Objective: verify MaaS governance endpoint signature/type cleanup.

Files:
- `src/api/maas/endpoints/governance.py`

Do: compile the endpoint and run package compatibility tests.
Do not: change route behavior, auth semantics, or database models in this
packet.

### Packet: ghost_access_revenue_pilot

Objective: make the first paid reliability pilot executable without secrets.

Files:
- `plans/REVENUE_USEFULNESS_SPRINT_2026-05-31.md`
- `docs/ghost-access/reliability-pilot-*`
- `docs/templates/GHOST_ACCESS_*`

Do: keep buyer-facing scripts, tracker fields, payment handoff, daily summary,
and incident note templates aligned.
Do not: send outreach, claim payment, or store private contact/payment data.

### Packet: nl_runtime_diagnostics

Objective: keep redacted NL/Ghost Access evidence reviewable.

Files:
- `nl-diagnostics/*`
- `nl-diagnostics/incidents/`

Do: run service compile/tests and confirm redaction boundaries.
Do not: restart or mutate NL production services.

### Packet: repo_coordination_mcp

Objective: keep Codex/MCP local tooling and dirty-worktree ownership gates
reproducible.

Files:
- `docs/team/swarm_ownership.json`
- `pyproject.toml`
- `requirements.txt`
- `scripts/verify_codex_environment.py`
- `mcp-server/*`
- `tests/unit/test_spb_readonly_tools.py`

Do: validate ownership JSON, coordination contract, dependency metadata,
targeted MCP tests, and fast local MCP/skills/agents verifier.
Do not: enable GitHub MCP without a locally valid token or paste tokens into
chat.

### Packet: repo_hygiene_config

Objective: keep dependency manifests and Ghost Access operator templates
installable, reviewable, and no-secret by default.

Files:
- `pyproject.toml`
- `requirements.txt`
- `docs/templates/GHOST_ACCESS_DAILY_HEALTH_SUMMARY_TEMPLATE.md`
- `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`
- `tests/unit/security/test_dependency_security_pins_unit.py`

Do: verify `pyproject.toml` dependencies are satisfiable by
`requirements.txt`, refresh editable metadata only with `--no-deps`, and check
template privacy sections.
Do not: delete generated metadata directories, run a broad dependency upgrade,
mutate production services, or send outreach/payment messages.

### Packet: commercial_income_automation

Objective: verify paid-task, non-bounty income, and commercial MaaS static
contracts without making external submissions or money claims.

Files:
- `src/sales/`
- `scripts/ops/*paid*.py`
- `scripts/ops/*income*.py`
- `scripts/ops/check_commercial_mesh_platform_readiness.py`
- `tests/unit/sales/`
- relevant `tests/unit/scripts/test_*paid*`, `test_*income*`, and
  `test_check_commercial_mesh_platform_readiness.py`

Do: compile commercial scripts, run focused sales/script tests, build local
commercial artifacts, verify static readiness, and use
`run_income_watch_cycle.py --offline` for approval-free validation.
Do not: submit to external marketplaces, charge buyers, register listings,
query private wallet evidence as a success claim, or claim received funds
without confirmed wallet/platform evidence.

### Packet: evidence_readiness

Objective: verify current architecture/evidence maps and the local
real-readiness gate without promoting production/customer claims.

Files:
- `docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json`
- `docs/architecture/CURRENT_NAMESPACE_CONVERGENCE_MAP.json`
- `docs/architecture/CURRENT_CROSS_LAYER_LINK_MAP.md`
- `scripts/ops/check_real_readiness.py`
- related `scripts/ops/verify_*` evidence scripts
- `src/api/maas/endpoints/governance.py`

Do: parse JSON maps, compile changed verifier scripts, run focused evidence
tests, fix local import/type blockers, and run
`scripts/ops/check_real_readiness.py --json --skip-git-check`.
Do not: treat `REAL_READINESS_READY` as proof of live customer traffic,
external DPI bypass, settlement finality, or production SLOs.

### Packet: coordination_product_readiness

Objective: verify local agent coordination scripts and registered product
packages without promoting production runtime claims.

Files:
- `docs/team/swarm_ownership.json`
- `docs/agent-engineering/`
- `products/agent-work-receipt-gate/`
- `products/security-gates/`
- `products/production-readiness.json`
- `scripts/agents/*`
- `templates/security/`
- `tests/unit/scripts/test_agent_work_receipt_gate.py`
- `tests/unit/scripts/test_security_scan_template_unit.py`

Do: validate ownership JSON, compile agent scripts, run safe local agent smoke
tests, run focused product tests, and run product readiness verifiers.
Do not: run destructive agents, apply Kubernetes chaos experiments, publish a
product, send outreach, or claim external runtime production readiness.

### Packet: coordination_agent_suite

Objective: verify the local coordination agent suite and current
policy/evidence map source references without sweeping unrelated architecture
maps.

Files:
- `docs/team/swarm_ownership.json`
- `scripts/agent-coord.sh`
- `scripts/agents/`
- `.githooks/pre-commit`
- `.githooks/post-commit`
- `docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json`
- `docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json`
- focused coordination, policy-map, and evidence-map tests

Do: validate ownership JSON, coordination contract, safe agent smoke tests,
shell/JSON parsing, focused policy/evidence unit guards, and dirty-worktree
owner gate.
Do not: run destructive agents, production writes, outreach, broad staging, or
claim production runtime readiness from local coordination smoke tests.

### Packet: runbook_pilot_edge_mesh_lab

Objective: verify the Pilot 1 Edge Mesh Lab operator handoff and its local
Pilot 0 baseline without executing a real lab-node run.

Files:
- `docs/runbooks/README.md`
- `docs/runbooks/PILOT1_EDGE_MESH_LAB.md`
- `config/chaos_agent.json`
- `scripts/ops/run_pilot0_edge_mesh_maas.py`
- `scripts/agents/chaos_engineer_agent.py`

Do: link-check the runbook index, scan for secrets, validate the chaos-agent
config shape, check claim-boundary markers, run chaos report mode, and run the
local Pilot 0 preflight.
Do not: use production VPN listeners, shared customer infrastructure, external
targets, or claim that Pilot 1 has completed without a real lab node evidence
packet.

## Completion Audit

Completion of the persistent user objective is not yet proven. Before marking
the goal complete, enumerate every active roadmap and prove each named item
with current files, command output, tests, runtime evidence, or explicit
operator/user completion records.
