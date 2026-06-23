# Packet 07: MaaS API Compatibility Review

## Objective

Review the `maas_api_compat` package and restore compatibility auth, legacy,
marketplace, billing, and supply-chain API behavior without weakening claim
boundaries or redaction.

## Scope

- `src/api/maas/**`
- `src/api/maas_auth.py`
- `src/api/maas_auth_legacy_full.py`
- `src/api/maas_billing.py`
- `src/api/maas_compat.py`
- `src/api/maas_legacy.py`
- `tests/api/test_maas_auth.py`
- `tests/api/test_maas_marketplace.py`
- `tests/api/test_maas_billing.py`
- `tests/unit/api/test_maas_*`

## Result

Completed. The package changes are present in `HEAD` at
`a43af85fd fix(maas): restore compatibility auth flows`, and MaaS auth/API
paths no longer appear as dirty in the current dirty-worktree review.

## Fix

- Restored DB-backed API-key rotation, `/auth/me`, `/auth/set-admin/{email}`,
  bootstrap-admin guards, and OIDC unavailable behavior.
- Restored legacy `src.api.maas_auth` direct-call compatibility wrappers with
  redacted EventBus evidence for registration, login, rotation, admin
  promotion, bootstrap, OIDC, credential resolution, profile reads, and API-key
  listing.
- Fixed supply-chain router composition so direct and combined routes resolve
  consistently.
- Removed trailing whitespace from MaaS/node helper edits and then cleared the
  remaining full-worktree trailing whitespace findings.
- Aligned the duplicate registration unit contract with the current API
  `409 Conflict` behavior already covered by integration and enterprise tests.

## Verification

- `git diff --check`: passed.
- `python3 -m py_compile src/api/maas_auth_legacy_full.py src/api/maas/endpoints/auth.py src/api/maas/endpoints/supply_chain.py src/api/maas/endpoints/combined.py src/api/maas/endpoints/nodes.py`: passed.
- `PYTHONPATH=. python3 - <<'PY' ... import src.core.app ... PY`: `app_import_ok`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/api/test_maas_auth.py -q --no-cov`: `40 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_auth_endpoints.py -q --no-cov`: `20 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_package_compat_unit.py tests/unit/api/test_maas_auth_event_evidence_unit.py -q --no-cov`: `21 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/api/test_maas_auth.py tests/api/test_maas_marketplace.py -q --no-cov`: `105 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/api/test_maas_billing.py -q --no-cov`: `145 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_unit.py -q --no-cov`: `59 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_acl_unit.py tests/unit/api/test_maas_agent_mesh_unit.py tests/unit/api/test_maas_marketplace_unit.py tests/unit/api/test_maas_nodes_helpers_unit.py tests/unit/api/test_maas_security_unit.py tests/unit/api/test_maas_supply_chain_unit.py -q --no-cov`: `263 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_compat_* tests/unit/api/test_maas_legacy_* -q --no-cov`: `57 passed`.
