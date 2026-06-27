# Packet 06: Client Reply Readiness

## Objective

Make the remaining `ANTIBLOCK-CLIENTS-01` blocker operationally safe to close
once external testers reply.

## Context

- Goal gate remains `VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE`.
- `ANTIBLOCK-CLIENTS-01` is blocked on two external short replies:
  mobile Happ/Hiddify and restricted/work Wi-Fi.
- The current request packet hash is
  `da1cda1c0817d5563a2c5322080b74197758d5d31a2dae8b2ce235669e409277`.

## Do

- Validate request freshness, request coverage, stdin-only commands, request
  packet hash binding, and reply recorder guards.
- Keep reply recording separate from readiness generation.
- Keep NL/SPB server writes out of this packet.

## Verification

- `python3 -m pytest nl-diagnostics/test_build_remote_client_reply_readiness.py -q --no-cov`
- `python3 -m py_compile nl-diagnostics/build_remote_client_reply_readiness.py`
- `python3 nl-diagnostics/build_remote_client_reply_readiness.py`
- Two dry-run reply validations through
  `record_remote_client_evidence_reply.py`, one for each request id.
