# Integration Spine Code Wiring Evidence

Generated: `2026-05-21T05:32:31Z`
Status: `VERIFIED HERE`
Decision: `LOCAL_CODE_WIRING_VERIFIED`
Completion decision: `NOT_COMPLETE`
Goal can be marked complete: `False`

## Claim Boundary

Local integration spine contract only. It proves fail-closed wiring between identity, event bus, policy engine, safe actuator, and settlement/reward adapters; it does not prove production rollout, customer traffic, or live on-chain settlement.

## Summary

- `required_wiring_keys_total`: `5`
- `wiring_keys_covered`: `5`
- `trace_cases_total`: `7`
- `trace_cases_passed`: `7`
- `trace_cases_failed`: `0`
- `success_event_sequence_verified`: `True`
- `canonical_identity_consistent`: `True`
- `policy_before_actuator_verified`: `True`
- `simulated_actuator_blocks_settlement`: `True`
- `settlement_failure_fails_closed`: `True`
- `simulated_settlement_fails_closed`: `True`
- `token_rewards_local_only_fails_closed`: `True`

## Wiring Covered

- `event_bus`: IntegrationSpine publishes the same request identity through EventBus stage/block/fail events.
- `identity`: SpineIdentity carries node_id, spiffe_id, DID, and wallet through every emitted event.
- `policy_engine`: A real zero-trust PolicyEngine allow/deny decision gates actuator execution.
- `safe_actuator`: SafeActuator blocks failed or simulated execution before settlement.
- `settlement_reward_loop`: reward_manager.reward_relay is called only after identity, policy, and actuator success and fails closed on backend false/error/simulated status.

## Trace Cases

- `success_identity_event_policy_actuator_settlement`: passed=`True`, status=`COMPLETED`, events=`coordination.request,pipeline.stage_start,pipeline.stage_end`, executor_calls=`1`, reward_calls=`1`
- `identity_rejected_before_policy_actuator_settlement`: passed=`True`, status=`IDENTITY_REJECTED`, events=`task.blocked`, executor_calls=`0`, reward_calls=`0`
- `policy_denied_before_actuator_settlement`: passed=`True`, status=`POLICY_DENIED`, events=`coordination.request,task.blocked`, executor_calls=`0`, reward_calls=`0`
- `simulated_actuator_blocks_settlement`: passed=`True`, status=`ACTUATOR_SIMULATED`, events=`coordination.request,pipeline.stage_start,task.failed`, executor_calls=`1`, reward_calls=`0`
- `settlement_backend_failure_fails_closed`: passed=`True`, status=`SETTLEMENT_FAILED`, events=`coordination.request,pipeline.stage_start,task.failed`, executor_calls=`1`, reward_calls=`1`
- `simulated_settlement_backend_fails_closed`: passed=`True`, status=`SETTLEMENT_FAILED`, events=`coordination.request,pipeline.stage_start,task.failed`, executor_calls=`1`, reward_calls=`1`
- `token_rewards_local_only_fails_closed`: passed=`True`, status=`SETTLEMENT_FAILED`, events=`coordination.request,pipeline.stage_start,task.failed`, executor_calls=`1`, reward_calls=`1`

## Source Files

- `src/integration/spine.py`
- `src/integration/code_wiring.py`
- `src/dao/token_rewards.py`
- `tests/unit/test_integration_spine.py`

## Not Complete Because

- This is executable local contract wiring, not a production rollout.
- External X0T settlement receipt and live RPC verification are still separate production evidence gates.
- Operator-captured production raw evidence bundles are still required before production closeout.
