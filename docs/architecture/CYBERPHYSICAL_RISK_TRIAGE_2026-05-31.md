# x0tta6bl4 Cyberphysical Risk Triage - 2026-05-31

This note turns the external architectural analysis into repo-backed engineering
work. It is not a production-readiness claim.

## Status

The analysis is useful, but mixed:

- Repo-backed: SPIFFE/SPIRE integration exists, MAPE-K control loops exist,
  Telegram integrations exist, and CID-related dependencies are present.
- Partially backed: Telegram is used both for notification paths and sales/user
  interaction; there is no single enforced "read-only Telegram" boundary.
- Not repo-backed from the current scan: "LobeHub Skills" as a runtime control
  dependency and a specific `mtls-bot` automation identity.
- Needs immediate local-secret hygiene: a local ignored `.env.telegram-bot` file
  contains a Telegram token-like value. Do not quote it in chat or commit it.
  Rotate the token locally if it was real.

## Evidence Snapshot

| Area | Current repo evidence | Current assessment |
| --- | --- | --- |
| SPIFFE/SPIRE identity | `src/core/app.py`, `src/core/mtls_middleware.py`, `src/security/spiffe/`, `infra/security/spire-agent-daemonset.yaml`, `deploy/helm/maas/templates/api-deployment.yaml` | Real integration exists. Workload socket is mounted read-only in some app charts, but SPIRE agent manifests still use hostPath sockets and permissive k8s workload-attestation settings that need hardening review. |
| SPIRE socket path | `/run/spire/sockets/agent.sock` and `/tmp/spire-agent/public/api.sock` appear across code, docs, and validation scripts | The risk is real: local socket access must be treated as identity material access. Need a policy gate for socket mounts and workload selectors. |
| Telegram | `telegram_bot.py`, `src/sales/telegram_bot.py`, `scripts/send_telegram_alert.sh`, `scripts/telegram_webhook_server.py`, `src/services/provisioning_service.py` | Mixed notification and business-flow usage. It should not be allowed to become a mesh-control plane without an explicit claim gate and read-only policy. |
| MAPE-K | `src/core/mape_k_loop.py`, `src/core/mape_orchestrator.py`, `src/self_healing/mape_k/manager.py` | Control-loop code exists and already uses safe-actuator/EventBus evidence in key paths. Hardware-level safe mode is not proven by repo evidence. |
| CID/content addressing | `requirements.txt` includes `py-cid` and `py-multicodec`; `src/dao/knowledge_storage.py` references IPFS CID | Dependency exists, but broad claims that all plans/config/telemetry are content-addressed are not proven by current code search. |
| UI helper deps | `requirements.txt` includes `iterfzf`, `qprompt`, `anybadge`, `starlette-csrf`, `yattag` | Dependencies are present; this alone does not prove active operational integration. |

## Engineering Backlog

1. Telegram control boundary
   - Add a documented policy: Telegram may notify, sell, and deliver user config,
     but must not execute mesh lifecycle, MAPE-K, billing settlement, or node
     control actions directly.
   - Add a static guard check for Telegram modules that flags direct imports or
     calls into mesh/provisioning/control executors unless a fail-closed claim
     gate is attached.

2. SPIRE workload socket hardening
   - Add a manifest audit that checks SPIRE socket mounts are read-only for
     workloads.
   - Flag `skip_kubelet_verification = true` outside local/dev manifests.
   - Require explicit namespace/service-account selectors for production SPIRE
     entries before making live identity claims.

3. MAPE-K safe mode
   - Define a repo-level safe-mode contract: if knowledge storage, CID lookup,
     EventBus, or dataplane evidence is unavailable, high-risk Execute actions
     must fail closed.
   - Extend readiness checks to prove that this contract is wired into the
     primary MAPE-K execution paths.

4. CID claim boundary
   - Separate "CID dependency installed" from "content-addressed operational
     plan verified".
   - Add evidence only when a plan/config/telemetry artifact is actually hashed,
     stored, resolved, and validated through CID-aware code.

5. Local secret hygiene
   - Rotate any real Telegram token found in local files.
   - Keep `.env.telegram-bot` ignored locally.
   - Prefer `.env.example` placeholders plus secret-manager docs for shared
     environments.

## Next Autonomous Slice

The safest next code task is the Telegram control-boundary guard, because it is
small, reviewable, and directly addresses a real risk from the analysis without
requiring live infrastructure or private secrets.
