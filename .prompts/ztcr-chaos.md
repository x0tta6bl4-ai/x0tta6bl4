# ZTCR — Zero-Trust Chaos Resilience

## Context

MAPE-K self-healing is ineffective if an attacker can forge recovery commands or a compromised node can disrupt consensus. ZTCR adds cryptographic authentication and Byzantine fault tolerance to every recovery action.

ZTCR stands for Zero-Trust Chaos Resilience: no node is trusted by default, every command is signed, every consensus round is verified.

## Architecture Decision

Three-layer security for recovery:

1. **SignedCommand** — every recovery action is HMAC-signed with per-node keys
2. **PBFT Consensus** — recovery actions require 2/3+ node agreement
3. **SVIDSigner** — SPIFFE Verifiable Identity Document binds node identity to its public key via SPIRE

## SPEC

### Module: `src/self_healing/signed_command.py`

```
class SignedCommand:
    """Immutable, signed recovery command."""
    
    command_id: str      # UUID4
    node_id: str         # Source node
    action: str          # Action type (restart, rekey, reroute, migrate)
    params: dict         # Action parameters
    timestamp: float     
    signature: bytes     # HMAC-SHA256 signature
    svid: str            # SPIFFE SVID for identity binding
    
    @classmethod
    def create(cls, action: str, params: dict, signer: Signer) -> SignedCommand
    def verify(self, verifier: Verifier) -> tuple[bool, str]  # (valid, reason)
    @classmethod
    def from_bytes(cls, data: bytes) -> SignedCommand
    def to_bytes(self) -> bytes
```

### Module: `src/self_healing/anomaly_consensus.py`

```
class PBFTConsensus:
    """PBFT-style consensus for anomaly recovery commands."""
    
    async def propose(self, command: SignedCommand) -> ConsensusRound
    async def vote(self, round_id: str, accept: bool) -> None
    async def get_result(self, round_id: str) -> ConsensusResult | None
    
    # States: PRE_PREPARE, PREPARE, COMMIT, EXECUTED, REJECTED
```

### Module: `src/self_healing/svid_signer.py`

```
class SVIDSigner:
    """SPIFFE-compatible identity binding for PBFT messages."""
    
    async def sign_message(self, message: bytes, svid_path: str) -> bytes
    async def verify_message(self, message: bytes, signature: bytes, svid: str) -> bool
    async def get_node_svid(self, node_id: str) -> str | None
```

## CONSTRAINTS

1. **Keys are never hardcoded.** SignedCommand keys come from SPIRE agent, not config files.
2. **Consensus is async.** PBFT rounds have configurable timeouts to handle network partitions.
3. **SVID is validated.** Every signature is verified against the SPIFFE chain — not just parsed.
4. **No single point of failure.** PBFT requires 2/3+ nodes — a single compromised node cannot force recovery.

## VERIFICATION

```bash
python3 -m pytest tests/unit/self_healing/test_svid_signer.py -v
python3 -m pytest tests/unit/self_healing/test_anomaly_consensus.py -v
python3 -m pytest tests/unit/self_healing/test_spire_crash_chaos.py -v
# Expect: 29/29 tests passed
```

## CHAOS TEST SCENARIOS

| Test | What Happens | Expected Recovery |
|------|-------------|-------------------|
| SPIRE crash | `docker kill spire-server` | SVID rotation → new cert issued within 30s |
| Split-brain | Network partition between 2 of 3 nodes | No recovery commands until 2/3 quorum restored |
| Replay attack | Old SignedCommand replayed | Timestamp + sequence number rejection |
| Invalid SVID | Forged SPIFFE identity | Signature verification fails, command dropped |
| Double-spend | Same command proposed twice | PBFT round deduplication |

## EDGE CASES

1. **SPIRE agent unreachable** — use cached SVID, retry with backoff.
2. **Clock skew** — SignedCommand timestamps allow 5s tolerance.
3. **PBFT timeout** — exponential backoff, circuit breaker after 3 rounds.
4. **SVID expired** — immediate re-attestation via SPIRE agent.
5. **Key compromise** — emergency mode: rotate all keys, invalidate all pending commands.
