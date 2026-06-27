# Packet 04: DAO Governance Policy Review

## Objective

Review and harden the `dao_governance_policy` dirty-worktree package without
staging unrelated files.

## Scope

- `src/dao/agent_voter.py`
- `src/dao/mapek_threshold_manager.py`
- `src/dao/token_rewards.py`
- `tests/unit/dao/test_mapek_threshold_manager_security_unit.py`
- `tests/unit/dao/test_token_rewards_unit.py`
- `config/dao_policy.json`
- `tests/unit/security/test_tee_attestation.py`
- `tests/unit/services/test_pqc_formal_rotation.py`
- `scripts/ops/summarize_dirty_worktree_review.py`

## Result

Completed. The package is owned by `codex-implementer`, has no unowned paths,
and the DAO package checks pass.

## Fix

`TokenRewards` now fails closed when blockchain settlement is configured but
`gas_guard` is unavailable. It also defers high-gas settlement without clearing
pending rewards.

## Verification

- `python3 -m json.tool config/dao_policy.json >/dev/null`
- `python3 -m py_compile src/dao/agent_voter.py src/dao/mapek_threshold_manager.py src/dao/token_rewards.py tests/unit/dao/test_token_rewards_unit.py tests/unit/services/test_pqc_formal_rotation.py tests/unit/security/test_tee_attestation.py scripts/ops/summarize_dirty_worktree_review.py`
- `git diff --check -- src/dao/agent_voter.py src/dao/mapek_threshold_manager.py src/dao/token_rewards.py tests/unit/dao/test_token_rewards_unit.py config/dao_policy.json tests/unit/security/test_tee_attestation.py tests/unit/services/test_pqc_formal_rotation.py scripts/ops/summarize_dirty_worktree_review.py`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/dao/test_token_rewards_unit.py -q --no-cov`: `32 passed`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/dao tests/unit/services/test_pqc_formal_rotation.py tests/unit/security/test_tee_attestation.py -q --no-cov`: `480 passed, 3 skipped`
