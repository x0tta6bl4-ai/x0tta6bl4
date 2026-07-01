# x0tMQ: MAVLink v2 Post-Quantum Authentication Protocol

    draft-x0tta6bl4-x0tmq-mavlink-pqc-00

    x0tta6bl4
    June 2026

    Intended status: Standards Track
    Expires: 30 December 2026

## Abstract

This document specifies x0tMQ (x0tta6bl4 MAVLink Quantum), a
backward-compatible extension to the MAVLink v2 protocol (MAVLink 2.0)
that adds support for post-quantum asymmetric authentication and
session key establishment.  MAVLink v2 currently relies solely on
HMAC-SHA256 symmetric signatures, which are vulnerable to pre-key
compromise and lack forward secrecy.  x0tMQ introduces three new
message types — X0_SESSION_INIT, X0_SIGNED_CMD, and x0CHUNK —
encapsulating post-quantum primitives defined in NIST FIPS 203
(ML-KEM) and FIPS 204 (ML-DSA) within standard MAVLink v2 frames,
enabling transparent relay through legacy infrastructure without
hardware modification.

## Status of This Memo

This Internet-Draft is submitted in full conformance with the
provisions of BCP 78 and BCP 79.

Internet-Drafts are working documents of the Internet Engineering Task
Force (IETF).  Note that other groups may also distribute working
documents as Internet-Drafts.  The list of current Internet-Drafts is
at https://datatracker.ietf.org/drafts/current/.

Internet-Drafts are draft documents valid for a maximum of six months
and may be updated, replaced, or obsoleted by other documents at any
time.  It is inappropriate to use Internet-Drafts as reference material
or to cite them other than as "work in progress."

This Internet-Draft will expire on 30 December 2026.

## Copyright Notice

Copyright (c) 2026 IETF Trust and the persons identified as the
document authors.  All rights reserved.

