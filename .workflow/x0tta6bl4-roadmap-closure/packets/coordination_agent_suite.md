# Packet: coordination_agent_suite

## Objective

Verify the local coordination agent suite and refresh stale source references
in policy/evidence maps that block the policy-map unit guard.

## Files

- `docs/team/swarm_ownership.json`
- `scripts/agent-coord.sh`
- `scripts/agents/`
- `.githooks/pre-commit`
- `.githooks/post-commit`
- `docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json`
- `docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json`
- `tests/unit/scripts/test_agent_work_receipt_gate.py`
- `tests/unit/scripts/test_security_scan_template_unit.py`
- `tests/unit/scripts/test_summarize_dirty_worktree_review.py`
- `tests/unit/scripts/test_check_real_readiness_unit.py`
- `tests/unit/test_policy_enforcement_map_unit.py`
- `tests/unit/test_cross_plane_evidence_map_unit.py`
- `tests/unit/test_real_readiness_gate_doc_unit.py`

## Do

- Validate the coordination ownership map and hook contract.
- Compile local coordination agents and shell wrappers.
- Run the safe local agent smoke suite.
- Verify focused coordination, dirty-worktree, policy-map, and evidence-map
  unit tests.
- Update stale `nodes.py` source references only where they block current
  policy/evidence guards.

## Do Not

- Run destructive agents, production VPN actions, outreach, publication, broad
  staging, or commits.
- Treat local agent smoke tests as proof of production runtime health.
- Sweep unrelated architecture-map stale references in this packet.

## Verification

```bash
python3 -m json.tool docs/team/swarm_ownership.json >/dev/null
bash scripts/agents/check_coordination_contract.sh
find scripts/agents -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile
find scripts/agents -maxdepth 1 -name '*.sh' -print0 | xargs -0 bash -n
find scripts/agents -maxdepth 1 -name '*.json' -print0 | xargs -0 -I{} python3 -m json.tool {} >/dev/null
PYTHONPATH=. ./.venv/bin/python scripts/agents/test_all_agents.py
PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_agent_work_receipt_gate.py tests/unit/scripts/test_security_scan_template_unit.py -q --no-cov
PYTHONPATH=. ./.venv/bin/python scripts/agents/check_swarm_ownership.py --agent lead-coordinator --print-scope
bash -n scripts/agent-coord.sh scripts/agents/request_channel.sh scripts/agents/start_swarm_session.sh scripts/agents/stop_swarm_session.sh scripts/agents/install_swarm_hook.sh
PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_summarize_dirty_worktree_review.py tests/unit/test_policy_enforcement_map_unit.py tests/unit/scripts/test_check_real_readiness_unit.py::test_swarm_coordination_contract_failure_blocks_readiness -q --no-cov
python3 -m json.tool docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json >/dev/null && python3 -m json.tool docs/architecture/CURRENT_EVIDENCE_RUNTIME_BRIDGE_MAP.json >/dev/null
PYTHONPATH=. ./.venv/bin/pytest tests/unit/test_cross_plane_evidence_map_unit.py tests/unit/test_real_readiness_gate_doc_unit.py -q --no-cov
python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json
```
