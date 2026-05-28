# Current Cross-Layer Link Map

Captured: 2026-05-27
Status: working map, not a production completion proof.

This document records the current code-level links between major x0tta6bl4 layers. It is based on the local CodeGraph index and direct source inspection in `/mnt/projects`.

## Evidence Snapshot

- CodeGraph status: checked after sync; exact local counts are available via `codegraph_status`.
- Main runtime entrypoint: `src/core/app.py`.
- Production lifecycle entrypoint: `src/core/production_lifespan.py`.
- Local fail-closed control path: `src/integration/spine.py`.
- Executable wiring proof already present: `src/integration/code_wiring.py` and `docs/verification/integration-spine-code-wiring-2026-05-20.md`.
- Light-mode MaaS route audit on 2026-05-27: 92 MaaS routes checked through Starlette's router, 0 shadowed routes after the billing order fix.
- Machine-readable component registry: `docs/architecture/CURRENT_COMPONENT_REGISTRY.json`.
- Component registry drift-check: `tests/unit/test_component_registry_unit.py`.
- Lifecycle readiness map: `docs/architecture/CURRENT_LIFECYCLE_READINESS_MAP.json`.
- Lifecycle readiness drift-check: `tests/unit/test_lifecycle_readiness_map_unit.py`.
- Runtime readiness flags: `/edge/health` and `/events/health` expose `startup_hook_completed`; `/api/v1/maas/marketplace/status` exposes `write_db_ready`; `/api/v1/maas/billing/readiness` exposes `stripe_config_ready`; `/api/v1/maas/governance/readiness` exposes `control_plane_ready`; `/api/v1/maas/supply-chain/readiness` exposes `persistent_supply_chain_ready`; `/api/v1/maas/analytics/readiness` exposes `analytics_runtime_ready`; `/api/v1/maas/playbooks/readiness` exposes `playbook_control_plane_ready`; `/api/v1/maas/policies/readiness` exposes `policy_runtime_ready`; `/api/v1/maas/nodes/readiness` exposes `node_runtime_ready`; `/api/v1/maas/telemetry/readiness` exposes `telemetry_runtime_ready`; `/vpn/readiness` exposes `vpn_runtime_ready` for route-only commerce, billing, governance, supply-chain, analytics, playbook, policy, node, telemetry, and VPN modules.
- Namespace convergence map: `docs/architecture/CURRENT_NAMESPACE_CONVERGENCE_MAP.json`.
- Namespace convergence drift-check: `tests/unit/test_namespace_convergence_map_unit.py`.
- Canonical import direction map: `docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json`.
- Canonical import drift-check: `tests/unit/test_canonical_import_map_unit.py`.
- Evidence-to-runtime bridge map: `docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json`.
- Evidence-to-runtime drift-check: `tests/unit/test_evidence_runtime_bridge_map_unit.py`.
- Policy enforcement map: `docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json`.
- Policy enforcement drift-check: `tests/unit/test_policy_enforcement_map_unit.py`.
- Event/control-plane map: `docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json`.
- Event/control-plane drift-check: `tests/unit/test_event_control_plane_map_unit.py`.

## Runtime Spine

```text
HTTP/API
  -> src/core/app.py
     -> security/rate/tracing/validation/shutdown/metering/audit middleware
     -> MaaS routers, billing routers, ledger, swarm, edge, event-sourcing

Production mode
  -> src/core/production_lifespan.py
     -> database schema guard
     -> MeshNetworkManager
     -> PrometheusExporter
     -> ZeroTrustValidator
     -> ConsciousnessEngine
     -> PARLController
     -> Federated Learning integration
     -> MAPEKLoop background task
     -> edge startup/shutdown
     -> event-sourcing startup/shutdown

Local control/evidence plane
  -> EventBus + service_event_identity + SafeActuator/AsyncSafeActuator
     -> governance / DAO / token bridge / marketplace / rewards
     -> swarm / self-healing / SPIFFE / MPTCP / ghost server
```

