# Packet: repo_hygiene_config

## Objective

Keep the repository dependency manifests and Ghost Access operator templates
installable, reviewable, and safe to use without secrets.

## Files

- `pyproject.toml`
- `requirements.txt`
- `docs/templates/GHOST_ACCESS_DAILY_HEALTH_SUMMARY_TEMPLATE.md`
- `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`
- `tests/unit/security/test_dependency_security_pins_unit.py`

## Do

- Ensure core `pyproject.toml` dependencies can be installed on top of the
  pinned `requirements.txt` lock.
- Keep the MCP dependency present in both manifests.
- Use the real package name `liboqs-python` for the OQS runtime dependency.
- Verify Ghost Access templates have required privacy sections and do not
  contain raw secrets, subscription links, UUIDs, private keys, or QR codes.
- Refresh local editable metadata only with `--no-deps`.

## Do Not

- Delete stale generated `egg-info` directories without explicit approval.
- Widen this packet into a full dependency upgrade.
- Mutate NL production services or run external outreach/payment actions.

## Verification

```bash
PYTHONPATH=. ./.venv/bin/pytest tests/unit/security/test_dependency_security_pins_unit.py -q --no-cov
inline pyproject/requirements installability check
inline Ghost Access daily health and starter incident template policy check
./.venv/bin/python -m pip install -e . --no-deps
./.venv/bin/python -m pip install --no-deps fastapi==0.128.5 starlette==0.52.1
./.venv/bin/python -m pip check
```

