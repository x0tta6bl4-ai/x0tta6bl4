# NL Server Quarantine

This directory is for local read-only intake from NL.

Rules:

- content under `incoming/` is git-ignored;
- files here are not deployable;
- blocked files must not be copied into source paths;
- promote files to `services/nl-server/<component>/` only after manual review.

Recommended dry run:

```bash
python3 services/nl-server/tools/pull_candidate_readonly.py --priority P1
```

Explicit local intake:

```bash
python3 services/nl-server/tools/pull_candidate_readonly.py --priority P1 --pull
```