## Main Layer Bindings

| Binding | Evidence | Why it matters |
|---|---|---|
| API shell -> production intelligence runtime | `src/core/app.py:38-57`, `src/core/production_lifespan.py:102-182` | Production mode does not just serve HTTP. It starts DB schema checks, mesh state, metrics, zero-trust, consciousness, PARL, FL, MAPE-K, edge, and event sourcing. |
| API shell -> route surface | `src/core/app.py:227-263` | Router registration order is behavior. Fixed-prefix billing routes are registered before the legacy MaaS catch-all routes, and the billing status path has a regression guard. |
| Governance API -> local control plane | `src/api/maas_governance.py:24-30`, `src/api/maas_governance.py:313-410` | Governance execution uses EventBus, service identity, normalized policy evaluation, and SafeActuator before applying actions. |
| Policy decision dialects -> runtime enforcement gates | `src/security/policy_decision_adapter.py:30-87`, `src/security/zero_trust/policy_engine.py:216-232`, `src/security/policy_engine.py:225-244`, `docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json` | Runtime components accept decisions from both zero-trust `allowed` and ABAC `effect` shapes without truthiness-based allow bugs; 17 guarded components are tracked. |
| `src.libx0t` canonical imports -> top-level compatibility surface | `docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json`, `tests/unit/test_canonical_import_map_unit.py`, `src/libx0t/core/production_checks.py:34`, `src/security/pqc_identity.py:15`, `src/network/discovery/protocol.py:329` | `src/libx0t` now imports its own `src.libx0t.*` modules when they exist, while top-level `libx0t` stays as a compatibility/public surface. |
| Governance API -> PQC attestation | `src/api/maas_governance.py:521-528` | Proposal finality hash is signed through `src.libx0t.core.app.pqc_sign` when available. |
| Billing API -> legacy MaaS metering | `src/api/maas_billing.py:28-32`, `src/api/maas_billing.py:260-292` | New Stripe billing still depends on legacy mesh lookup and usage metering. |
| Billing API -> reliability and observability | `src/api/maas_billing.py:22-26`, `src/api/maas_billing.py:64-93` | Stripe calls are wrapped by shared retry/circuit policy and mark degraded dependencies for HTTP responses. |
| Ledger API -> RAG memory | `src/api/ledger_endpoints.py:15-17`, `src/api/ledger_endpoints.py:56-147`, `src/api/ledger_endpoints.py:156-207` | `/api/v1/ledger` lazily indexes and searches the Continuity Ledger through the RAG pipeline, and search responses now expose `metadata.citations` when retrieved chunks carry source metadata. |
| Verification evidence -> Ledger API -> RAG memory | `src/ledger/rag_search.py:21-22`, `src/ledger/rag_search.py:193-331`, `src/api/ledger_endpoints.py:260-303` | `docs/verification` artifacts can now be explicitly indexed into the same runtime RAG surface as the Continuity Ledger, with metadata preserving source path and evidence boundaries. |
| EventBus traces -> Ledger API -> RAG memory | `src/services/service_event_trace.py:159-209`, `src/ledger/rag_search.py:237-247`, `src/ledger/rag_search.py:364-460`, `src/api/ledger_endpoints.py:311-366`, `scripts/ops/smoke_ledger_event_trace_citation.py:131-620` | Redacted EventBus history can now be indexed as runtime evidence. Search citations can carry `event_id`, `event_type`, `source_agent`, registered `service_name`, `layer`, `entrypoint`, and `redacted=true`; the smoke script exercises the API route and search citation path across swarm consensus, commerce settlement, DAO executor blocked-action, self-healing recovery-action, self-healing PQC identity, mesh network reward, share-to-earn network usage reward, MPTCP network control, SPIRE security identity, and PQC security service layers. |
| Marketplace settlement -> telemetry -> chain bridge -> audit | `src/services/marketplace_settlement.py:4-10`, `src/services/marketplace_settlement.py:35-143` | Escrow release/refund is driven by MaaS telemetry uptime, then optionally calls TokenBridge, emits marketplace events, and writes audit logs. |
| Share-to-earn -> routing stats -> reward events | `src/services/share_to_earn_service.py:10-12`, `src/services/share_to_earn_service.py:83-150` | Economy accounting uses exit-node eligibility and local mesh stats, then emits reward lifecycle events without claiming live settlement. |
| EventBus + service identity + actuator -> cross-layer control plane | `docs/architecture/CURRENT_EVENT_CONTROL_PLANE_MAP.json`, `src/coordination/events.py:18-69`, `src/services/service_event_identity.py:76-103`, `src/integration/spine.py:123-186` | 37 current `src` files touch the event/control surface. API, DAO, network, security, self-healing, server, swarm, commerce, reward code, trace filtering, and Ledger/RAG event-trace indexing share one event vocabulary and identity envelope. |
| Redacted service identity status -> event-producing services | `src/services/service_identity_registry.py:16-149`, `src/api/service_identity_status.py:21-33`, `src/core/app.py:250` | 21 current services that call `service_event_identity()` are now visible through `/api/v1/service-identity/status` without exposing SPIFFE IDs, DIDs, or wallet values. |
| Registered service trace filters -> EventBus history/replay/API | `src/services/service_event_trace.py:35-209`, `src/coordination/events.py:282-330`, `src/coordination/cli.py:213-267`, `src/api/service_identity_status.py:27-54` | Operators can filter EventBus history/replay by registered service name, optional source-agent alias, or layer, using the same registry as service identity status. The HTTP trace endpoint recursively redacts `spiffe_id`, `did`, and `wallet_address` before returning event data. |
| SafeActuator reused outside IntegrationSpine | `src/integration/spine.py:123-186` plus imports in `src/swarm`, `src/services`, `src/server`, `src/self_healing`, `src/dao`, `src/security`, `src/network` | SafeActuator is becoming the common guard for dangerous actions, not just a test helper. |
| Canonical service identity across background services | `src/services/service_event_identity.py:76-103` | Background events share SPIFFE/DID/wallet identity resolution through service-specific and generic env vars, and the status helper reports presence/source metadata with values redacted. |

