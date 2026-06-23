# x0tta6bl4 roadmap closure

## Goal

Move the persistent objective forward: close x0tta6bl4 roadmap tasks across
the active project roadmaps in reviewable, evidence-backed packets.

This run does not redefine completion as a small subset. It records the current
safe tranche and keeps the broader goal active until every roadmap item has
authoritative completion evidence.

## Success Criteria

- Current roadmap sources are refreshed from the worktree, not memory.
- Each tranche has a bounded package, owner, files, and checks.
- No NL production VPN service is mutated without explicit approval.
- Local code packets are either verified or left with exact failing checks.
- Commercial Ghost Access pilot tasks are moved forward only with safe,
  no-secret operator artifacts.
- Real-readiness, release, customer-traffic, settlement, and production claims
  remain behind their existing proof gates.

## Current Context

- Branch: `sync-main-20260529`, ahead of origin.
- Dirty worktree inventory at start of tranche: 28 paths; unowned paths: 0.
- Dirty worktree inventory after the coordination/MCP follow-up: 81 paths;
  unowned paths: 0; owner review gate: `DIRTY_WORKTREE_OWNER_REVIEW_READY`.
- Current real-readiness gate after the evidence package: `REAL_READINESS_READY`;
  95 checks passed, 0 failed, 0 warnings.
- Registered repo-local product readiness after the coordination product
  package: `ALL_REGISTERED_PRODUCTS_READY`; 2/2 products passed.
- Pilot 1 Edge Mesh Lab runbook is indexed, link-checked, secret-scanned, and
  backed by a fresh local Pilot 0 baseline:
  `PILOT0_EDGE_MESH_MAAS_READY`.
- Repo hygiene config package is locally checked: project dependencies are
  installable over the `requirements.txt` lock, Ghost Access operator
  templates pass the privacy policy check, and the local editable metadata was
  refreshed without dependency installation.
- Dirty worktree inventory after the repo hygiene package: 87 paths; unowned
  paths: 0; owner review gate: `DIRTY_WORKTREE_OWNER_REVIEW_READY`.
- Commercial income automation package is locally checked: static commercial
  contract is ready, paid-task/non-bounty artifacts build under `.tmp`,
  commercial tests pass, and income-watch now has an approval-free offline
  verifier.
- Dirty worktree inventory after the commercial package: 90 paths; unowned
  paths: 0; owner review gate: `DIRTY_WORKTREE_OWNER_REVIEW_READY`.
- Coordination agent suite follow-up is locally checked: coordination contract,
  agent compile/smoke, shell/JSON parsing, and focused policy/evidence map
  tests pass after stale `nodes.py` references were refreshed in the current
  policy/evidence maps.
- Dirty worktree inventory after the coordination agent suite follow-up:
  92 paths; unowned paths: 0; owner review gate:
  `DIRTY_WORKTREE_OWNER_REVIEW_READY`.
- Active short-term commercial roadmap: Ghost Access Reliability Pilot.
- Technical gates in force: `STATUS_REALITY.md`,
  `docs/05-operations/REAL_READINESS_GATE.md`,
  `docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md`,
  `docs/verification/release-gate-v1.1.md`.
- First-party VPN is local/staging-ready but production apply remains
  approval-blocked.
- Horizon-2 decentralized RAG remains deferred until live validation gaps are
  re-evaluated.

## Constraints

- Do not use `git add -A`, `git add .`, or broad commits.
- Do not revert unrelated dirty worktree changes.
- Do not collect or store secrets, raw subscription links, UUIDs, private keys,
  QR codes, bot tokens, or personal payment data.
- Do not stop, disable, mask, kill, or mutate `x-ui.service`, `xray`,
  `ghost-access-*`, or NL VPN listeners without explicit current approval.
- Use `--no-cov` for focused pytest runs when the global coverage gate would
  make unrelated narrow checks fail.

## Risks

- Roadmaps contain older aspirational "production ready" wording that is
  superseded by current reality gates.
- Dirty worktree packets span docs, VPN diagnostics, security compatibility,
  MaaS API compatibility, and eBPF runtime.
- Outreach/payment tasks require human/operator action and cannot be honestly
  marked complete by local code alone.
- External production, customer traffic, settlement, DPI, and uptime claims
  require separate evidence artifacts.

## Approval Required

- Any NL production write, deploy, restart, listener change, or service apply.
- Any outbound outreach, message sending, payment request, invoice, post, or
  publication.
