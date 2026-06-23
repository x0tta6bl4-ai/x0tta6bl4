# First-party VPN Production Readiness

- ok: `false`
- evidence_dir: `/mnt/projects/nl-diagnostics/firstparty-production-readiness-20260606T213702Z`
- deployment_epoch: `local-firstparty-production-readiness-20260606T213702Z`
- decision_allowed: `false`
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
- decision_reasons: `['pqc_provider_gate_failed']`
- scope: local loopback only; no NL/SPB writes; no OS mutation