## Non-Obvious Links Found

1. `src/core/app.py` rewrites its own `__file__` to `libx0t/core/app.py` when the legacy file exists (`src/core/app.py:33-36`). This is a compatibility bridge that can confuse tooling and audits if they rely on `__file__`.

2. The MaaS route tree had a real shadowing hazard. Before the route-order fix on 2026-05-27, light-mode runtime matched `/api/v1/maas/billing/status` to legacy route `/api/v1/maas/{mesh_id}/status`, with `mesh_id='billing'`. The billing routers now register before `src.api.maas_legacy`, and `tests/unit/api/test_maas_negative_cases_unit.py` checks the direct Starlette match.

3. Billing is not isolated from legacy MaaS. `src/api/maas_billing.py` imports `usage_metering_service` and `_get_mesh_or_404` from `src.api.maas_legacy` first, only falling back to `src.api.maas`. This means legacy mesh semantics directly affect invoice generation.

4. The local integration spine is broader than `IntegrationSpine`. `SafeActuator` and `AsyncSafeActuator` are imported by swarm PBFT, swarm MAPE-K intelligence, PQC rotator, ghost server, eBPF self-healing, SPIFFE agent/server, MPTCP manager, DAO governance, DAO executor, governance contract, proposal executor, and token bridge.

5. `EventBus` is the hidden control plane. `get_event_bus()` is used by governance, DAO, token bridge, MPTCP, SPIFFE, self-healing, ghost server, swarm, reward events, and marketplace events. The project already has a common event vocabulary, even where modules look separate. The current event/control-plane map tracks 37 `src` files, 31 `EventType` values, and 21 services that resolve canonical event identity.