- Any destructive git or filesystem operation.
- Any mass refactor or cross-package staging.

## Work Packets

1. `security_identity_runtime`
   - Files: `src/libx0t/security/post_quantum.py`,
     `src/libx0t/security/pqc_core.py`, `src/security/pqc/compat.py`,
     `tests/unit/security/test_pqc_compat_unit.py`.
   - Purpose: close PQC compatibility/import drift without resurrecting the
     old top-level implementation.
   - Status: verified locally in this run; shim monkeypatch regression fixed
     and the full security suite now passes.

2. `maas_api_compat`
   - File: `src/api/maas/endpoints/governance.py`.
   - Purpose: tighten endpoint type compatibility around MaaS governance.
   - Status: focused compile and package compatibility test passed locally.

3. `network_runtime`
   - File: `src/network/ebpf/x0tta6bl4_pulse.bpf.c`.
   - Purpose: review checksum/TTL cleanup against eBPF runtime roadmap.
   - Status: Python-side first-party network compile checks passed; changed BPF
     C file compiles locally to `/tmp/x0tta6bl4_pulse.bpf.o`.

4. `ghost_access_revenue_pilot`
   - Files: `plans/REVENUE_USEFULNESS_SPRINT_2026-05-31.md`,
     `docs/ghost-access/*reliability-pilot*`,
     `docs/templates/GHOST_ACCESS_*`.
   - Purpose: make the 7-day paid reliability pilot executable without
     collecting secrets.
   - Status: docs are locally consistency-checked; local links are valid,
     price bands are aligned, no-secret scan is clean, and actual Day 1
     outreach remains operator action.

5. `nl_runtime_diagnostics`
   - Files: `nl-diagnostics/*` and `nl-diagnostics/incidents/`.
   - Purpose: keep redacted production-adjacent evidence current.
   - Status: verified locally with read-only checks; JSON evidence parses,
     service-side NL tests pass, diagnostics builder tests pass, redaction scan
     is clean, and incident notes now have a README clarifying that historical
     commands are not current execution authorization.

6. `repo_coordination_mcp`
   - Files: `docs/team/swarm_ownership.json`, `pyproject.toml`,
     `requirements.txt`, `scripts/verify_codex_environment.py`,
     `scripts/mcp/github_mcp_stdio.sh`, `mcp-server/*`, and
     `tests/unit/test_spb_readonly_tools.py`.
   - Purpose: make local MCP/operator tooling reviewable and reproducible.
   - Status: owner map is current, `mcp` dependency is recorded, and fast
     Codex/MCP environment checks pass locally.

7. `evidence_readiness`
   - Files: `docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json`,
     `docs/architecture/CURRENT_NAMESPACE_CONVERGENCE_MAP.json`,
     `docs/architecture/CURRENT_CROSS_LAYER_LINK_MAP.md`,
     `scripts/ops/check_real_readiness.py`, related evidence verifier scripts,
     and `src/api/maas/endpoints/governance.py`.
   - Purpose: verify the current evidence maps and local real-readiness gate
     after the MaaS governance import/signature issue was fixed.
   - Status: local script compile, architecture-map JSON parse, focused
     evidence tests, MaaS governance tests, individual runtime smoke verifiers,
     and the full `check_real_readiness.py --json --skip-git-check` gate pass
     locally. The gate decision is `REAL_READINESS_READY`, with 95/95 checks
     passing.

8. `coordination_product_readiness`
   - Files: `docs/team/swarm_ownership.json`, `docs/agent-engineering/`,
     `products/agent-work-receipt-gate/`, `products/security-gates/`,
     `products/production-readiness.json`, `scripts/agents/*`,
     `templates/security/`, and focused unit tests.
   - Purpose: make agent coordination and the registered product packages
     locally install-ready without overclaiming production runtime status.
   - Status: coordination contract passes, 8/8 local agents pass their smoke
     runner, Agent Work Receipt Gate is `READY_FOR_CLIENT_REPO_INSTALL`,
     Security Gates is `READY_FOR_CLIENT_REPO_INSTALL`, and the product
     registry is `ALL_REGISTERED_PRODUCTS_READY`.

