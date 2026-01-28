# Security Boundary - 2026-01-26

## Scope (In-Scope)
- FastAPI services under `src/api/`.
- Flask dashboards under `src/web/`.
- Billing webhooks under `src/api/billing.py`.

## Out of Scope / Quarantined
- Legacy PHP web stack under `/web/**` (includes `web/html`, `web/dvijok`, `web/login`, `web/test`, etc.).

## Rationale
- Legacy PHP stack contains weak password hashing (MD5) and lacks CI coverage.
- Current hardening sprint focuses on API surface used in staging/production.

## Boundary Rules
- Do NOT deploy `/web/**` to production or expose it on public ingress.
- If required for internal testing, restrict to internal network/VPN only.
- No customer data, auth tokens, or API keys should flow through legacy web.

## Linked Follow-Up
- Issue #2411: Legacy web cleanup (MD5 -> bcrypt, auth hardening), target sprint 2026-02-16.

## Review Cadence
- Re-evaluate boundary after sprint 2026-02-16.
