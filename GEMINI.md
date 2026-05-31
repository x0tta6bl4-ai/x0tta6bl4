# Gemini Operating Rules For x0tta6bl4

This repo is evidence-gated. Do not describe it as production-ready unless the
local readiness gate says so.

## Required Status Check

Before claiming release, production, v4.0 readiness, full stabilization, or
technical debt completion, run:

```bash
python3 scripts/ops/check_real_readiness.py --skip-command-checks --skip-git-check --json
```

Allowed wording:
- If `decision` is `REAL_READINESS_READY`, report what the gate actually
  verified and keep the gate's claim boundary.
- If `decision` is `REAL_READINESS_BLOCKED`, say blocked and name the blocker.

Current known blocker can be `external-dpi-proof-missing`. Do not turn local
startup, local tests, generated OpenAPI, or JSON logs into external DPI,
customer traffic, settlement finality, production SLO, or production readiness
proof.
Local evidence is not production readiness proof.

## Worktree Safety

- Do not suggest committing the entire dirty worktree.
- Do not stage unrelated files.
- Do not delete or move broad directory trees unless the user explicitly asked
  for that exact deletion.
- Treat existing uncommitted changes as someone else's work unless you made
  them in this turn.

## Documentation And Checkboxes

- Do not mark checklist items `[x]` unless the acceptance evidence exists and
  was verified in this session.
- Keep public docs honest. Prefer "research surface", "local evidence", and
  "blocked by current evidence gate" over product claims.
- Preserve links to current truth files: `docs/architecture/CURRENT_*`,
  `docs/verification/*`, and `scripts/ops/check_real_readiness.py`.

## Logging Changes

- `src/core/logging_config.py::setup_logging(name=...)` must return the named
  logger passed by `name`. Do not silently replace it with the root logger.
- If configuring root logging is required, add a separate explicit helper and
  tests.
- Runtime use of `src/core/structured_logging.py` is not proven just because
  its unit tests pass. Verify the actual import path used by `src/core/app.py`.

## External Evidence

- Never ask the user to paste private target URLs, proxy endpoints, operator
  IDs, scope IDs, subscriber data, tokens, or captures into chat.
- Use local scripts for private input, for example:

```bash
python3 scripts/ops/run_external_dpi_intake_local.py --write-ready
```

If the validator rejects the artifact, report `ACTION_REQUIRED`; do not
fabricate evidence.