9. `runbook_pilot_edge_mesh_lab`
   - Files: `docs/runbooks/README.md`,
     `docs/runbooks/PILOT1_EDGE_MESH_LAB.md`, `config/chaos_agent.json`,
     `scripts/ops/run_pilot0_edge_mesh_maas.py`, and
     `scripts/agents/chaos_engineer_agent.py`.
   - Purpose: make the Pilot 1 lab-node handoff reviewable while keeping the
     actual lab-node run behind operator control and claim boundaries.
   - Status: runbook links, secret scan, config schema, claim-boundary markers,
     chaos config report mode, and local Pilot 0 preflight baseline pass.

10. `repo_hygiene_config`
   - Files: `pyproject.toml`, `requirements.txt`,
     `docs/templates/GHOST_ACCESS_DAILY_HEALTH_SUMMARY_TEMPLATE.md`,
     `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`, and
     `tests/unit/security/test_dependency_security_pins_unit.py`.
   - Purpose: keep dependency manifests and Ghost Access operator templates
     installable, reviewable, and no-secret by default.
   - Status: dependency manifest test passes, pyproject-vs-requirements
     installability passes, Ghost Access template policy passes, editable
     metadata was refreshed with `--no-deps`, and local FastAPI/Starlette were
     restored to the lock-file versions. The broad `pip check` still reports
     unrelated local environment drift.

11. `commercial_income_automation`
   - Files: `src/sales/`, paid/income scripts under `scripts/ops/`, commercial
     readiness verifier scripts, and focused sales/script tests.
   - Purpose: make paid-task and non-bounty income automation locally
     reproducible while keeping real submissions, buyer charging, wallet
     probing, funds-received claims, and settlement claims behind operator
     approval/evidence.
   - Status: commercial compile passes, main commercial tests pass
     (`192 passed`), extra commercial script tests pass (`9 passed`), static
     commercial readiness is `COMMERCIAL_MESH_PLATFORM_STATIC_CONTRACT_READY`,
     local paid-task/non-bounty artifacts build, and offline income-watch
     validation passes without external probes.

12. `coordination_agent_suite`
   - Files: `docs/team/swarm_ownership.json`, `scripts/agent-coord.sh`,
     `scripts/agents/`, `.githooks/pre-commit`, `.githooks/post-commit`,
     `docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json`,
     `docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json`, and focused
     coordination/policy/evidence tests.
   - Purpose: verify the local coordination agent suite and refresh stale
     policy/evidence source references that block current guards.
   - Status: coordination contract, agent compile/smoke, shell/JSON parsing,
     focused unit tests, and owner gate pass locally. The post-fix broad
     real-readiness rerun did not complete in this tranche; the previous
     evidence-readiness `REAL_READINESS_READY` result remains recorded.

## Integration Policy

- Accept only changes that improve the requested roadmap end state and have
  matched checks or clear operator handoff boundaries.
- Keep local evidence distinct from production/customer proof.
- Preserve concurrent work and do not rewrite another package to make this
  tranche look cleaner.
- Record skipped checks with a concrete reason and next command.

## Verification

Completed in this run:

