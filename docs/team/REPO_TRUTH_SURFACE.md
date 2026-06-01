# Repo Truth Surface

Last updated: 2026-06-01

This document defines which repo files can be used as current evidence and
which files are only planning, sales, or historical material. It is a routing
guide for agents and operators. The enforceable check is
`scripts/claim_hygiene_scan.py`.

## Trust Zones

### authoritative

Current evidence and operating truth:

- `STATUS_REALITY.md`
- `docs/verification/**`
- `docs/research/**`
- `.claude/rules/**`
- this file

Use these files before repeating claims from README, commercial pages, landing
pages, old roadmaps, or archived material.

### active_claim_surface

Current public or customer-facing surfaces:

- `README.md`
- `index_maas.html`
- `x0tta6bl4.yaml`
- `docs/commercial/**`
- `docs/product/**`
- `docs/release/**`
- `business/**`
- `go-to-market/**`
- `web/**`

Before changing these files, run:

```bash
bash scripts/agent-coord.sh claim_hygiene_scan --zone active_claim_surface --fail-on-active
```

The gate must have `active=0` before a change is treated as clean.

### aspirational

Planning and desired-future material:

- `docs/vision/**`
- `plans/**`
- `deploy/**`
- `config/**`
- `charts/**`
- `chaos/**`
- `grafana/**`

These files may describe targets, pitch language, persona language, or future
architecture, but they are not evidence that a capability is delivered.

### legacy

Historical and archived material:

- `archive/**`
- `docs/archive/**`
- `backups/**`
- `root_archive/**`

Do not quote these files as current truth without an explicit historical caveat.

## Claim Rules

High-risk public claims require fresh artifacts in the authoritative zone:

- production readiness or production deployment
- production traffic validation
- field-validated 5G, LoRa, or DP backend claims
- high PPS or benchmark claims
- uptime or MTTR claims
- Rekor-backed supply-chain claims
- stronger SPIRE/PQ claims than `standard leaf SVID + detached PQ attestation`

When in doubt, prefer the narrower wording in `STATUS_REALITY.md` and the
current `docs/verification/release-gate-v1.1.md` decision.

## Commands

```bash
bash scripts/agent-coord.sh claim_hygiene_scan --zone authoritative --fail-on-active
bash scripts/agent-coord.sh claim_hygiene_scan --zone active_claim_surface --fail-on-active
pytest -q tests/test_claim_hygiene_scan.py --no-cov
```

The normal repo pytest configuration enables repo-wide coverage gates, so use
`--no-cov` for this focused scanner regression test.
