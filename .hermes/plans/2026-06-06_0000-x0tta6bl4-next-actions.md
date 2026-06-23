# x0tta6bl4 Next Actions Plan

> **For Hermes:** Use x0tta6bl4 thinking contract: evidence first, explicit claim boundaries, small reversible actions, verify after every step.

**Goal:** Turn the current large dirty worktree into reviewable, tested, safe packages without overclaiming production readiness.

**Current evidence:**
- `scripts/ops/summarize_dirty_worktree_review.py --json` returned `DIRTY_WORKTREE_UNOWNED_PATHS_BLOCKED`.
- `ready_to_release=false`, `owner_review_ready=false`.
- Dirty paths: `815`; unowned paths: `46`.
- Top changed areas: `src`, `tests`, `nl-diagnostics`, `services`, `scripts`, `docs`, `src-tauri`, `x0tta6bl4-app`, `agent`.

**Claim boundary:** This plan is only a local recovery/review plan. It does not prove production readiness, customer traffic, live dataplane delivery, settlement finality, or production SLOs.

---

## Phase 1 — Freeze and inventory

### Task 1: Stop broad changes

**Objective:** Prevent the dirty tree from becoming unrecoverable.

**Rules:**
- Do not run `git add -A`.
- Do not run `git add .`.
- Do not commit the whole tree.
- Do not stop/restart NL VPN services unless there is a current explicit incident reason.

**Verification:**
```bash
cd /mnt/projects
python3 scripts/ops/summarize_dirty_worktree_review.py --json
```

Expected: still reports packages and unowned paths, no mutation.

---

## Phase 2 — Clear blocker: unowned paths

### Task 2: Classify the 46 unowned paths

**Objective:** Decide for each unowned path whether it is scratch, real source, diagnostic evidence, or release artifact.

**Command:**
```bash
cd /mnt/projects
python3 scripts/ops/summarize_dirty_worktree_review.py --json > /tmp/x0tta6bl4-dirty-review.json
python3 - <<'PY'
import json
p='/tmp/x0tta6bl4-dirty-review.json'
d=json.load(open(p))
for path in d.get('unowned_paths', []):
    print(path)
PY
```

**Decision rule:**
- Scratch/debug files: move to a maintained diagnostics path or delete only after review.
- Real source files: add to `docs/team/swarm_ownership.json` with owner.
- Screenshots/evidence: keep only if linked from an evidence doc.
- Client config artifacts: quarantine unless verified by distribution gate.

**Verification:**
```bash
python3 -m json.tool docs/team/swarm_ownership.json >/dev/null
bash scripts/agents/check_coordination_contract.sh
```

---

## Phase 3 — Stabilize review packages in safe order

### Task 3: Evidence readiness package first

**Why first:** It controls the gates that tell us what is true.

**Package:** `evidence_readiness`, 17 paths.

**Checks:**
```bash
cd /mnt/projects
python3 -m py_compile scripts/ops/check_real_readiness.py scripts/ops/summarize_dirty_worktree_review.py scripts/ops/verify_traffic_delivery_operator_flow.py
PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_check_real_readiness_unit.py tests/unit/scripts/test_summarize_dirty_worktree_review.py tests/unit/scripts/test_verify_traffic_delivery_operator_flow.py tests/unit/test_real_readiness_gate_doc_unit.py tests/unit/test_cross_plane_evidence_map_unit.py tests/unit/test_autonomous_mesh_reality_map_unit.py -q --no-cov
PYTHONPATH=. ./.venv/bin/python scripts/ops/check_real_readiness.py --json --skip-git-check
```

**Success:** No syntax errors; tests pass; readiness output remains explicit about blockers and claim boundaries.

---

### Task 4: NL runtime diagnostics package second

**Why second:** NL VPN is live operational infrastructure; diagnostics must stay safe and read-only unless explicitly authorized.

**Package:** `nl_runtime_diagnostics`, 199 paths.

**Checks:**
```bash
cd /mnt/projects
find services/nl-server -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile
PYTHONPATH=. ./.venv/bin/pytest services/nl-server/tests -q --no-cov
bash scripts/vpn_status.sh --check --no-color
```

**Safety:** Do not stop, disable, mask, or pkill `x-ui.service`, `xray`, `ghost-access-*`, or NL VPN listeners.

---

### Task 5: Desktop/native app package third

**Why third:** It is product-visible and already has build/test evidence from the audit.

**Package:** `frontend_native_app`, 16 paths.

**Checks:**
```bash
cd /mnt/projects
npm --prefix x0tta6bl4-app run build
cd /mnt/projects/src-tauri && CARGO_TARGET_DIR=/tmp/x0tta6bl4-cargo-check-next cargo check
cd /mnt/projects
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='' pytest --no-cov -q src-tauri/runtime/test_desktop_core_api_unit.py tests/unit/core/test_app_desktop_live_snapshot_unit.py
```

**Success:** Build and focused tests pass. Do not install `.deb` on the main workstation without rollback plan.

---

### Task 6: MaaS API compatibility package fourth

**Why fourth:** It touches API auth/billing/compat surfaces and must not regress control-plane behavior.

**Package:** `maas_api_compat`, 34 paths.

**Checks:**
```bash
cd /mnt/projects
python3 -m py_compile src/api/maas_auth.py src/api/maas_legacy.py src/api/maas_compat.py src/api/maas_billing.py
PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_package_compat_unit.py -q --no-cov
PYTHONPATH=. ./.venv/bin/python - <<'PY'
import src.core.app
print('app_import_ok')
PY
```

**Success:** Compat imports and focused tests pass.

---

## Phase 4 — Fix known high-risk issue

### Task 7: Investigate ML-DSA client-kit signing flakiness

**Objective:** Find root cause before changing code.

**Known symptom:**
```text
MlDsaShapeError: ML-DSA signature hint vector exceeds omega
```

**Known tests:**
```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='' pytest --no-cov -q tests/unit/scripts/test_vpn_systemd_templates_unit.py::test_firstparty_verify_client_kits_accepts_signed_archives tests/unit/scripts/test_vpn_systemd_templates_unit.py::test_firstparty_verify_client_kits_can_require_live_readiness
```

**Process:** Use systematic debugging:
1. Reproduce in loop.
2. Identify whether failure is RNG/input/reference-signer state/order dependent.
3. Add a regression test only after root cause is known.
4. Fix the source, not the symptom.

---

## Phase 5 — Commit discipline

### Task 8: Commit only one verified package at a time

**Objective:** Make each change reviewable.

**Rules:**
- Stage exact package paths only.
- Use `SWARM_AGENT` required by ownership.
- Commit after checks pass.

**Example pattern:**
```bash
SWARM_AGENT=codex-implementer git add -- <exact paths from one package>
SWARM_AGENT=codex-implementer git commit -m "chore(evidence): stabilize readiness package"
```

**Never:**
```bash
git add -A
git add .
```

---

## Recommended immediate next action

Start with Phase 2: classify and resolve the 46 unowned paths. Until that is cleared, the worktree remains blocked and not review-ready.