6. Policy decisions had two shapes. Zero-trust returns `allowed/action/matched_rules`, while the older ABAC policy engine returns `effect/policy_id/rule_id`. Before the adapter, a truthy ABAC `DENY` dataclass could be treated as allowed by repeated `_policy_allowed()` helpers. `src/security/policy_decision_adapter.py` now normalizes both dialects and the policy enforcement map tracks 17 guarded components.

7. Production lifecycle and API route inclusion are not the same thing. `src/core/app.py` includes `src.edge.api` and `src.event_sourcing.api` routers in all modes, but their startup/shutdown hooks are only called by `src/core/production_lifespan.py` when production lifespan is active.

   Current lifecycle map details: 23 router registrations are tracked. `edge-computing` and `event-sourcing` are the only tracked routers with explicit `production_lifespan` startup/shutdown hooks, and both routes are still present in light mode where that lifespan is not attached. Their health payloads now expose `startup_hook_completed` so operators can separate route reachability from startup completion. Route-only marketplace, billing, governance, supply-chain, analytics, playbooks, policies, nodes, telemetry, and VPN APIs now expose runtime readiness fields so operators can separate route availability from database-backed writes, Stripe configuration, local control-plane dispatch readiness, durable SBOM/attestation evidence readiness, analytics DB/Redis telemetry readiness, signed command dispatch readiness, policy route-precedence/DB readiness, node route-precedence/telemetry/healing readiness, telemetry route-precedence/Redis/settlement-uptime readiness, and VPN x-ui/config/ZKP/production-env readiness.

8. There are parallel package surfaces: `src/libx0t/...` and top-level `libx0t/...`. Current namespace map shows 154 top-level `libx0t` Python files, 114 `src/libx0t` Python files, 82 common paths, only 14 byte-identical common paths, and 68 differing common paths. This is a compatibility asset, but also a drift risk unless one surface is declared canonical.

   Concrete import hole found and fixed: `src.libx0t.core.production_lifespan` imported `libx0t.security.zero_trust`, but top-level `libx0t/security` had no source package. Top-level security shims now re-export canonical modules for `post_quantum`, `pqc_core`, `pqc_mtls`, `zero_trust`, and `production_hardening`.

   Follow-up import pass: `docs/architecture/CURRENT_CANONICAL_IMPORT_MAP.json` declares `src.libx0t` as the canonical internal direction when a matching `src/libx0t` module exists. Current AST scan leaves 0 direct top-level `libx0t.*` import statements inside `src/libx0t`. The previous yggdrasil/byzantine/eBPF top-level-only implementations are now reached through explicit `src.libx0t.network` bridge modules.

   Additional import hole fixed: `src/libx0t/core/production_checks.py` no longer imports missing `libx0t.security.post_quantum_liboqs`; it uses `src.security.pqc.LIBOQS_AVAILABLE`. `src/security/pqc_identity.py` and `src/network/discovery/protocol.py` now prefer `src.libx0t.security.post_quantum` before falling back to top-level `libx0t.security.post_quantum`.

   Hidden dependency fixed during verification: `src.libx0t.core.mape_k_loop` had relative imports into missing `src.libx0t.dao`, `src.libx0t.mesh`, and `src.libx0t.monitoring` packages. It now redirects to the already canonical `src.core.mape_k_loop`, matching the top-level `libx0t.core.mape_k_loop` compatibility pattern.

   Production hardening bridge fixed: `src/libx0t/core/production_system.py` now imports `src.security.production_hardening` directly, and `libx0t.security.production_hardening` exists as a compatibility shim for legacy callers.

9. Marketplace settlement uses operational telemetry as financial state input. `uptime_tracker` from `src/api/maas_telemetry.py` decides whether escrow is released or refunded in `src/services/marketplace_settlement.py`.

10. The ledger layer is exposed as an API memory surface, not only as internal docs. `src/api/ledger_endpoints.py` can index and query the Continuity Ledger at runtime, so release/evidence documents can influence operator-facing answers.

