"""First-party frame crypto and PQC-bound key schedule.

The production key agreement input is an ML-KEM shared secret produced by the
PQC layer. This module does not claim to implement ML-KEM itself; it binds that
secret to our wire protocol, identities, nonces, and transcript.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import secrets


MIN_SECRET_BYTES = 32
KEY_BYTES = 32
NONCE_BYTES = 32
TAG_BYTES = 32
SUPPORTED_KEM_ALGORITHMS = {"ML-KEM-768", "ML-KEM-1024"}
SUPPORTED_SIGNATURE_ALGORITHMS = {"ML-DSA-65", "ML-DSA-87"}


class FrameCryptoError(ValueError):
    """Raised when frame crypto verification or setup fails."""


@dataclass(frozen=True)
class PqcSessionMaterial:
    """Inputs that bind a session key to PQC and zero-trust identity."""

    kem_algorithm: str
    signature_algorithm: str
    pqc_shared_secret: bytes
    client_nonce: bytes
    server_nonce: bytes
    transcript_hash: bytes
    client_identity_hash: bytes
    server_identity_hash: bytes
    deployment_epoch: str = "local-dev"

    @classmethod
    def create(
        cls,
        *,
        kem_algorithm: str,
        signature_algorithm: str,
        pqc_shared_secret: bytes,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
        client_nonce: bytes | None = None,
        server_nonce: bytes | None = None,
        deployment_epoch: str = "local-dev",
    ) -> "PqcSessionMaterial":
        return cls(
            kem_algorithm=kem_algorithm,
            signature_algorithm=signature_algorithm,
            pqc_shared_secret=pqc_shared_secret,
            client_nonce=client_nonce or secrets.token_bytes(NONCE_BYTES),
            server_nonce=server_nonce or secrets.token_bytes(NONCE_BYTES),
            transcript_hash=hashlib.sha256(transcript).digest(),
            client_identity_hash=client_identity_hash,
            server_identity_hash=server_identity_hash,
            deployment_epoch=deployment_epoch,
        )

    def validate(self) -> None:
        if self.kem_algorithm not in SUPPORTED_KEM_ALGORITHMS:
            raise FrameCryptoError(f"unsupported KEM algorithm: {self.kem_algorithm}")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise FrameCryptoError(
                f"unsupported signature algorithm: {self.signature_algorithm}"
            )
        if len(self.pqc_shared_secret) < MIN_SECRET_BYTES:
            raise FrameCryptoError("PQC shared secret is too short")
        for name, value in (
            ("client_nonce", self.client_nonce),
            ("server_nonce", self.server_nonce),
            ("transcript_hash", self.transcript_hash),
            ("client_identity_hash", self.client_identity_hash),
            ("server_identity_hash", self.server_identity_hash),
        ):
            if len(value) < MIN_SECRET_BYTES:
                raise FrameCryptoError(f"{name} is too short")


@dataclass(frozen=True)
class SessionKeys:
    """Directional session keys."""

    client_tx: bytes
    client_rx: bytes
    server_tx: bytes
    server_rx: bytes
    control: bytes
    session_id: int


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    output = b""
    block = b""
    counter = 1
    while len(output) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        output += block
        counter += 1
    return output[:length]


def derive_session_keys(material: PqcSessionMaterial) -> SessionKeys:
    """Derive directional keys from PQC and identity-bound session material."""
    material.validate()
    salt = hashlib.sha256(
        b"x0tta6bl4-firstparty-vpn-salt-v1"
        + material.client_nonce
        + material.server_nonce
        + material.transcript_hash
    ).digest()
    ikm = b"".join(
        [
            material.pqc_shared_secret,
            material.client_identity_hash,
            material.server_identity_hash,
            material.deployment_epoch.encode("utf-8"),
        ]
    )
    prk = _hkdf_extract(salt, ikm)
    client_to_server = _hkdf_expand(prk, b"x0vpn-v1 client-to-server", KEY_BYTES)
    server_to_client = _hkdf_expand(prk, b"x0vpn-v1 server-to-client", KEY_BYTES)
    control = _hkdf_expand(prk, b"x0vpn-v1 control", KEY_BYTES)
    session_id_bytes = _hkdf_expand(prk, b"x0vpn-v1 session-id", 8)
    session_id = int.from_bytes(session_id_bytes, "big")
    return SessionKeys(
        client_tx=client_to_server,
        client_rx=server_to_client,
        server_tx=server_to_client,
        server_rx=client_to_server,
        control=control,
        session_id=session_id,
    )


class FrameCrypto:
    """Authenticated stream wrapper for protocol frames.

    This is a first-party construction using HMAC-SHA256 as a PRF and MAC. It
    gives us deterministic tests and a dependency-free internal protocol core.
    Production rollout must keep the PQC key exchange and should be reviewed
    before claiming standardized AEAD equivalence.
    """

    def __init__(self, *, encrypt_key: bytes, decrypt_key: bytes) -> None:
        if len(encrypt_key) != KEY_BYTES or len(decrypt_key) != KEY_BYTES:
            raise FrameCryptoError("frame keys must be 32 bytes")
        self.encrypt_key = encrypt_key
        self.decrypt_key = decrypt_key

    def protect(self, *, sequence: int, plaintext: bytes, aad: bytes) -> bytes:
        ciphertext = _xor_with_prf(self.encrypt_key, sequence, plaintext, aad)
        tag = _tag(self.encrypt_key, sequence, aad, ciphertext)
        return ciphertext + tag

    def open(self, *, sequence: int, protected_payload: bytes, aad: bytes) -> bytes:
        if len(protected_payload) < TAG_BYTES:
            raise FrameCryptoError("protected payload is too short")
        ciphertext = protected_payload[:-TAG_BYTES]
        received = protected_payload[-TAG_BYTES:]
        expected = _tag(self.decrypt_key, sequence, aad, ciphertext)
        if not hmac.compare_digest(received, expected):
            raise FrameCryptoError("frame authentication failed")
        return _xor_with_prf(self.decrypt_key, sequence, ciphertext, aad)


def _tag(key: bytes, sequence: int, aad: bytes, ciphertext: bytes) -> bytes:
    return hmac.new(
        key,
        b"x0vpn-v1 tag"
        + sequence.to_bytes(8, "big")
        + len(aad).to_bytes(4, "big")
        + aad
        + ciphertext,
        hashlib.sha256,
    ).digest()


def _xor_with_prf(key: bytes, sequence: int, payload: bytes, aad: bytes) -> bytes:
    stream = bytearray()
    counter = 0
    aad_hash = hashlib.sha256(aad).digest()
    while len(stream) < len(payload):
        stream.extend(
            hmac.new(
                key,
                b"x0vpn-v1 stream"
                + sequence.to_bytes(8, "big")
                + counter.to_bytes(4, "big")
                + aad_hash,
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    return bytes(left ^ right for left, right in zip(payload, stream))
