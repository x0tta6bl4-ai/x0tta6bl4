"""x0tMQ session manager — PQC-authenticated MAVLink v2 session.

x0tMQ — x0tta6bl4 MAVLink Quantum.

Phases
------
1. X0_SESSION_INIT (MSG_ID 50001)
   GCS encapsulates an ML-KEM-1024 key and sends the ciphertext (fragmented
   via x0CHUNK).  The UAV decapsulates and derives session keys.

2. X0_SESSION_ACK (MSG_ID 50003)
   UAV confirms session establishment, binding the session key.

3. X0_SIGNED_CMD (MSG_ID 50002)
   Critical commands carry an ML-DSA-87 signature (fragmented).  The
   receiver reassembles and verifies before applying the command.

4. Telemetry HMAC
   High-frequency telemetry is authenticated with HMAC-SHA3-256 keyed
   from the ML-KEM shared secret via HKDF-SHA3-256 (draft §7).

All heavy PQC operations delegate to the first-party implementations
in src.network.firstparty_vpn.{mlkem, mldsa, crypto}.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import List, Optional, Tuple

from src.network.firstparty_vpn.mlkem import (
    MlKemEncapsulation,
    MlKemKeyPair,
    mlkem_decapsulate,
    mlkem_encapsulate,
    mlkem_keygen,
)
from src.network.firstparty_vpn.mldsa import (
    mldsa_reference_sign,
    mldsa_reference_verify,
    mldsa_derive_reference_keypair,
)

from .chunk import X0Chunker, X0_CHUNK_MSG_ID, X0_SESSION_INIT_ID, X0_SIGNED_CMD_ID, X0_SESSION_ACK_ID
from .frame import MavlinkV2Frame
from .hkdf import derive_x0tmq_keys


_KEM_ALGORITHM = "ML-KEM-1024"
_SIG_ALGORITHM = "ML-DSA-87"


class X0SessionManager:
    """PQC-authenticated session between a GCS and a UAV.

    Thread-safety: not guarded.  Use one instance per direction.

    Example (GCS side):
        mgr = X0SessionManager(sys_id=1, comp_id=1)
        uav_ek = b"..."  # obtained out-of-band
        frames = mgr.initiate_session(42, uav_ek)
        for f in frames:
            radio.send(f.serialize())
    """

    def __init__(self, sys_id: int, comp_id: int) -> None:
        self._sys_id = sys_id
        self._comp_id = comp_id
        self._chunker = X0Chunker(sys_id, comp_id)

        # Session state — populated after SESSION_INIT + ACK.
        self.session_id: Optional[int] = None
        self.session_key: Optional[bytes] = None
        self.cmd_key: Optional[bytes] = None
        self.auth_key: Optional[bytes] = None
        self.enc_key: Optional[bytes] = None

    # ------------------------------------------------------------------
    # Phase 1 — Session establishment (GCS → UAV)
    # ------------------------------------------------------------------

    def initiate_session(
        self, session_id: int, uav_encapsulation_key: bytes,
    ) -> Tuple[List[MavlinkV2Frame], bytes]:
        """GCS: generate ML-KEM-1024 keys and encapsulate.

        Returns (chunked_frames, shared_secret_bytes).
        The caller should send the frames and retain *shared_secret*
        for key derivation.
        """
        result: MlKemEncapsulation = mlkem_encapsulate(_KEM_ALGORITHM, uav_encapsulation_key)
        self._derive_keys(session_id, result.shared_secret)
        frames = self._chunker.fragment(session_id, result.ciphertext)
        return frames, result.shared_secret

    def accept_session(
        self,
        uav_mlkem_keypair: MlKemKeyPair,
        reassembled_ciphertext: bytes,
    ) -> bytes:
        """UAV: decapsulate the ML-KEM-1024 ciphertext from the GCS.

        Returns the shared secret.  Call *handle_session_ack()* on the
        GCS after it receives the ACK from UAV.
        """
        ss = mlkem_decapsulate(
            _KEM_ALGORITHM,
            uav_mlkem_keypair.decapsulation_key,
            reassembled_ciphertext,
        )
        return ss

    def build_session_ack(self) -> MavlinkV2Frame:
        """UAV → GCS: confirm session with HMAC-SHA3-256 of session_id."""
        if self.session_id is None or self.auth_key is None:
            raise ValueError("session not established")
        proof = hmac.new(
            self.auth_key,
            self.session_id.to_bytes(8, "big"),
            hashlib.sha3_256,
        ).digest()
        return MavlinkV2Frame(
            sys_id=self._sys_id,
            comp_id=self._comp_id,
            msg_id=X0_SESSION_ACK_ID,
            payload=proof,
        )

    def verify_session_ack(self, ack_frame: MavlinkV2Frame) -> bool:
        """GCS: verify the X0_SESSION_ACK from the UAV."""
        if self.session_id is None or self.auth_key is None:
            return False
        if ack_frame.msg_id != X0_SESSION_ACK_ID:
            return False
        expected = hmac.new(
            self.auth_key,
            self.session_id.to_bytes(8, "big"),
            hashlib.sha3_256,
        ).digest()
        return hmac.compare_digest(ack_frame.payload, expected)

    # ------------------------------------------------------------------
    # Phase 2 — Command signing (GCS) & verification (UAV)
    # ------------------------------------------------------------------

    def sign_command(
        self,
        cmd_payload: bytes,
        gcs_signing_key: bytes,
    ) -> List[MavlinkV2Frame]:
        """GCS: ML-DSA-87 sign a command, return chunked X0_SIGNED_CMD frames."""
        sig = mldsa_reference_sign(_SIG_ALGORITHM, gcs_signing_key, cmd_payload)
        return self._chunker.fragment(self.session_id or 0, sig)

    def verify_command(
        self,
        cmd_payload: bytes,
        reassembled_signature: bytes,
        gcs_verification_key: bytes,
    ) -> bool:
        """UAV: ML-DSA-87 verify a signed command."""
        return mldsa_reference_verify(
            _SIG_ALGORITHM,
            gcs_verification_key,
            cmd_payload,
            reassembled_signature,
        )

    # ------------------------------------------------------------------
    # Phase 3 — Telemetry HMAC
    # ------------------------------------------------------------------

    def authenticate_telemetry(self, data: bytes) -> bytes:
        """32-byte HMAC-SHA3-256 tag over *data*.

        Raises ValueError if session not established.
        """
        if self.auth_key is None:
            raise ValueError("x0tMQ session not established")
        return hmac.new(self.auth_key, data, hashlib.sha3_256).digest()

    def verify_telemetry(self, data: bytes, tag: bytes) -> bool:
        expected = self.authenticate_telemetry(data)
        return hmac.compare_digest(expected, tag)

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def set_session_from_secret(self, session_id: int, shared_secret: bytes) -> None:
        """UAV: populate session state from raw ML-KEM shared secret."""
        self._derive_keys(session_id, shared_secret)

    def _derive_keys(self, session_id: int, pqc_shared_secret: bytes) -> None:
        """HKDF-SHA3-256 derivation per draft §7."""
        client_id = hashlib.sha256(b"x0tmq-client-v1").digest()
        server_id = hashlib.sha256(b"x0tmq-server-v1").digest()
        # Deterministic nonces derived from shared secret for reproducibility
        nonce_seed = hashlib.sha3_256(
            pqc_shared_secret + session_id.to_bytes(8, "big")
        ).digest()
        client_nonce = nonce_seed[:32]
        server_nonce = nonce_seed[32:64] if len(nonce_seed) >= 64 else hashlib.sha3_256(nonce_seed).digest()[:32]
        transcript = hashlib.sha3_256(
            session_id.to_bytes(8, "big")
        ).digest()

        keys = derive_x0tmq_keys(
            pqc_shared_secret,
            client_nonce=client_nonce,
            server_nonce=server_nonce,
            transcript_hash=transcript,
            client_identity_hash=client_id,
            server_identity_hash=server_id,
        )
        self.session_id = session_id
        self.session_key = keys["session_key"]
        self.cmd_key = keys["cmd_key"]
        self.auth_key = keys["auth_key"]
        self.enc_key = keys["enc_key"]

    @staticmethod
    def generate_mlkem_keypair() -> MlKemKeyPair:
        """Fresh ML-KEM-1024 keypair."""
        return mlkem_keygen(_KEM_ALGORITHM)

    @staticmethod
    def generate_mldsa_keypair_65(seed: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """ML-DSA-65 keypair for hybrid transition (draft §10.6).

        Returns (signing_key, verification_key).
        """
        seed = seed or secrets.token_bytes(32)
        kp = mldsa_derive_reference_keypair(seed, "ML-DSA-65")
        return kp.signing_key, kp.verification_key