11. Production guardrails are fail-closed only under production conditions. `src/core/production_lifespan.py:184-200` allows degraded startup outside production unless `X0TTA6BL4_FAIL_OPEN_STARTUP=false`; production guardrail violations force fail-closed.

12. Verification artifacts are now a runtime-searchable evidence source when explicitly requested. Current evidence map tracks 1073 text-like files under `docs/verification` (`.md`, `.json`, `.jsonl`) and 38 `*_LATEST` aliases. `/api/v1/ledger/evidence/index` indexes them into the same `LedgerRAGSearch` pipeline; `/api/v1/ledger/search` can request this with `include_verification=true`.

13. The Ledger API had a hidden result-shape mismatch: `LedgerRAGSearch.query()` returns `LedgerSearchResult.results`, while the API assumed a lower-level `RAGResult.retrieved_chunks`. The API serializer now supports both shapes so the real runtime path matches the mocked tests and the RAG implementation.

14. Network, commerce, and chain traces converge through shared event helpers. `src/network/mesh_vpn_bridge.py` passes EventBus and identity into `TokenRewards`; `src/services/share_to_earn_service.py` publishes reward events; `src/api/maas_marketplace.py`, marketplace services, and `src/dao/token_bridge.py` share the same escrow event helper. This means network usage, marketplace lifecycle, and token bridge evidence use the same control-plane vocabulary.

15. Service identity is now inspectable without leaking identity values. `src/services/service_identity_registry.py` enumerates all 21 current `service_event_identity()` callers, and `/api/v1/service-identity/status` reports only configured/source/env-var metadata, not the SPIFFE/DID/wallet values themselves.

16. Event traces now use the same service registry. `src/services/service_event_trace.py` maps registered service names/layers to EventBus `source_agent` filters, so `EventBus.get_event_history()` and `EventBus.replay_events()` can be filtered by layer-level service identity without making the base event bus depend on the service registry. `/api/v1/service-identity/event-traces` exposes the filtered view with recursive identity-field redaction.

17. EventBus traces are now runtime evidence, not just operator inspection output. `/api/v1/ledger/event-traces/index` builds a redacted trace payload with `service_event_trace_history()`, `LedgerRAGSearch.index_event_traces()` stores each event as RAG evidence, and Ledger citations preserve `event_id`, `source_agent`, service name, layer, entrypoint, and `redacted=true`. `python3 scripts/ops/smoke_ledger_event_trace_citation.py --json` proves the API index route, search route, citation metadata, and identity-value redaction across `swarm-pbft`, `maas-settlement`, `dao-executor`, `recovery-action-executor`, `mesh-vpn-bridge`, `share-to-earn`, `mptcp-manager`, `spire-server-client`, `pqc-rotator`, and `pqc-zero-trust-healer`.

18. PQC zero-trust recovery has two useful names that now stay connected. `PQCZeroTrustExecutor` resolves identity as registered service `pqc-zero-trust-executor`, but its EventBus source is `pqc-zero-trust-healer`. The service registry now carries that `source_agent` alias, so layer filters and Ledger citations keep both the runtime source and the registered service identity.

## Current Risk Hotspots