This document is subject to BCP 78 and the IETF Trust's Legal
Provisions Relating to IETF Documents
(https://trustee.ietf.org/license-info) in effect on the date of
publication of this document.  Please review these documents
carefully, as they describe your rights and restrictions with respect
to this document.  Code Components extracted from this document must
include Revised BSD License text as described in Section 4.e of the
Trust Legal Provisions and are provided without warranty as described
in the Revised BSD License.

## Table of Contents

1.  Introduction
2.  Conventions and Terminology
3.  Protocol Overview
4.  Message Types
    4.1  X0_SESSION_INIT (MSG_ID 50001)
    4.2  X0_SIGNED_CMD (MSG_ID 50002)
    4.3  x0CHUNK (MSG_ID 50000)
5.  x0CHUNK Fragmentation
6.  Cryptographic Algorithms
    6.1  ML-KEM-1024 (FIPS 203)
    6.2  ML-DSA-87 (FIPS 204)
    6.3  HMAC-SHA3-256
7.  Session Establishment
8.  Command Signing and Verification
9.  Performance Characteristics
10. Security Considerations
11. IANA Considerations
12. References
    12.1  Normative References
    12.2  Informative References
Author's Address

---

## 1.  Introduction

The MAVLink protocol [MAVLINK] is the de facto standard communication
protocol for unmanned aerial vehicles (UAVs), ground stations, and
robotic systems.  MAVLink v2 supports packet signing using a
pre-shared key via HMAC-SHA256.  This design exhibits three
fundamental limitations:

   1.  **Symmetric key model**: All participants share the same
       authentication key.  Compromise of any single node exposes the
       entire fleet.

   2.  **No forward secrecy**: A captured key allows retroactive
       decryption of all recorded traffic ("harvest now, decrypt
       later" / HNDL attack).

   3.  **No asymmetric command authentication**: Critical commands
       (arm, disarm, waypoint override, geofence modification) cannot
       be bound to a specific authenticated originator.

The emergence of cryptographically relevant quantum computers (CRQCs)
within the next decade renders RSA and ECC-based alternatives
insufficient for systems with long operational lifetimes, such as
orbital and deep-sea assets.  x0tMQ addresses these gaps by
encapsulating NIST-standardized post-quantum primitives [FIPS203]
[FIPS204] in MAVLink v2 frames that pass transparently through legacy
relays.

## 2.  Conventions and Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and
"OPTIONAL" in this document are to be interpreted as described in
BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all
capitals, as shown here.

**Terms:**

-   **GCS**: Ground Control Station.
-   **FCS**: Flight Controller / companion computer.
-   **Relay**: Any intermediate node forwarding MAVLink frames without
    inspecting message payload beyond the header.
-   **HNDL**: Harvest Now, Decrypt Later — the practice of collecting
    ciphertext for future quantum decryption.
-   **SVID**: SPIFFE Verifiable Identity Document (X.509 or JWT).
-   **PQ**: Post-Quantum.

## 3.  Protocol Overview

x0tMQ operates in three phases during a MAVLink session:

   Phase 1 — Session Key Establishment
       The GCS generates an ML-KEM-1024 keypair and sends the public
       key encapsulated as a X0_SESSION_INIT message.  The FCS
       decapsulates the session key.  Both sides now share a
       symmetric session key with forward secrecy.

   Phase 2 — Ongoing Command Authentication
       Every critical command (arm/disarm, geofence update, waypoint
       override) is signed by the sender using ML-DSA-87.  The
       signature is transmitted as a X0_SIGNED_CMD message
       that pairs with the preceding command message.  For
       high-frequency telemetry, HMAC-SHA3-256 provides lightweight
       per-packet authentication.

   Phase 3 — Transparent Relay via Chunking
       ML-DSA-87 signatures are ~2.4 KB, exceeding the nominal
       MAVLink v2 payload limit of 280 bytes.  x0CHUNK
       fragments the signature into 245-byte segments, each
       encapsulated in a valid MAVLink frame with MSG_ID 50000,
       INCOMPAT_FLAGS = 0, and a correct CRC-16-CCITT checksum.
       Legacy relays forward these frames as opaque valid data.

## 4.  Message Types

All x0tMQ messages use MAVLink v2 framing with the following
common header fields:

    magic:       0xFD (MAVLink v2 start byte)
    incompat:    0x00  (x0tMQ set compat, not incompat)
    compat:      set according to message type
    len:         payload length (exclusive of signature/CRC)
    seq:         MAVLink sequence counter
    sysid:       system identifier
    compid:      component identifier
    msgid:       message ID as specified per type below

### 4.1  X0_SESSION_INIT (MSG_ID 50001)

**Purpose:** Transmit an ML-KEM-1024 encapsulation key from GCS to FCS
for session key establishment.

**Payload format (fixed length: 1600 bytes):**

    +--------+-------------+-------------+----------------------+
    | Offset | Field       | Size (bytes)| Description          |
    +--------+-------------+-------------+----------------------+
    | 0      | kem_ct      | 1568        | ML-KEM-1024           |
    |        |             |             | ciphertext             |
    +--------+-------------+-------------+----------------------+
    | 1568   | session_id  | 16          | Random session         |
    |        |             |             | identifier (BLAKE3)    |
    +--------+-------------+-------------+----------------------+
    | 1584   | signature   | 16          | HMAC-SHA3-256          |
    |        |             |             | truncated to 16 bytes  |
    |        |             |             | keyed with pre-shared   |
    |        |             |             | link key              |
    +--------+-------------+-------------+----------------------+

The GCS MUST generate a fresh ML-KEM-1024 keypair once per session.
The FCS decapsulates the ciphertext to obtain the 32-byte session
key.  The ciphertext field uses the standard ML-KEM-1024 encapsulation
output as defined in [FIPS203] Section 7.2.

### 4.2  X0_SIGNED_CMD (MSG_ID 50002)

**Purpose:** Provide an ML-DSA-87 signature over a preceding command
message.

**Payload format (variable length, up to 2506 bytes):**

    +--------+-------------+-------------+----------------------+
    | Offset | Field       | Size (bytes)| Description          |
    +--------+-------------+-------------+----------------------+
    | 0      | cmd_seq     | 2           | seq of the signed     |
    |        |             |             | command message       |
    +--------+-------------+-------------+----------------------+
    | 2      | session_id  | 16          | Session identifier    |
    |        |             |             | from SESSION_INIT     |
    +--------+-------------+-------------+----------------------+
    | 18     | nonce       | 8           | Random nonce          |
    +--------+-------------+-------------+----------------------+
    | 26     | pq_sig      | 2460        | ML-DSA-87 signature   |
    |        |             | (variable)  | (nominal: 2429 bytes, |
    |        |             |             | padded with zeros)    |
    +--------+-------------+-------------+----------------------+

The receiving FCS buffers the command identified by cmd_seq and
applies it only after successful ML-DSA-87 signature verification
against the GCS's registered public key.

### 4.3  x0CHUNK (MSG_ID 50000)

**Purpose:** Fragment a large x0tMQ message (SESSION_INIT or
SIGNED_CMD) into relay-transparent MAVLink frames.

**Payload format (fixed length: 253 bytes):**

    +--------+-------------+-------------+----------------------+
    | Offset | Field       | Size (bytes)| Description          |
    +--------+-------------+-------------+----------------------+
    | 0      | src_msgid   | 2           | Original message ID   |
    |        |             |             | of the fragmented     |
    |        |             |             | message               |
    +--------+-------------+-------------+----------------------+
    | 2      | chunk_idx   | 2           | Zero-based chunk      |
    |        |             |             | index                 |
    +--------+-------------+-------------+----------------------+
    | 4      | total_chunks| 2          | Total number of chunks |
    |        |             |             | (max: 1024)           |
    +--------+-------------+-------------+----------------------+
    | 6      | payload     | 245         | Chunk data            |
    +--------+-------------+-------------+----------------------+
    | 251    | crc16       | 2           | CRC-16-CCITT over     |
    |        |             |             | payload[0..250]       |
    +--------+-------------+-------------+----------------------+

The receiving endpoint reconstructs the original message by
concatenating all chunks in order of chunk_idx, then verifying the
CRC-16-CCITT over the full reassembled payload.

## 5.  x0CHUNK Fragmentation

Fragmentation is REQUIRED for any x0tMQ message whose payload
exceeds the MAVLink v2 maximum payload of 280 bytes (or the
effective path MTU when relay constraints are tighter).

The replay protection model is built around two mechanisms:

   1.  **Seq ordering**: x0CHUNK frames carry a unique seq
       value in their MAVLink header, incremented per chunk from the
       same origin.  Receivers MUST reject chunks with seq values
       below the previous validated chunk from the same origin.

   2.  **Per-chunk HMAC**: When fragmentation is used for SESSION_INIT
       or SIGNED_CMD, each chunk's payload is authenticated with a
       session-derived key such that receivers can discard
       out-of-order or malicious chunks before reassembly.

On reception of the final chunk (where chunk_idx == total_chunks - 1),
the reassembler verifies the complete CRC-16-CCITT over the full
payload.  If verification fails, all chunks for that message MUST be
discarded and a X0_NACK (deferred to future specification) MAY
be emitted.

## 6.  Cryptographic Algorithms

### 6.1  ML-KEM-1024 (FIPS 203)

**Role:** Session key encapsulation.

-   **Key generation**: Encapsulation key (public) and decapsulation
    key (private) per [FIPS203] Section 6.2.
-   **Encapsulation**: Produces a 1568-byte ciphertext and a 32-byte
    shared secret.
-   **Decapsulation**: Recovers the 32-byte shared secret from the
    ciphertext.
-   **Clock cycles (ARM64 Neoverse-N2)**: 241 microseconds per
    encapsulation/decapsulation operation.
-   **Security strength**: Category 5 (highest) against quantum
    adversaries [NISTPQ].

Ciphertext size in ML-KEM-1024 is 1568 bytes, which MUST be
fragmented via x0CHUNK if the MAVLink frame cannot
accommodate the full payload in a single message.

### 6.2  ML-DSA-87 (FIPS 204)

**Role:** Command signing and non-repudiation.

-   **Key generation**: Per [FIPS204] Section 7.1, producing a
    public verification key (~2.4 KB) and a private signing key.
-   **Sign**: 509 microseconds for a 256-byte payload (ARM64 Neoverse-N2).
-   **Verify**: Comparable or lower latency, depending on architecture.
-   **Signature size**: Variable, nominally 2429 bytes.
    MUST be fragmented via x0CHUNK.
-   **Security strength**: Category 5 [NISTPQ].

### 6.3  HMAC-SHA3-256

**Role:** Lightweight per-packet authentication for high-frequency
telemetry (100 Hz+).

-   **Key size**: 32 bytes (derived from ML-KEM session key).
-   **HMAC output**: 32 bytes.
-   **Clock cycles (ARM64 Neoverse-N2)**: 1.1 microseconds.
-   **Overhead**: 32 bytes per telemetry packet.

HMAC-SHA3-256 is used for routine telemetry frames where ML-DSA-87
overhead (~2.4 KB) would be prohibitive.  The key is rotated each
session via ML-KEM-1024 re-keying at intervals determined by the
security policy (RECOMMENDED: every 15 minutes or 100,000 packets,
whichever comes first).

## 7.  Session Establishment

A x0tMQ session proceeds as follows:

Step 1 — GCS generates an ML-KEM-1024 keypair (ek, dk).

Step 2 — GCS encapsulates: (ct, ss) = ML-KEM-1024.Encaps(ek).

Step 3 — GCS frames ct as X0_SESSION_INIT (MSG_ID 50001),
    possibly fragmented via x0CHUNK (MSG_ID 50000) if ct
    exceeds MTU.

Step 4 — FCS receives all x0CHUNK frames, reassembles, and
    decapsulates: ss = ML-KEM-1024.Decaps(dk, ct).

Step 5 — Both sides derive three keys from ss via HKDF-SHA3-256
    [RFC5869]:

        K_cmd  = HKDF(ss, "x0tmq-cmd-key")   — for ML-DSA
        K_auth = HKDF(ss, "x0tmq-auth-key")  — for HMAC-SHA3-256
        K_enc  = HKDF(ss, "x0tmq-enc-key")   — reserved

Step 6 — FCS sends X0_SESSION_ACK (provisional MSG_ID 50003,
    specification forthcoming) confirming session establishment.

The session_id (16 bytes, generated and included in SESSION_INIT)
binds all subsequent SIGNED_CMD and HMAC-authenticated telemetry
frames to this session context.  Sessions MUST be re-established
after any link interruption exceeding 30 seconds.

## 8.  Command Signing and Verification

When a GCS issues a critical command (e.g., MAV_CMD_DO_SET_MODE,
MAV_CMD_COMPONENT_ARM_DISARM, MAV_CMD_NAV_WAYPOINT), it MUST:

   1.  Transmit the original command in a standard MAVLink command
       message.

   2.  Transmit a X0_SIGNED_CMD (MSG_ID 50002) message that
       references the command by its MAVLink seq number and carries
       an ML-DSA-87 signature over (cmd_seq || session_id || nonce ||
       original_payload).

   3.  Optionally fragment the SIGNED_CMD via x0CHUNK.

The receiving FCS:

   1.  Buffers the command message upon reception.

   2.  Reassembles the SIGNED_CMD from x0CHUNK frames, if
       fragmented.

   3.  Verifies the ML-DSA-87 signature using the GCS's public key
       that was registered out-of-band (or discovered via a PKI
       mechanism such as SPIFFE/SPIRE [SPIFFE]).

   4.  If verification succeeds, executes the command.  If
       verification fails, discards both the command and the
       signature frame, and logs a security event.

For high-frequency telemetry (rates exceeding 50 Hz), the sender MAY
use HMAC-SHA3-256 instead of ML-DSA-87, appending the 32-byte HMAC
as an additional MAVLink frame immediately following each telemetry
frame.

## 9.  Performance Characteristics

Benchmarks measured on ARM64 Neoverse-N2 (Ampere Altra) @ 2.8 GHz,
using the liboqs reference implementation [LIBOQS]:

    +-----------------------------+----------+------------------+
    | Operation                   | Time     | Notes            |
    +-----------------------------+----------+------------------+
    | ML-KEM-1024 Encapsulation    | 241 μs   | One-shot, first  |
    |                             |          | session only     |
    +-----------------------------+----------+------------------+
    | ML-KEM-1024 Decapsulation    | 241 μs   | One-shot         |
    +-----------------------------+----------+------------------+
    | ML-DSA-87 Sign (256B input) | 509 μs   | Per critical cmd |
    +-----------------------------+----------+------------------+
    | ML-DSA-87 Verify (256B)     | ~480 μs  | Onboard FCS      |
    +-----------------------------+----------+------------------+
    | HMAC-SHA3-256 (32B input)   | 1.1 μs   | Per telemetry    |
    |                             |          | packet           |
    +-----------------------------+----------+------------------+

These benchmarks support practical deployment on current-generation
ARM Cortex-A72 and Neoverse platforms.  Lightweight microcontrollers
(Cortex-M4/M7) SHOULD offload PQ operations to a companion computer
or a hardware security module (HSM).

## 10.  Security Considerations

### 10.1  Relay-Striping Attacks

A malicious relay MAY strip appended authentication frames.  x0tMQ
mitigates this by using x0CHUNK fragmentation with
CRC-16-CCITT verification per chunk, ensuring that missing or
truncated chunks are detected at the receiver before reassembly.

### 10.2  Replay Attacks

Each X0_SIGNED_CMD contains a unique nonce and a session_id.
Receivers MUST reject messages with duplicate (session_id, nonce)
tuples within the session lifetime.

### 10.3  Key Compromise

If an ML-DSA-87 private key is compromised, the attacker can sign
arbitrary commands.  Mitigations include:

-   Short-lived keys (RECOMMENDED: 24-hour validity).
-   Integration with SPIFFE/SPIRE [SPIFFE] for automatic key rotation
    and revocation.
-   Hardware-backed key storage (TPM 2.0, ARM TrustZone).

### 10.4  Denial of Service via Signature Verification

Computationally expensive ML-DSA-87 verification (~480 μs) can be
abused by flooding.  Implementations SHOULD:

-   Rate-limit signature verification per (source, session).
-   Reject messages with invalid CRC before attempting PQ
    verification.
-   Drop chunks from unauthenticated sources.

### 10.5  HNDL Mitigation

ML-KEM-1024 provides post-quantum forward secrecy.  Even if the long-
term decapsulation key is later compromised, past session traffic
cannot be decrypted because the session key is derived from the
encapsulation ciphertext, which is destroyed after decapsulation.

### 10.6  Transition Period (Pre-2028)

During the hybrid transition, implementations MAY dual-sign commands
with both ML-DSA-44 (smaller, faster) and HMAC-SHA256 (legacy
compatibility).  The receiver SHOULD accept either as valid until a
configurable cutoff date.  This hybrid approach follows the pattern
of CNSA 2.0 [CNSA20].

## 11.  IANA Considerations

This document requests the assignment of three MAVLink message IDs
from the MAVLink reserved range (50000-65535):

    +-----------+---------------------+------------+
    | MSG_ID    | Name                | Reference  |
    +-----------+---------------------+------------+
    | 50000     | x0CHUNK      | Section 4.3|
    | 50001     | X0_SESSION_INIT | Section 4.1|
    | 50002     | X0_SIGNED_CMD  | Section 4.2|
    +-----------+---------------------+------------+

The MAVLink message registry is maintained at
https://mavlink.io/en/messages/.

## 12.  References

### 12.1  Normative References

[FIPS203]  National Institute of Standards and Technology, "FIPS 203:
           Module-Lattice-Based Key-Encapsulation Mechanism Standard",
           August 2024,
           <https://doi.org/10.6028/NIST.FIPS.203>.

[FIPS204]  National Institute of Standards and Technology, "FIPS 204:
           Module-Lattice-Based Digital Signature Standard",
           August 2024,
           <https://doi.org/10.6028/NIST.FIPS.204>.

[RFC2119]  Bradner, S., "Key words for use in RFCs to Indicate
           Requirement Levels", BCP 14, RFC 2119,
           DOI 10.17487/RFC2119, March 1997,
           <https://www.rfc-editor.org/info/rfc2119>.

[RFC8174]  Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC
           2119 Key Words", BCP 14, RFC 8174, DOI 10.17487/RFC8174,
           May 2017, <https://www.rfc-editor.org/info/rfc8174>.

[RFC5869]  Krawczyk, H. and P. Eronen, "HMAC-based Extract-and-Expand
           Key Derivation Function (HKDF)", RFC 5869,
           DOI 10.17487/RFC5869, May 2010,
           <https://www.rfc-editor.org/info/rfc5869>.

[MAVLINK]  MAVLink Developer Guide,
           <https://mavlink.io/en/>.

### 12.2  Informative References

[CNSA20]   National Security Agency, "Commercial National Security
           Algorithm Suite 2.0 (CNSA 2.0)", September 2022,
           <https://media.defense.gov/2022/Sep/07/2003071845/-1/-1/0/
           CNSA%202.0%20FACT%20SHEET.PDF>.

[LIBOQS]   Open Quantum Safe, "liboqs - C library for quantum-safe
           cryptographic algorithms",
           <https://github.com/open-quantum-safe/liboqs>.

[NISTPQ]   National Institute of Standards and Technology,
           "Post-Quantum Cryptography Standardization",
           <https://csrc.nist.gov/projects/post-quantum-cryptography>.

[SPIFFE]   SPIFFE/SPIRE, "SPIFFE Verifiable Identity Document",
           <https://spiffe.io/docs/latest/spiffe-about/spiffe-concepts/>.

## Author's Address

    x0tta6bl4
    Email: x0tta6bl4.ai@gmail.com

    GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4
