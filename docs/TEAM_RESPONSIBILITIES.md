# Team Responsibilities (Swarm Session)

Last updated: 2026-02-21

This file is the operational ownership map for the current parallel session.
If a file is not listed in your agent scope, do not stage or commit it.

## Agent scopes

### agent1-ml-core

- `src/ml/__init__.py`
- `src/ml/graphsage_anomaly_detector.py`
- `tests/unit/ml/test_graphsage_anomaly_detector_unit.py`

### agent2-ml-rag

- `src/ml/rag.py`
- `src/api/maas_analytics.py`
- `docs/STATUS.md`

### agent3-supply-chain

- `src/api/maas_supply_chain.py`
- `src/api/maas_playbooks.py`
- `src/database/__init__.py`
- `alembic/versions/0005_supply_chain_and_playbook_acks.py`
- `tests/api/test_maas_supply_chain.py`

### agent4-devops-ci

- `.gitlab-ci.yml`
- `docker/Dockerfile.api`
- `docker/Dockerfile.controller`
- `docker/Dockerfile.worker`
- `tests/load/maas_load_test.js`
- `tests/load/run_load_tests.sh`
- `src/services/maas_auth_service.py`

### lead-coordinator

- `docs/TEAM_RESPONSIBILITIES.md`
- `docs/team/SWARM_OPERATING_MODEL.md`
- `docs/team/swarm_ownership.json`
- `scripts/agents/check_swarm_ownership.py`
- `scripts/agents/swarm_coord.py`
- `scripts/agents/install_swarm_hook.sh`
- `scripts/agents/start_swarm_session.sh`
- `scripts/agents/stop_swarm_session.sh`
- `.githooks/pre-commit`
- `.githooks/post-commit`

## Commit rules

1. Use only your worktree.
2. Stage files explicitly (`git add <path>`).
3. Do not use `git add -A`.
4. Install swarm hook:

```bash
scripts/agents/install_swarm_hook.sh
export SWARM_AGENT=agent1-ml-core  # change per agent
```

Or run session bootstrap (recommended, no manual export needed):

```bash
scripts/agents/start_swarm_session.sh agent1-ml-core
```

5. Optional lease tuning:

```bash
export SWARM_LEASE_TTL=1800
```

6. For full auto coordination session:

```bash
scripts/agents/start_swarm_session.sh agent1-ml-core
# ... work ...
scripts/agents/stop_swarm_session.sh agent1-ml-core
```

7. If cross-scope changes are required, hand off through owner agent.
