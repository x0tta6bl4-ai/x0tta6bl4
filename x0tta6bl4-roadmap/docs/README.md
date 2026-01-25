# x0tta6bl4 v3.0 Roadmap Dashboard

This directory hosts the public dashboard for Phase 1 Mesh Networking.

## Structure
- `index.html` main dashboard page
- `assets/data/metrics.json` dynamic data file updated by `scripts/update_dashboard.py`
- `assets/js/dashboard.js` front-end logic to render charts
- `docs/` supplementary documentation & issue templates
- `calendar_events.ics` shared calendar events for Phase 1

## Update Vote Counts
```bash
python3 scripts/update_dashboard.py --yes 42 --no 3
```
Commit & push to update GitHub Pages.

## Deployment (GitHub Pages)
1. Enable GitHub Pages: Repository Settings → Pages → Source `main` / root.
2. Commit changes and push.
3. Page will be available at: `https://<org>.github.io/roadmap/`

## Future Enhancements
- Auto-fetch live Snapshot proposal via API
- Historical metrics trends
- Webhook-triggered updates
