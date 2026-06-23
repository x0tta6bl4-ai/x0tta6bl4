# Packet 05: Core API Runtime Review

## Objective

Review and harden the `core_api_runtime` mesh API path without staging unrelated
dirty-worktree files.

## Scope

- `src/core/app.py`
- `tests/unit/core/test_app_mesh.py`

## Result

Completed. The core mesh API fix is present in `HEAD` at
`1d961a73d fix(core): keep mesh API proof gates fail closed`, so these paths are
no longer dirty in the current worktree review.

## Fix

- Mesh API responses now use the fast fail-closed cross-plane claim gate instead
  of running the full cross-plane proof gate inside `/mesh/status`,
  `/mesh/peers`, and `/mesh/routes` request handling.
- Mesh API EventBus evidence now skips oversized root event logs by default
  instead of synchronously loading a large `.agent_coordination/events.log`.
- Unit tests now inject a temporary EventBus and cover the oversized-log guard.

## Verification

- `python3 -m py_compile src/core/app.py src/core/app_desktop.py`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/core/test_app_mesh.py -q --no-cov --durations=10`: `7 passed in 3.28s`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/core/test_app_desktop_live_snapshot_unit.py -q --no-cov`: `7 passed in 2.66s`
- `PYTHONPATH=. ./.venv/bin/python - <<'PY' ... import src.core.app ... PY`: `app_import_ok`
- `git diff --check -- src/core/app.py src/core/app_desktop.py tests/unit/core/test_app_desktop_live_snapshot_unit.py tests/unit/core/test_app_mesh.py`
- ASGI smoke for `/mesh/status`: `status_code=200`, `control_policy_status=missing`, `cross_plane_decision=CROSS_PLANE_CLAIMS_BLOCKED_FAST_LOCAL_OBSERVATION`
