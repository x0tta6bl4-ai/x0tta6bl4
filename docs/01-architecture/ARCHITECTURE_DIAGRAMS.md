# x0tta6bl4 Architecture Diagrams (As-Built)

**Version:** `v3.4.0`  
**Updated:** `2026-03-05`  
**Status:** `aligned with repository code`

## Source of truth

This document is aligned to:

- `src/core/app.py` (FastAPI composition, middleware chain, router registration)
- `src/database/__init__.py` (SQLAlchemy models, DB circuit-breaker wiring)
- `src/monitoring/maas_metrics.py` and `src/monitoring/metrics.py` (business + platform metrics)
- `mesh-operator/cmd/manager/main.go` (operator manager bootstrapping)
- `mesh-operator/controllers/meshcluster_controller.go` (reconcile logic)
- `charts/x0tta-mesh-operator/templates/operator/deployment.yaml` (runtime args and probes)
- `scripts/ops/mesh_operator_release_dry_run.sh` (release control checkpoints)

## 1) Runtime Architecture (MaaS API + Services)

```mermaid
flowchart LR
    A[Client / CLI / Integrations] --> B[FastAPI Gateway\nsrc/core/app.py]
    B --> C[Security + Reliability Middleware\nCORS, mTLS, RateLimit, Validation,\nTracing, Shutdown, Security Headers]
    C --> D[API Routers]

    D --> D1[MaaS Core Routers\nmarketplace, billing, governance,\nplaybooks, auth, analytics, dashboard]
    D --> D2[Full-mode Routers\nnodes, telemetry, vpn, users,\nswarm, ledger, vision]
    D --> D3[Edge + Event Sourcing Routers]

    D1 --> E[Domain/Resilience Layer\nMAPE-K, Circuit Breaker,\nRetry, Policy, Health Bot]
    D2 --> E
    D3 --> E

    E --> F[(SQLAlchemy DB\nsrc/database/__init__.py)]
    E --> G[(Prometheus Metrics\n/metrics)]
    E --> H[Logs + Tracing]
```

### Router loading contract

- Always loaded: `maas_legacy`, `maas_compat`, `maas_auth`, `maas_playbooks`, `maas_supply_chain`, `maas_marketplace`, `maas_governance`, `maas_analytics`, `maas_billing`, `billing`, `maas_agent_mesh`, `maas_dashboard`, `edge.api`, `event_sourcing.api`.
- Full mode only (`MAAS_LIGHT_MODE=false`): `maas_nodes`, `maas_policies`, `maas_telemetry`, `vpn`, `users`, `swarm`, `ledger_endpoints`, `swarm_endpoints`, `vision_endpoints`.

## 2) Kubernetes Control Plane (mesh-operator)

```mermaid
flowchart LR
    U[User / CI] --> H[Helm Chart\ncharts/x0tta-mesh-operator]
    H --> O[mesh-operator Deployment\ncontroller-runtime manager]
    O --> R[MeshClusterReconciler]

    CR[MeshCluster CR] --> R
    R --> CM[ConfigMap\nmeshcluster.json]
    R --> SVC[Service\nmesh TCP 8080]
    R --> DEP[Deployment\nmesh-node replicas]
    R --> ST[Status / Conditions\nReady, Progressing, Degraded]

    DEL[CR deletion] --> FIN[Finalizer cleanup]
    FIN --> X[Delete owned resources]
```

### Reconcile contract

- Reconcile loop: `ConfigMap` -> `Service` -> `Deployment` -> `status patch`.
- Finalizer enforces cleanup on delete.
- Status reflects `ObservedGeneration`, `ReadyReplicas`, and phase transitions.
- Default requeue behavior is active even in steady state (heartbeat reconciliation).

## 3) Release Control Architecture

```mermaid
flowchart LR
    PR[Push / PR] --> CI[mesh-operator-kind-e2e.yml]
    CI --> G1[Image reproducibility gate]
    CI --> G2[Kind smoke + webhook + lifecycle e2e]
    CI --> G3[Canary rollout + rollback e2e]

    REL[Release dry-run script] --> CP[CP-01..CP-10 checkpoints]
    CP --> EV[Evidence artifacts\n/docs/release/*.json *.md *.log]
```

Current dry-run control points include canary rollback validation (`CP-10`), so release evidence and CI gates use the same control model.

