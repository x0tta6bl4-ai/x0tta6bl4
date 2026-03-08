# MaaS v3.4.0 Launch Kit (GTM + Product Hunt)
Last updated: 2026-03-05

This folder is the canonical launch package for P2.

## Files

- `PH_ASSETS_MAAS_2026.md` — Product Hunt listing copy, maker comment, replies, social snippets.
- `PH_SUBMISSION_READY_MAAS_v3_4_0.md` — copy-paste submission form payload for Product Hunt.
- `GTM_ONE_PAGER_MAAS_v3_4_0.md` — sales-ready one-pager for CTO/CISO and platform teams.
- `GTM_OUTREACH_PACK_MAAS_v3_4_0.md` — cold outreach and follow-up templates for post-launch pipeline.
- `DEMO_FLOW_DAO_HELM_UPGRADE.md` — demo script for `propose -> vote -> execute -> helm upgrade`.
- `LAUNCH_CHECKLIST_MAAS_v3_4_0.md` — launch day execution checklist (T-7 to T+1).
- `CLAIMS_EVIDENCE_MATRIX_MAAS_v3_4_0.md` — claim governance and evidence links.

## Asset Generation

Run:

```bash
python3 marketing/generate_assets.py
```

Outputs:
- `marketing/app_connected.svg`
- `marketing/ph_launch_card.svg`

## Guardrails

- Do not claim ISO certification; claim readiness baseline only.
- Do not claim automated on-chain Helm execution as GA; this is planned next-phase work.
- Every public claim must map to evidence in repository files.
