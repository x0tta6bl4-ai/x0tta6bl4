# GHOST-CORE / x0tta6bl4_pulse Claim Audit

Date: 2026-05-21
Status: `REPAIRED_TO_EXPERIMENTAL_CLAIM_BOUNDARY`

## Findings

- `ghost-core.sh` previously mixed local simulation with production-style
  dashboard text, including eBPF adaptation claims without live attach proof.
- `src/network/transport/pulse_transport.py` used `os.getenv` and `os.urandom`
  without importing `os`; basic instantiation failed.
- `src/services/ghost_mesh_daemon.py` reported a fixed high pulse-coherence
  percentage; this was a hard-coded metric, not evidence.
- `src/api/leaderboard_api.py` emitted random global leaderboard values and
  fixed global totals.
- `src/services/share_to_earn_service.py` accrued random local rewards by
  default and marked local exit-node simulation as active.
- `docs/MESH_STATUS.md` and `PRODUCT_LAUNCH.md` contained production/global
  claims without matching evidence.

## Repairs

- `ghost-core.sh` now reports eBPF as `NOT_LOADED` unless a `pulse_stats` map is
  actually visible, and it no longer prints the old adaptation-complete banner
  based on randomness.
- `x0tta6bl4_pulse` transport now imports correctly and reports
  `EXPERIMENTAL_LOCAL_TIMING_PROFILE` / `NOT_VERIFIED`.
- Mesh stats now read pulse status from the actual transport stats instead of a
  hard-coded value.
- Share-to-Earn is observe-only unless `GHOST_ENABLE_ECONOMY_SIMULATION=1`.
- Exit-node simulation is disabled unless
  `GHOST_ENABLE_EXIT_NODE_SIMULATION=1`.
- Leaderboard API returns `LOCAL_ONLY_NO_GLOBAL_LEDGER` unless mock data is
  explicitly enabled with `GHOST_ENABLE_MOCK_LEADERBOARD=1`.
- Product/status docs were reset to `NOT_READY_FOR_PRODUCTION_LAUNCH` and
  `LOCAL_EXPERIMENT_NOT_PRODUCTION_VERIFIED`.

## Verification

- `python3 -m py_compile` passed for the repaired modules.
- `bash -n ghost-core.sh` passed.
- `PulseUDPTransport(local_port=0).get_stats()` reports
  `protocol=x0tta6bl4_pulse`, `evidence_status=EXPERIMENTAL_LOCAL_TIMING_PROFILE`,
  and `stealth_mode=NOT_VERIFIED`.
- `create_mesh_node(..., traffic_profile="GHOST_PULSE")` wires
  `PulseUDPTransport` and reports the experimental evidence status.
- No `ghost-core`, `leaderboard`, `share_to_earn`, `mesh_daemon`, or
  `pqc_rotator` test processes remain running after cleanup.

## Remaining Gate

Do not claim `VERIFIED HERE` for x0tta6bl4_pulse as a stealth-access protocol
until there is live XDP attach evidence, map counter evidence, packet captures,
and reproducible local lab measurements.
