# Telegram Control-Boundary Policy for x0tta6bl4

## 1. Purpose
Telegram is used in x0tta6bl4 for notifications, sales, user onboarding, and delivering user-specific configurations. However, it must NOT be used as a direct control plane for the mesh network, infrastructure, or billing settlement.

## 2. Forbidden Operations
Telegram handlers, webhooks, and bots are prohibited from:
- Directly importing mesh orchestration or MAPE-K control loop modules.
- Directly executing infrastructure mutation commands (kubectl, docker-compose, alembic).
- Directly triggering high-risk mesh actions like `deploy_mesh`, `scale_mesh`, or `heal_node`.
- Accessing raw node identifiers, peer addresses, or internal routing tables.

## 3. Mandatory Boundary
Any action that requires mesh mutation or high-privilege operations must be performed via:
1. An explicit API boundary (FastAPI/Core API).
2. A separate service with its own authorization layer.
3. Attaching a fail-closed claim gate to the request.

## 4. Enforcement
This policy is enforced by `scripts/ops/check_telegram_control_boundary.py`, which performs static analysis on all known Telegram entrypoints. This check is a mandatory part of the production readiness gate.

## 5. Violation Response
Any violation of this boundary is considered a P0 security risk. The readiness gate will fail-close, and the code must be refactored to use the proper service-layer boundaries before proceeding.

---
*Created: June 2, 2026*
*Status: ENFORCED*
