# First-party VPN Production Readiness

- ok: `true`
- evidence_dir: `/mnt/projects/nl-diagnostics/firstparty-production-readiness-20260606T214343Z`
- deployment_epoch: `local-firstparty-production-readiness-20260606T214343Z`
- decision_allowed: `true`
- pqc_runtime_metadata_matches_manifest: `True`
- source_tree_hash: `74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26`
- collected:
  - dataplane: `true`
  - external_policy_source: `true`
  - identity_signer: `true`
  - leak_protection: `true`
  - linux_preflight: `true`
  - pqc: `true`
  - rekey_policy: `true`
  - rollout_gate: `true`
  - source_audit: `true`
  - zero_trust_policy: `true`
- scope: local loopback only; no NL/SPB writes; no OS mutation
