# x0tta6bl4 project audit - 2026-06-06

## Scope

Goal: review the current x0tta6bl4 project state around the Ubuntu desktop app, local agent, and first-party VPN code without changing live services.

Gemini process note: Gemini was restored to running state and was not managed further during this audit.

## Current high-level state

- Worktree is very dirty: `git status --short` reported `771` entries.
- Key changed areas:
  - `agent/`
  - `src-tauri/`
  - `x0tta6bl4-app/`
  - `src/network/firstparty_vpn/`
  - `services/nl-server/firstparty-vpn-test/`
  - VPN scripts and diagnostics
- Local VPN check after tests: PASS, warnings 0, exit IP `89.125.1.107`.

## Ubuntu desktop app state

The app is a real Tauri/React desktop shell:

- Frontend: `x0tta6bl4-app`
- Desktop wrapper: `src-tauri`
- Ubuntu package target: `.deb` and AppImage
- Local packaged API: `src-tauri/runtime/desktop_core_api.py`
- Local node heartbeat: `src-tauri/runtime/desktop_mesh_runtime.py`
- Installed systemd units:
  - `x0tta6bl4-node.service`
  - `x0tta6bl4-core-api.service`
  - optional `x0tta6bl4-full-core-api.service`

Important boundary: this currently proves a local desktop control plane and local state display. It does not prove a live first-party VPN dataplane carrying user traffic.

## First-party VPN state

The repository contains substantial first-party VPN code under `src/network/firstparty_vpn/`, including:

- wire protocol frames with magic `X0VPN001`
- frame crypto and replay protection
- handshake and identity modules
- ML-KEM / ML-DSA reference code
- TUN/client/server/deployment helpers
- anti-DPI/camouflage helpers
- production readiness and source-audit helpers

Important boundary: unit coverage is broad, but a live end-to-end Ubuntu client-to-server TUN traffic test was not proven in this audit.

## Verification run

Commands run:

```bash
cd x0tta6bl4-app && npm run lint -- --max-warnings=0
cd src-tauri && CARGO_TARGET_DIR=/tmp/x0tta6bl4-cargo-check-... cargo check
cd agent && go test ./...
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='' pytest --no-cov -q src-tauri/runtime/test_desktop_core_api_unit.py tests/unit/core/test_app_desktop_live_snapshot_unit.py
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='' pytest -q tests/unit/network/test_firstparty_vpn_protocol_unit.py --cache-clear
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='' pytest -q tests/unit/scripts/test_vpn_systemd_templates_unit.py -q
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='' pytest --no-cov -q tests/unit/scripts/test_vpn_systemd_templates_unit.py::test_firstparty_verify_client_kits_accepts_signed_archives tests/unit/scripts/test_vpn_systemd_templates_unit.py::test_firstparty_verify_client_kits_can_require_live_readiness
bash scripts/vpn_status.sh --check --no-color
```

Results:

- `npm run lint`: passed.
- `cargo check`: passed.
- `go test ./...` in `agent`: passed.
- Desktop API tests with `--no-cov`: `9 passed in 10.85s`.
- First-party protocol suite: `306 passed`; command exit was 1 only because global coverage gate requires 75% and targeted run reached 10.83%.
- Full `test_vpn_systemd_templates_unit.py`: `68 passed, 2 failed`; both failures were in client-kit export using ML-DSA signing.
- Rerun of the two failed client-kit tests with `--no-cov`: `2 passed in 41.99s`.
- Local VPN status: PASS, warnings 0.

## Findings

### Critical: worktree is not reviewable as one change

`771` dirty entries across unrelated systems is too large to merge or deploy safely. The current state must be split into focused review packets.

### High: first-party client-kit signing is flaky

The full wrapper test run failed in:

- `test_firstparty_verify_client_kits_accepts_signed_archives`
- `test_firstparty_verify_client_kits_can_require_live_readiness`

Failure:

```text
MlDsaShapeError: ML-DSA signature hint vector exceeds omega
```

The same two tests passed when rerun alone. Treat this as nondeterministic ML-DSA/reference-signer risk until proven otherwise.

### High: Ubuntu installer path is not release-safe

`agent/scripts/install.sh` now copies:

```bash
cp "agent/bin/x0t-agent" "/usr/local/bin/x0t-agent"
```

This only works from a repo checkout with a local build artifact. It is not a safe remote installer/release path.

### Medium: desktop `.deb` has live systemd side effects

The Debian `postinst` enables and starts:

- `x0tta6bl4-node.service`
- `x0tta6bl4-core-api.service`

This is reasonable for a desktop package only after VM/install testing. Do not install this package on a main workstation without a rollback plan.

### Medium: pytest default mode is bad for focused checks

`pyproject.toml` has:

```text
addopts = "-v --maxfail=10 --cov=src --cov-report=term-missing --cov-report=html"
```

Focused tests fail on coverage even when all selected tests pass. Use `--no-cov` for targeted audits, or create a separate focused-test command.

## Recommended next actions

1. Freeze merge/deploy of the whole dirty tree.
2. Split changes into four packets:
   - Ubuntu desktop app
   - first-party VPN protocol/library
   - first-party VPN deployment/client-kit tooling
   - agent installer/runtime credential changes
3. Fix or quarantine ML-DSA client-kit signing flakiness before claiming client-kit export readiness.
4. Replace `agent/scripts/install.sh` local binary copy with a release artifact URL/checksum flow.
5. Build the Ubuntu `.deb` only in a clean worktree or throwaway VM, then install/test there.
6. Prove first-party VPN with an end-to-end TUN traffic test, not only unit tests.
