# Redacted NL Source Reviews

This directory is for sanitized review copies only.

Rules:

- files here are not deployable;
- raw source that contains links, tokens, UUIDs, or keys must never be stored here;
- each redacted file must have a `.meta.json` with source path, raw hash, redacted hash, and redaction counts;
- promotion from this directory is forbidden without manual source reconstruction.

Use:

```bash
python3 services/nl-server/tools/pull_candidate_redacted.py
python3 services/nl-server/tools/pull_candidate_redacted.py --pull
```