| Risk | Current evidence | Practical next action |
|---|---|---|
| MaaS catch-all route shadowing class | Billing status shadowing was fixed by registering `src.api.maas_billing` before `src.api.maas_legacy` (`src/core/app.py:237-242`) and adding a direct route-match test. A light-mode audit checked 92 MaaS routes and found 0 shadowed routes after the fix. | Keep the route-audit command as a regression check, and add targeted tests when new fixed-prefix MaaS routers are introduced. |
| Duplicate package surfaces | Namespace map shows `libx0t` and `src/libx0t` are not mirrors: 82 common Python paths, 68 differing common paths. Canonical import map now tracks 0 direct top-level imports inside `src/libx0t` and records five bridge modules for top-level-only network implementations. | Decide whether to migrate yggdrasil/byzantine/eBPF implementations behind the bridges or keep top-level `libx0t.network` as their source of truth. |
| Runtime route without lifecycle | Lifecycle map tracks 23 router registrations. `edge-computing` and `event-sourcing` have explicit production hooks, but both routes are present in light mode where `production_lifespan` is not attached. Their health payloads now report `startup_hook_completed`. `maas-marketplace` remains route-import-only and reports `write_db_ready` at `/api/v1/maas/marketplace/status`. `maas-billing` remains route-import-only and reports `stripe_config_ready` at `/api/v1/maas/billing/readiness`. `maas-governance` remains route-import-only and reports `control_plane_ready` at `/api/v1/maas/governance/readiness`. `maas-supply-chain` remains route-import-only and reports `persistent_supply_chain_ready` at `/api/v1/maas/supply-chain/readiness`. `maas-analytics` remains route-import-only and reports `analytics_runtime_ready` at `/api/v1/maas/analytics/readiness`. `maas-playbooks` remains route-import-only and reports `playbook_control_plane_ready` at `/api/v1/maas/playbooks/readiness`. `maas-policies` remains route-import-only, full-mode-only, and reports `policy_runtime_ready` plus the legacy GET/POST shadowing boundary at `/api/v1/maas/policies/readiness`. `maas-nodes` remains route-import-only, full-mode-only, and reports `node_runtime_ready` plus legacy node-route shadowing, telemetry bridge, token signing, audit-log, and healing-service readiness at `/api/v1/maas/nodes/readiness`. `maas-telemetry` remains route-import-only, full-mode-only, and reports `telemetry_runtime_ready` plus legacy heartbeat/topology shadowing, Redis persistence, fallback cache, reputation, metrics, and settlement uptime readiness at `/api/v1/maas/telemetry/readiness`. `vpn` remains route-import-only, full-mode-only, and reports `vpn_runtime_ready` plus fixed-prefix route precedence, lazy x-ui, local User DB, config generator, cache, MaaS auth, legacy admin-token, ZKP legacy DB, and production VPN env readiness at `/vpn/readiness`. | Extend this readiness distinction to the remaining full-mode-only route-only modules that still lack explicit backing-state readiness, such as users. |
| Local evidence vs production settlement | Integration wiring report says `NOT_COMPLETE` for live settlement | Keep local wiring, live RPC receipt, and operator evidence as separate gates. |
| Background service identity drift | 21 services call `service_event_identity()` and are now registered in `src/services/service_identity_registry.py`. | Keep the registry drift-check aligned with new service identity callers, and extend the status payload only with redacted metadata. |
| Event/control-plane drift | Event map tracks 37 `src` files touching EventBus, service identity, event helpers, SafeActuator, AsyncSafeActuator, identity status, service trace filters, or EventBus-to-Ledger indexing. | Keep `tests/unit/test_event_control_plane_map_unit.py` as the guard when adding new event publishers, action executors, trace filters, or trace-memory bridges. |
| Evidence can become overbroad runtime memory | `docs/verification` has 1073 indexable text-like files, and EventBus trace indexing can add runtime event history. | Keep verification indexing explicit, tag every chunk with source class metadata, require `redacted=true` for EventBus traces, and preserve relative paths/event IDs in citations. |

## Next Links To Build

1. Route precedence guard:
   - Done: test that `/api/v1/maas/billing/status` reaches `maas_billing.get_subscription_status`.
   - Next: test that legacy mesh status still works for real mesh ids.
   - Done: audit 92 light-mode MaaS routes against earlier route matches; current shadowed count is 0.
   - Next: keep the audit as a reusable regression check for future router additions.