- `find src/security src/libx0t/security -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/security/test_pqc_compat_unit.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/security/test_post_quantum_unit.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/security/test_hybrid_tls_demo.py::test_handshake_performance_sla -q --no-cov`
- `python3 -m py_compile src/api/maas/endpoints/governance.py src/api/maas_auth.py src/api/maas_legacy.py src/api/maas_compat.py src/api/maas_billing.py`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_package_compat_unit.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_compat_* tests/unit/api/test_maas_legacy_* -q --no-cov`
- `python3 -m py_compile src/network/transport/ghost_pulse_transport.py src/network/firstparty_vpn/*.py`
- `clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c src/network/ebpf/x0tta6bl4_pulse.bpf.c -o /tmp/x0tta6bl4_pulse.bpf.o`
- `python3 -m json.tool docs/team/swarm_ownership.json >/dev/null`
- `bash scripts/agents/check_coordination_contract.sh`
- `python3 -m py_compile scripts/verify_codex_environment.py`
- `bash -n scripts/mcp/github_mcp_stdio.sh`
- `python3 -c "import pathlib, tomllib; tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print('pyproject: ok')"`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/test_spb_readonly_tools.py mcp-server/test_operator_tools.py -q --no-cov`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json`
- `python3 scripts/verify_codex_environment.py --skip-slow-mcp`
- `find services/nl-server -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile`
- `PYTHONPATH=. ./.venv/bin/pytest services/nl-server/tests -q --no-cov`
- `python3 -m json.tool <each dirty nl-diagnostics JSON file> >/dev/null`
- `PYTHONPATH=. ./.venv/bin/pytest nl-diagnostics/test_*.py -q --no-cov`
- inline redaction scan over dirty `nl-diagnostics` JSON files and
  `nl-diagnostics/incidents/*.note`
- local link check across Ghost Access reliability pilot docs and templates
- placeholder/price-band scan across Ghost Access reliability pilot docs
- no-secret scan across Ghost Access reliability pilot docs and templates
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/security tests/security -q --no-cov`
- `python3 -m py_compile scripts/ops/check_real_readiness.py scripts/ops/summarize_dirty_worktree_review.py scripts/ops/verify_traffic_delivery_operator_flow.py scripts/ops/run_measured_attestation_verifier_handoff.py scripts/ops/verify_measured_attestation_verifier_smoke.py scripts/ops/verify_measured_attestation_verifier_smoke_artifact.py`
- `python3 -m json.tool docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json >/dev/null`
- `python3 -m json.tool docs/architecture/CURRENT_NAMESPACE_CONVERGENCE_MAP.json >/dev/null`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_check_real_readiness_unit.py tests/unit/scripts/test_summarize_dirty_worktree_review.py tests/unit/scripts/test_verify_traffic_delivery_operator_flow.py tests/unit/scripts/test_run_measured_attestation_verifier_handoff.py tests/unit/scripts/test_verify_measured_attestation_verifier_smoke.py tests/unit/scripts/test_verify_measured_attestation_verifier_smoke_artifact.py tests/unit/test_real_readiness_gate_doc_unit.py tests/unit/test_cross_plane_evidence_map_unit.py tests/unit/test_autonomous_mesh_reality_map_unit.py -q --no-cov`
- `python3 -m py_compile src/api/maas/endpoints/governance.py`
- `PYTHONPATH=. ./.venv/bin/python -c "import src.core.app; print('app_import_ok')"`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_governance_evidence_unit.py tests/api/test_maas_governance.py tests/api/test_maas_governance_edge.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/verify_safe_actuator_runtime_metadata_retention.py --require-retained --json`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/verify_maas_heal_api_post_action_dataplane_probe.py --target 10.123.45.67 --require-ready --json`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/verify_maas_autonomous_mesh_runtime_smoke.py --dataplane-probe-target 10.123.45.67`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/verify_maas_real_agent_control_loop.py --dataplane-probe-target 10.123.45.67 --timeout-seconds 180`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/check_real_readiness.py --json --skip-git-check`
- `python3 -m json.tool .workflow/x0tta6bl4-roadmap-closure/state.json >/dev/null`
- `python3 /mnt/projects/user_data/x0ttta6bl4/.codex/skills/codex-dynamic-workflows/scripts/verify_workflow.py .workflow/x0tta6bl4-roadmap-closure`
- `git diff --check`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json`
- `python3 -m json.tool docs/team/swarm_ownership.json >/dev/null`
- `bash scripts/agents/check_coordination_contract.sh`
- `python3 -m py_compile <coordination agent scripts and product verifier tests>`
- `bash -n scripts/agents/lane_pickup.sh scripts/agents/start_micro_niche_scout.sh scripts/agents/start_rkn_tspu_scout.sh scripts/agents/stop_micro_niche_scout.sh scripts/agents/stop_rkn_tspu_scout.sh`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/test_all_agents.py`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_agent_work_receipt_gate.py tests/unit/scripts/test_security_scan_template_unit.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/verify_agent_work_receipt_gate_release.py --output-dir .tmp/validation-shards/agent-work-receipt-gate-coordination --json`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/verify_security_gates_release.py --output-dir .tmp/validation-shards/security-gates-coordination --json`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/verify_products_production_readiness.py --output-dir .tmp/validation-shards/products-production-coordination --json`
- `python3 -m json.tool config/chaos_agent.json >/dev/null`
- `PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py --help`
- local link check for `docs/runbooks/README.md` and
  `docs/runbooks/PILOT1_EDGE_MESH_LAB.md`
- local secret scan for `docs/runbooks/PILOT1_EDGE_MESH_LAB.md` and
  `config/chaos_agent.json`
- local schema check for `config/chaos_agent.json`
- local claim-boundary marker check for
  `docs/runbooks/PILOT1_EDGE_MESH_LAB.md`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/chaos_engineer_agent.py --config config/chaos_agent.json --mode report`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/run_pilot0_edge_mesh_maas.py --require-ready --output-dir .tmp/validation-shards/pilot1-edge-mesh-lab --json`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/security/test_dependency_security_pins_unit.py -q --no-cov`
- inline pyproject/requirements installability check
- inline Ghost Access daily health and starter incident template policy check
- `./.venv/bin/python -m pip install -e . --no-deps`
- `./.venv/bin/python -m pip install --no-deps fastapi==0.128.5 starlette==0.52.1`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json`
- `python3 -m py_compile src/sales/*.py scripts/ops/*agent*.py scripts/ops/*paid*.py scripts/ops/*income*.py`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/sales tests/unit/scripts/test_run_income_watch_cycle.py tests/unit/scripts/test_run_paid_task_hunter.py tests/unit/scripts/test_check_commercial_mesh_platform_readiness.py tests/unit/scripts/test_agent_work_receipt_gate.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_build_non_bounty_income_map.py tests/unit/scripts/test_build_paid_task_automation_plan.py tests/unit/scripts/test_collect_paid_task_listings.py tests/unit/scripts/test_ensure_x402_paid_api_public.py tests/unit/scripts/test_run_paid_task_watch_loop.py tests/unit/scripts/test_score_paid_task_listings.py -q --no-cov`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/check_commercial_mesh_platform_readiness.py --require-ready --json`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/build_paid_task_automation_plan.py --write-md .tmp/validation-shards/commercial-income/paid-task-automation-plan.md --write-json .tmp/validation-shards/commercial-income/paid-task-automation-plan.json`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/build_non_bounty_income_map.py --write-md .tmp/validation-shards/commercial-income/non-bounty-income-map.md --write-json .tmp/validation-shards/commercial-income/non-bounty-income-map.json --artifact-dir .tmp/validation-shards/commercial-income/non-bounty-artifacts`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/run_income_watch_cycle.py --offline --cycles 1 --agentjob-wait-seconds 0 --output .tmp/validation-shards/commercial-income/income-watch-cycle-offline.json --history-jsonl .tmp/validation-shards/commercial-income/income-watch-history-offline.jsonl`
- `PYTHONPATH=. ./.venv/bin/python scripts/ops/score_paid_task_listings.py --input docs/commercial/paid_task_listings.example.json --top 5 --write-json .tmp/validation-shards/commercial-income/paid-task-score-example.json --write-md .tmp/validation-shards/commercial-income/paid-task-score-example.md`
- `find .tmp/validation-shards/commercial-income -name '*.json' -print0 | xargs -0 -I{} python3 -m json.tool {} >/dev/null`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json`
- `find scripts/agents -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile`
- `find scripts/agents -maxdepth 1 -name '*.sh' -print0 | xargs -0 bash -n`
- `find scripts/agents -maxdepth 1 -name '*.json' -print0 | xargs -0 -I{} python3 -m json.tool {} >/dev/null`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/test_all_agents.py`
- `PYTHONPATH=. ./.venv/bin/python scripts/agents/check_swarm_ownership.py --agent lead-coordinator --print-scope`
- `bash -n scripts/agent-coord.sh scripts/agents/request_channel.sh scripts/agents/start_swarm_session.sh scripts/agents/stop_swarm_session.sh scripts/agents/install_swarm_hook.sh`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_summarize_dirty_worktree_review.py tests/unit/test_policy_enforcement_map_unit.py tests/unit/scripts/test_check_real_readiness_unit.py::test_swarm_coordination_contract_failure_blocks_readiness -q --no-cov`
- `python3 -m json.tool docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json >/dev/null && python3 -m json.tool docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json >/dev/null`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/test_cross_plane_evidence_map_unit.py tests/unit/test_real_readiness_gate_doc_unit.py -q --no-cov`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json`

Known non-passing environment check:

- `./.venv/bin/python -m pip check` still reports pre-existing local
  environment drift in `opentelemetry`, `flwr`, `shap`, `numba`, and `spiffe`.
  The x0tta6bl4-specific metadata and Starlette conflicts are cleared.

Next useful checks:

- Review remaining split-owner manual packages before any explicit staging.
- Leave actual Ghost Access outreach/payment behind operator approval.

## Reusable Artifacts

- This workflow directory: `.workflow/x0tta6bl4-roadmap-closure/`.
- Use it as the running queue for future roadmap closure tranches.
