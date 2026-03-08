# AI Launchers

Repo-local launcher wrappers for `gemini`, `claude`, and `codex`.

## Purpose

These wrappers keep process-local settings out of shell history and reduce
operator drift:

- Node/V8 heap size via `NODE_OPTIONS=--max-old-space-size=...`
- optional proxy routing
- Gemini `--resume` convenience path

They are operator conveniences only. They are not release evidence and do not
change any `VERIFIED HERE`, `SIMULATED`, or `NOT VERIFIED YET` state.

## Enable

```bash
export PATH="$PWD/bin:$PATH"
```

## Wrappers

### `bin/gemini`

Defaults:

- `AI_HEAP_MB=4096`
- `GEMINI_USE_PROXY=1`
- `GEMINI_PROXY_URL=http://127.0.0.1:7890`
- reuses `scripts/agents/start_gemini_proxy.sh`

Examples:

```bash
bin/gemini
GEMINI_AUTO_RESUME=1 bin/gemini
GEMINI_PRINT_ENV=1 GEMINI_NO_EXEC=1 bin/gemini --resume
```

### `bin/gemini-resume`

Short alias for the common OOM-recovery path:

- defaults `AI_HEAP_MB=6144`
- defaults `GEMINI_AUTO_RESUME=1`

Example:

```bash
bin/gemini-resume
GEMINI_NO_EXEC=1 GEMINI_PRINT_ENV=1 bin/gemini-resume
```

### `bin/claude-code`

Defaults:

- `AI_HEAP_MB=4096`
- `CLAUDE_USE_PROXY=0`

Examples:

```bash
bin/claude-code
CLAUDE_PRINT_ENV=1 CLAUDE_NO_EXEC=1 bin/claude-code
CLAUDE_USE_PROXY=1 bin/claude-code
```

### `bin/codex`

Defaults:

- `AI_HEAP_MB=4096`
- `CODEX_USE_PROXY=0`

Examples:

```bash
bin/codex
CODEX_PRINT_ENV=1 CODEX_NO_EXEC=1 bin/codex exec
CODEX_USE_PROXY=1 bin/codex
```

### `bin/ai`

Router entrypoint:

```bash
bin/ai gemini
bin/ai claude
bin/ai codex
bin/ai --profile validation gemini --resume
```

### `bin/ai-verify` and `bin/ai-validate`

Short aliases for the two execution contours:

```bash
bin/ai-verify claude
bin/ai-verify codex
bin/ai-validate gemini --resume
```

Profiles:

- `verification` -> default `AI_HEAP_MB=4096`
- `validation` -> default `AI_HEAP_MB=6144`

If `AI_HEAP_MB` is already exported, `bin/ai` does not override it.

## Recommended usage

### Verification

```bash
bin/ai --profile verification claude
bin/ai --profile verification codex
bin/ai --profile verification gemini
```

### Validation

```bash
bin/ai --profile validation gemini --resume
bin/ai --profile validation codex
bin/gemini-resume
bin/ai-validate gemini --resume
```

## Coordination note

These wrappers do not open or close coordination sessions by themselves.
Continue to use:

```bash
bash scripts/agent-coord.sh session_start <agent> --mode verification "summary"
bash scripts/agent-coord.sh session_start <agent> --mode validation "summary"
```

Treat a child Gemini process started through `bin/gemini` as a disposable
subprocess for recovery or heavy execution, not as a new autonomous agent lane.
