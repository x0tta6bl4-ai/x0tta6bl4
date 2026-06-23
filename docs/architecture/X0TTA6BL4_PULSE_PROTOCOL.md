# x0tta6bl4 Pulse Protocol Boundary

Status: `LOCAL_EXPERIMENT_NOT_PRODUCTION_PROOF`

This document is the current claim boundary for Ghost Pulse timing evidence.
The implemented checks can show deterministic local sender-side timing plans,
loopback packet delivery, and replayable seed-derived profiles.

They do not prove:

- external DPI bypass;
- provider whitelist behavior;
- customer traffic delivery;
- anonymity;
- kernel/XDP attach on a production host;
- production readiness.

Promotion rule: a Pulse claim can move beyond local timing evidence only when
the corresponding Ghost Pulse proof-gate row is backed by current imported
external evidence and the cross-plane proof gate allows the requested claim.
