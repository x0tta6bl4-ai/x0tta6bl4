# x0tMQ Demo for Geoscan

## What is this?

**x0tMQ** (x0tta6bl4 MAVLink Quantum) — open post-quantum extension to MAVLink v2 protocol.

It adds:
- **ML-KEM-1024** (FIPS 203) — quantum-resistant session key exchange
- **ML-DSA-87** (FIPS 204) — quantum-resistant command signing
- **x0CHUNK** — fragment PQ signatures through existing MAVLink repeaters

## Quick start

```bash
# On any Linux machine with Python 3.10+
cd /path/to/x0tta6bl4

# Run the attack demonstration
python3 demo/geoscan/attack_demos.py

# Run the full protocol demo
python3 examples/x0tmq_demo.py
```

## What you'll see

### Attack Demonstrations (`attack_demos.py`)

1. **Relay-striping attack** — Repeater strips signature → DETECTED
2. **Command hijacking** — Attacker reuses signature → REJECTED
3. **HNDL attack** — Harvest now, decrypt later → PREVENTED
4. **Performance benchmark** — Key operations timing

### Full Protocol Demo (`x0tmq_demo.py`)

1. Key generation (ML-KEM-1024 + ML-DSA-87)
2. Session establishment via x0CHUNK fragmentation
3. SESSION_ACK mutual authentication
4. Command signing and verification
5. Telemetry HMAC authentication

## Requirements

- Python 3.10+
- No external dependencies (pure Python PQC implementation)

## Technical details

| Component | Size | Status |
|-----------|------|--------|
| ML-KEM-1024 ciphertext | 1568 bytes | FIPS 203 |
| ML-DSA-87 signature | 4627 bytes | FIPS 204 |
| x0CHUNK fragment | 255 bytes | Standard MAVLink v2 frame |
| HMAC-SHA3-256 tag | 32 bytes | 1.1 μs on ARM64 |

## Integration with Geoscan

x0tMQ can be integrated into:
- Flight controllers (MAVLink v2 stack)
- Ground control stations (QGroundControl, Mission Planner)
- Custom telemetry links

The protocol is **backward-compatible** — x0CHUNK frames look like standard MAVLink telemetry to existing repeaters.

## Documentation

- **Specification**: `docs/rfc/draft-x0tmq-mavlink-pqc.md` (IETF Internet-Draft)
- **Source code**: `src/security/x0tmq/` (591 LOC)
- **Tests**: `tests/unit/security/test_x0tmq.py` (18/18 passing)

## Contact

- GitHub: github.com/x0tta6bl4-ai/x0tta6bl4
- Email: x0tta6bl4.ai@gmail.com
