# Formal Specification: MAPE-K Self-Healing Liveness & Safety

**Status**: AlphaProof Nexus Blueprint v1.0
**Context**: x0tta6bl4 Formal Proof Pipeline

## 1. Abstract State Machine (ASM)

The MAPE-K loop transitions through the following formal states:

| State | Description | Transitions To |
| :--- | :--- | :--- |
| `IDLE` | Monitoring baseline metrics. | `ANALYZING` (on anomaly) |
| `ANALYZING` | Determining the root cause (Issue). | `PLANNING` |
| `PLANNING` | Selecting a remediation strategy (Action). | `EXECUTING` |
| `EXECUTING` | Applying the action via `SafeActuator`. | `VERIFYING` |
| `VERIFYING` | Observing post-action state. | `IDLE` (success), `COOLDOWN` (fail) |
| `COOLDOWN` | Blocking retries to prevent oscillation. | `IDLE` (after timeout) |
| `SAFE_MODE` | Terminal state for logic/safety violations. | `IDLE` (Operator override ONLY) |

## 2. Formal Invariants (Safety Properties)

These invariants MUST be true at all times. Any violation MUST trigger `SAFE_MODE`.

### I1: `Invariant_No_Concurrent_Recovery`
$\forall n \in Nodes, \forall i \in Issues, |ActiveActions(n, i)| \le 1$
*   *Implementation*: `pending_verifications` must not contain more than one entry per node.

### I2: `Invariant_CoolDown_Enforced`
$\forall a \in Actions, \forall n \in Nodes, \text{Executed}(a, n, t_1) \land \text{Failed}(a, n, t_1) \implies \nexists t_2 \in (t_1, t_1 + \text{Cooldown}): \text{Executed}(a, n, t_2)$
*   *Implementation*: `remediation_cooldowns` must be checked before `SafeActuator` calls.

### I3: `Invariant_Liveness_Progress`
$\text{State} = \text{VERIFYING} \implies \lozenge (\text{State} \in \{IDLE, COOLDOWN, SAFE\_MODE\})$
*   *Implementation*: Verification phase must have a strict timeout.

## 3. Proof Chain (Evidence)

Every transition must emit a `FormalProofFragment`:
1.  **Pre-condition Hash**: $H(State_{prev} + Metrics)$.
2.  **Logic Contract ID**: The invariant checked.
3.  **Post-condition Hash**: $H(State_{next})$.

## 4. Nexus Logic Gate

The `SelfHealingLogicContract` in Python acts as the runtime verifier for this specification. It mirrors the Lean logic intended for the AlphaProof Nexus pipeline.
