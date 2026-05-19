# Dependency Source Of Truth — 2026-04-28

This note records the current dependency-file order after the `liboqs-python`
cleanup pass on `fix-ci-pipelines`.

## Tracked Source Of Truth

The tracked dependency files that currently matter to repo automation are:

- `requirements.txt`
- `requirements.lock`
- `pyproject.toml`

Observed evidence:

- Git tracks `requirements.txt`, `requirements.lock`, and `pyproject.toml`.
- GitHub workflows install from `requirements.txt`.
- Security workflows audit `requirements.lock`.

## Draft Files Removed From Repo Root

The following files were present as untracked drafts in the repo root:

- `requirements.in`
- `requirements-full.txt`
- `requirements-x0tta6bl4.txt`

They had no live references outside archived inventory output and were removed
from the repo root to stop them from polluting `git status`.

Archived copies were preserved outside the repo root at:

- `/tmp/x0tta6bl4-dependency-drafts-20260428/requirements.in`
- `/tmp/x0tta6bl4-dependency-drafts-20260428/requirements-full.txt`
- `/tmp/x0tta6bl4-dependency-drafts-20260428/requirements-x0tta6bl4.txt`

SHA-256 at archival time:

- `requirements.in`: `7f3678103cd018eda5f99e5a2c75e7f91d9fca4db4e0e490ce4f7d4819a7915c`
- `requirements-full.txt`: `1f65fa5b847ba02eb549fec7c84b628658049f5f586b8a2fa684af0230d8e124`
- `requirements-x0tta6bl4.txt`: `0c13e1fffa09f26ccff16a258df631cbdaa1d3f949b8742b1357b1942b95f26e`

## Current Rule

Until the repo intentionally adopts a different dependency workflow:

- update `requirements.txt` and `requirements.lock` together
- do not reintroduce root-level draft dependency files
- treat any future `requirements.in` resurrection as a deliberate toolchain
  decision, not an incidental side effect of local repair work