2. Component registry:
   - Done: initial machine-readable registry lists component name, layer, source refs, event plane, service identity, actuator type, lifecycle mode, and hidden dependencies.
   - Current targets: `maas-governance`, `maas-billing`, `ledger-api`, `token-bridge`, `marketplace-settlement`, `share-to-earn`, `swarm-pbft`, `pqc-rotator`, `ebpf-self-healing`, `spire-agent`, `spire-server-client`, `mptcp-manager`, `ghost-l3-server`.
   - Done: automated drift check fails when a listed component stops exposing its claimed EventBus, identity, actuator, or source-ref surface.
   - Next: add policy-engine and lifecycle readiness claims to the same registry.

3. Lifecycle readiness map:
   - Done: machine-readable map compares `src/core/app.py` router registration with `src/core/production_lifespan.py` startup/shutdown hooks.
   - Done: drift-check verifies all 23 app router registrations are covered and explicit hook claims are still true.
   - Done: `/edge/health` and `/events/health` expose `startup_hook_completed`.
   - Done: `/api/v1/maas/marketplace/status` exposes `write_db_ready` and degraded database dependency metadata for a route-only commerce module with escrow/listing write state.
   - Done: `/api/v1/maas/billing/readiness` exposes `stripe_config_ready`, `stripe_plans_ready`, `write_db_ready`, and `legacy_metering_ready` for route-only billing with Stripe and invoice write state.
   - Done: `/api/v1/maas/governance/readiness` exposes `control_plane_ready`, `governance_db_ready`, `policy_engine_ready`, `safe_actuator_ready`, and `service_identity_ready` for route-only governance action dispatch.
   - Done: `/api/v1/maas/supply-chain/readiness` exposes `persistent_supply_chain_ready`, `attestation_store_ready`, `audit_log_ready`, and `ebpf_filter_adapter_ready` for route-only SBOM and binary-attestation evidence.
   - Done: `/api/v1/maas/analytics/readiness` exposes `analytics_runtime_ready`, `analytics_db_ready`, `analytics_service_ready`, and `realtime_telemetry_ready` for route-only analytics backed by DB aggregation and optional Redis telemetry.
   - Done: `/api/v1/maas/playbooks/readiness` exposes `playbook_control_plane_ready`, `playbook_dispatch_ready`, `persistent_playbook_ready`, `memory_queue_ready`, `token_signer_ready`, `playbook_db_ready`, and `audit_log_ready` for route-only signed command dispatch.
   - Done: `/api/v1/maas/policies/readiness` exposes `policy_runtime_ready`, `policy_db_ready`, `acl_policy_model_ready`, `rbac_dependency_ready`, and the legacy GET/POST shadowing boundary for full-mode-only DB-backed ACL policy routes.
   - Done: `/api/v1/maas/nodes/readiness` exposes `node_runtime_ready`, `node_db_ready`, `node_model_ready`, `node_rbac_ready`, `token_signer_ready`, `audit_log_ready`, `telemetry_bridge_ready`, `healing_service_ready`, and the legacy node-route shadowing boundary for full-mode-only DB-backed node runtime routes.
   - Done: `/api/v1/maas/telemetry/readiness` exposes `telemetry_runtime_ready`, `telemetry_db_ready`, `redis_persistence_ready`, `fallback_cache_ready`, `uptime_tracker_ready`, `settlement_uptime_ready`, `reputation_system_ready`, `metrics_export_ready`, and the legacy heartbeat/topology shadowing boundary for full-mode-only telemetry helper routes.
   - Done: `/vpn/readiness` exposes `vpn_runtime_ready`, `vpn_db_ready`, `config_generators_ready`, `xui_client_factory_ready`, `cache_ready`, `auth_dependency_ready`, `legacy_admin_token_ready`, `zkp_legacy_db_ready`, `zkp_attestor_ready`, `production_env_ready`, and fixed-prefix route-precedence metadata for full-mode-only VPN routes.
   - Next: extend the same readiness distinction to route-only modules that still lack explicit backing-state readiness, such as users.

