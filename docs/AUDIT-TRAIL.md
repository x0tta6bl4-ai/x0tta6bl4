# Audit Trail

The Zero-Trust engine writes append-only JSONL audit files through [zerotrust.go](/mnt/projects/agent/internal/security/zerotrust.go).

## Properties

- Each record includes `previous_hash` and `entry_hash`
- Files roll daily as `audit-YYYY-MM-DD.jsonl`
- Retention defaults to `365 days`
- Handshake decisions and policy decisions are both logged

## Logged event classes

- `handshake`: ML-DSA verification outcome, ML-KEM fingerprint, next re-authentication deadline
- `policy.upsert`: least-privilege policy updates and compiled firewall scope
- `policy.decision`: allow or deny decisions for peer actions

## Compliance notes

- The current implementation is tamper-evident rather than physically immutable
- For SOC2-style evidence, mirror these files to immutable object storage or a WORM volume
- Seal daily digests into Rekor or Ethereum L2 if strong non-repudiation is required
