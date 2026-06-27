# Formal Specification: eBPF Dataplane Atomic Handover

**Status**: AlphaProof Nexus Blueprint v1.3
**Context**: x0tta6bl4 Dataplane Verification

## 1. Abstract State Machine (Dataplane-ASM)

The eBPF/XDP program lifecycle must ensure that the datapath is never in an inconsistent state during updates.

| State | Description | Transitions To |
| :--- | :--- | :--- |
| `DETACHED` | No XDP program active on interface. | `COMPILING` |
| `COMPILING` | BCC program is being compiled. | `STAGED` (on success) |
| `STAGED` | Program loaded in kernel but not attached. | `ATTACHING` |
| `ATTACHING` | Program being attached to interface. | `ATTACHED` |
| `ATTACHED` | Program active and enforcing PQC. | `DETACHING` (on cleanup) |
| `LOAD_FAILURE`| Error during compile/load. | `DETACHED` |

## 2. Dataplane Formal Invariants

### D1: `Invariant_Atomic_Swap`
$\text{Attach}(Prog_{new}, Iface) \implies \text{Detach}(Prog_{old}, Iface) \text{ is atomic or fail-closed}$
*   The system must not leave the interface without protection if a new program fails to load.

### D2: `Invariant_Map_Consistency`
$\forall s \in GatewaySessions, \exists m \in eBPF\_Maps: m.key = s.id$
*   The eBPF session map must be a consistent projection of the PQC Gateway state.

### D3: `Invariant_Read_Only_Observation`
$\text{Observe}(Dataplane) \implies \text{Mutates}(Dataplane) = \text{False}$
*   Monitoring the dataplane must not affect packet forwarding logic.

## 3. Nexus Dataplane Proof

Every loader operation emits a `DataplaneProofFragment`:
1.  **BCC Fingerprint**: $H(BPF\_Text + CFlags)$.
2.  **Map Sync Vector**: Count of entries synced vs gateway entries.
3.  **Attach Status**: XDP flags used and interface index.