4. Namespace convergence:
   - Done: namespace convergence map captures file counts, import counts, bridges, and hotspots.
   - Done: top-level `libx0t.security` bridge restores current imports to `src.libx0t.security`.
   - Done: drift-check validates counts, source refs, and bridge imports.
   - Done: canonical import direction is declared in `CURRENT_CANONICAL_IMPORT_MAP.json`.
   - Done: import drift-check blocks `src/libx0t` imports back to top-level `libx0t.*` when a `src.libx0t` counterpart exists.
   - Done: yggdrasil/byzantine/eBPF top-level-only implementations are now reached through explicit `src.libx0t.network` bridge modules.
   - Next: decide whether those network implementations should move behind the bridges or remain top-level source-of-truth modules.

5. Evidence-to-runtime bridge:
   - Done: `docs/verification` artifacts can be indexed explicitly through `/api/v1/ledger/evidence/index`.
   - Done: `/api/v1/ledger/evidence/status` reports available text-like evidence artifacts without indexing them.
   - Done: `/api/v1/ledger/search` accepts `include_verification=true` to include evidence in the same RAG runtime surface.
   - Done: redacted EventBus traces can be indexed explicitly through `/api/v1/ledger/event-traces/index`.
   - Done: `/api/v1/ledger/event-traces/status` reports trace-memory indexing counters and source metadata.
   - Done: Ledger citations can now carry verification `relative_path/source_class` and EventBus `event_id/source_agent/layer` metadata.
   - Done: `scripts/ops/smoke_ledger_event_trace_citation.py --json` indexes local `swarm-pbft`, `maas-settlement`, `dao-executor`, `recovery-action-executor`, `mesh-vpn-bridge`, `share-to-earn`, `mptcp-manager`, `spire-server-client`, `pqc-rotator`, and `pqc-zero-trust-healer` EventBus trace samples and shows event-backed citations through `/api/v1/ledger/search`.
   - Done: map and drift-check track current counts, endpoint markers, metadata contract, and source refs.
   - Next: decide whether event-backed Ledger search should stay manual-index only or get an explicit request flag similar to `include_verification`.

6. Event/control plane:
   - Done: machine-readable map captures EventBus, EventType vocabulary, service identity, SafeActuator/AsyncSafeActuator, event helpers, and all current `src` files touching that surface.
   - Done: drift-check verifies source refs, current 31-value EventType vocabulary, and current 37-file event surface coverage.
   - Done: redacted `/api/v1/service-identity/status` reports configured identity source metadata for all 21 current service identity callers without exposing identity values.
   - Done: event history/replay can now filter through the same service registry by registered service name or layer.
   - Done: `/api/v1/service-identity/event-traces` exposes filtered EventBus traces with recursive redaction of `spiffe_id`, `did`, and `wallet_address`.
   - Done: filtered traces are linked into the Ledger/RAG citation path so runtime answers can cite event IDs and source layers directly.
   - Done: trace-memory smoke coverage now includes `spire-server-client` on the `security_identity_to_control_plane` layer through its policy-gated `create_entry()` path.
   - Done: trace-memory smoke coverage now includes `mesh-vpn-bridge` on the `network_to_rewards` layer through `TokenRewards.reward_relay()`.
   - Done: trace-memory smoke coverage now includes `share-to-earn` on the `network_usage_to_rewards` layer through `publish_share_to_earn_reward_event()`.
   - Done: trace-memory smoke coverage now includes `mptcp-manager` on the `network_to_control_plane` layer through policy-gated `MPTCPManager.enable_mptcp()`.
   - Done: trace-memory smoke coverage now includes `pqc-rotator` on the `security_service_to_control_plane` layer through policy-gated `PQCRotatorService.rotate_once()`.
   - Done: trace-memory smoke coverage now includes `pqc-zero-trust-healer` on the `self_healing_pqc_identity` layer through policy-gated `PQCZeroTrustExecutor.execute()`.
   - Next: connect route-only marketplace readiness into EventBus/Ledger evidence, or extend trace-memory smoke coverage to another route-only module with external backing state.
