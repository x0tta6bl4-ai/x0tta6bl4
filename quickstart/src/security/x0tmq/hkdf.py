"""HKDF-SHA3-256 key derivation as specified in the x0tMQ draft (§7).

Implements RFC 5869 using SHA3-256 as the underlying hash.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac_module


def _hmac_sha3_256(key: bytes, data: bytes) -> bytes:
    """Keyed-hash using SHA3-256."""
    return _hmac_module.new(key, data, hashlib.sha3_256).digest()


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """HKDF-Extract using SHA3-256."""
    return _hmac_sha3_256(salt, ikm)


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand using SHA3-256."""
    output = b""
    block = b""
    counter = 1
    while len(output) < length:
        block = _hmac_sha3_256(prk, block + info + bytes([counter]))
        output += block
        counter += 1
    return output[:length]


def derive_x0tmq_keys(
    pqc_shared_secret: bytes,
    *,
    client_nonce: bytes,
    server_nonce: bytes,
    transcript_hash: bytes,
    client_identity_hash: bytes,
    server_identity_hash: bytes,
    salt: bytes | None = None,
) -> dict[str, bytes]:
    """Derive the five x0tMQ session keys from the ML-KEM shared secret.

    Returns dict with keys:
        session_key (K_main) — primary session key
        cmd_key (K_cmd)      — ML-DSA sub-key
        auth_key (K_auth)    — HMAC-SHA3-256 telemetry key
        enc_key (K_enc)      — reserved for future encryption
        session_id            — 64-bit session identifier
    """
    if salt is None:
        salt = hashlib.sha3_256(
            b"x0tmq-v1-hkdf-salt"
            + client_nonce
            + server_nonce
            + transcript_hash
        ).digest()

    ikm = b"".join([
        pqc_shared_secret,
        client_identity_hash,
        server_identity_hash,
    ])
    prk = _hkdf_extract(salt, ikm)

    keys = {}
    keys["session_key"] = _hkdf_expand(prk, b"x0tmq-v1-session-key", 32)
    keys["cmd_key"] = _hkdf_expand(prk, b"x0tmq-v1-cmd-key", 32)
    keys["auth_key"] = _hkdf_expand(prk, b"x0tmq-v1-auth-key", 32)
    keys["enc_key"] = _hkdf_expand(prk, b"x0tmq-v1-enc-key", 32)
    sid = _hkdf_expand(prk, b"x0tmq-v1-session-id", 8)
    keys["session_id"] = int.from_bytes(sid, "big")
    return keys
