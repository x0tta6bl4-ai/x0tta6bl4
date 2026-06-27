# Packet: nl_runtime_diagnostics

## Objective

Keep NL production-adjacent diagnostics reviewable without mutating production
VPN services.

## Files

- `nl-diagnostics/nl-legacy-client-migration-progress-2026-06-05.json`
- `nl-diagnostics/nl-legacy-client-migration-replies-2026-06-05.json`
- `nl-diagnostics/nl-legacy-no-progress-nudge-dry-run-latest.json`
- `nl-diagnostics/nl-live-subscription-payload-latest.json`
- `nl-diagnostics/nl-no-progress-nudge-guarded-send-latest.json`
- `nl-diagnostics/nl-no-progress-nudge-review-latest.json`
- `nl-diagnostics/nl-transport-usage-latest.json`
- `nl-diagnostics/incidents/`

## Do

- Run only local compile, unit, JSON-parse, and redaction checks.
- Preserve the distinction between historical incident evidence and current
  approval for production actions.
- Keep `x-ui`, `xray`, `ghost-access-*`, and NL VPN listeners untouched.

## Do Not

- SSH to NL for mutating commands.
- Restart, stop, disable, mask, kill, or edit production services/timers/crons.
- Store raw subscription links, UUIDs, bot tokens, private keys, or payment
  data.

## Verification

```bash
find services/nl-server -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile
PYTHONPATH=. ./.venv/bin/pytest services/nl-server/tests -q --no-cov
python3 -m json.tool <each dirty nl-diagnostics JSON file> >/dev/null
PYTHONPATH=. ./.venv/bin/pytest nl-diagnostics/test_*.py -q --no-cov
```
