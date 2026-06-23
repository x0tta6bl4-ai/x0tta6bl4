# Packet: repo_coordination_mcp

## Objective

Keep local Codex/MCP operator tooling and dirty-worktree ownership review
reproducible.

## Files

- `docs/team/swarm_ownership.json`
- `pyproject.toml`
- `requirements.txt`
- `scripts/verify_codex_environment.py`
- `scripts/mcp/github_mcp_stdio.sh`
- `mcp-server/src/operator_tools.py`
- `mcp-server/src/spb_readonly_tools.py`
- `mcp-server/test_operator_tools.py`
- `tests/unit/test_spb_readonly_tools.py`

## Do

- Ensure every dirty path has an owner candidate.
- Record the `mcp` dependency required by local MCP servers and tests.
- Run focused MCP/SPB tests and the fast local Codex environment verifier.
- Keep GitHub MCP disabled unless `GITHUB_MCP_PAT` is explicitly exported
  locally.

## Do Not

- Enable GitHub MCP without a locally valid token.
- Paste or store private tokens in chat or workflow files.
- Mutate NL production services.

## Verification

```bash
python3 -m json.tool docs/team/swarm_ownership.json >/dev/null
bash scripts/agents/check_coordination_contract.sh
python3 -m py_compile scripts/verify_codex_environment.py
bash -n scripts/mcp/github_mcp_stdio.sh
PYTHONPATH=. ./.venv/bin/pytest tests/unit/test_spb_readonly_tools.py mcp-server/test_operator_tools.py -q --no-cov
python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json
python3 scripts/verify_codex_environment.py --skip-slow-mcp
```
