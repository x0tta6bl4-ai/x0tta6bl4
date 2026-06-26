# x0tta6bl4 v3.5.0

- **Tech debt elimination:** 1000+ files refactored
- **Security:** 11 CVEs patched (yt-dlp, starlette, PyJWT)
- **subprocess hardening:** 200+ unsafe calls → safe_run/safe_popen
- **Import hygiene:** 100% `from __future__ import annotations`, 0 missing `__init__.py`
- **Allowlist:** 65 commands, fully synchronized
- **Dead code removal:** charter_client.py, algorithm_update.py dup
- **Git hygiene:** 27 stale stashes dropped, .gitignore extended
- **ROADMAP.md:** updated for current state
