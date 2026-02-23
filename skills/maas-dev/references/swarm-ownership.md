# Swarm Ownership Map — x0tta6bl4

`docs/team/swarm_ownership.json` defines which SWARM_AGENT can commit which files.
Ownership check runs via `.githooks/pre-commit` → `scripts/agents/check_swarm_ownership.py`.

## Known Agents

| Agent | Description | Key Scope |
|-------|-------------|-----------|
| `codex-implementer` | Main implementation lane | `src/api/maas/**`, `tests/unit/api/**`, most new src/tests |
| `claude-maas-reviewer` | MaaS RBAC, security review | `src/api/maas_auth.py`, `tests/api/test_maas_*.py` |
| `lead-coordinator` | Swarm governance | `docs/team/swarm_ownership.json` only |
| `agent4-devops-ci` | CI/CD and containers | `.gitlab-ci.yml`, `docker/`, `tests/load/` |
| `agent3-supply-chain` | Supply chain / playbooks | `src/api/maas_supply_chain.py`, `src/api/maas_playbooks.py` |

## Flow for New Files

### 1. Edit swarm_ownership.json
Add new file paths to `codex-implementer.allow`:
```json
"tests/unit/api/endpoints/test_mymod_unit.py",
"src/api/maas/endpoints/mymod.py"
```

### 2. Commit ownership file as lead-coordinator
```bash
git restore --staged <new-files>          # unstage new files first
SWARM_AGENT=lead-coordinator git add docs/team/swarm_ownership.json
SWARM_AGENT=lead-coordinator git commit -m "chore(swarm): add mymod to codex-implementer scope"
```

### 3. Commit new files as codex-implementer
```bash
SWARM_AGENT=codex-implementer git add src/api/maas/endpoints/mymod.py tests/unit/api/endpoints/test_mymod_unit.py
SWARM_AGENT=codex-implementer git commit -m "feat(maas): add mymod endpoint"
```

## Full codex-implementer Scope (key paths)

- `src/api/maas/endpoints/nodes.py`
- `src/api/maas/endpoints/combined.py`
- `src/api/maas/endpoints/billing.py`
- `src/api/maas/endpoints/batman.py`
- `src/api/maas/services.py`
- `src/api/maas/models.py`
- `src/api/maas_nodes.py`
- `src/api/maas_telemetry.py`
- `tests/unit/api/endpoints/test_nodes_unit.py`
- `tests/unit/api/endpoints/test_combined_unit.py`
- `tests/unit/api/endpoints/test_batman_unit.py`
- `tests/unit/api/test_maas_telemetry.py`
- `tests/unit/self_healing/test_mape_k_unit.py`
- `tests/unit/self_healing/test_recovery_actions_unit.py`
- `tests/unit/consensus/test_raft_snapshots.py`
- `src/network/ebpf/metrics/exceptions.py`
- Most `src/security/**`, `src/network/**`, `src/services/**`, `src/llm/**`

## Full claude-maas-reviewer Scope

- `src/api/maas_auth.py`
- `tests/api/test_maas_analytics.py`
- `tests/api/test_maas_nodes.py`
- `tests/api/test_maas_billing.py`
- `tests/api/test_maas_auth.py`
- `tests/unit/api/test_maas_security_unit.py`
- `tests/unit/services/test_maas_analytics_service.py`

## Error: "non-owned staged files"

If you get this error, check which agent owns the file:
```bash
python3 scripts/agents/check_swarm_ownership.py --agent codex-implementer --dry-run
```

Then either switch agent or add file to the correct agent's scope.
