"""x0tMQ session manager — PQC-authenticated MAVLink v2 session.

Phases
------
1. SESSION_INIT (MSG_ID 50001)
   GCS encapsulates an ML-KEM-1024 key and sends the ciphertext (fragmented
   via X0TMQ_CHUNK).  The UAV decapsulates and derives session keys.

2. SIGNED_CMD (MSG_ID 50002)
   Critical commands carry an ML-DSA-87 signature (fragmented).  The
   receiver reassembles and verifies before applying the command.

3. Telemetry HMAC
   High-frequency telemetry is authenticated with HMAC-SHA3-256 keyed
   from the ML-KEM shared secret.

All heavy PQC operations delegate to the first-party implementations
in src.network.firstparty_vpn.{mlkem, mldsa, crypto}.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import List, Optional, Tuple

from src.network.firstparty_vpn.crypto import (
    PqcSessionMaterial,
    derive_session_keys,
)
from src.network.firstparty_vpn.mlkem import (
    ML_KEM_SHARED_SECRET_BYTES,
    MlKemEncapsulation,
    MlKemKeyPair,
    mlkem_decapsulate,
    mlkem_encapsulate,
    mlkem_keygen,
)
from src.network.firstparty_vpn.mldsa import (
    mldsa_reference_sign,
    mldsa_reference_verify,
)

from .chunk import CleitonqChunker
from .frame import MavlinkV2Frame


# Aliases matching the IETF draft terminology.
_KEM_ALGORITHM = "ML-KEM-1024"
_SIG_ALGORITHM = "ML-DSA-87"

# MAVLink message IDs reserved for x0tMQ.
MSG_SESSION_INIT = 50001
MSG_SIGNED_CMD = 50002


class CleitonqSessionManager:
    """PQC-authenticated session between a GCS and a UAV.

    Thread-safety: not guarded.  Use one instance per direction.

    Example (GCS side):
        mgr = CleitonqSessionManager(sys_id=1, comp_id=1)
        # one-time: register the UAV's public encapsulation key
        uav_ek = b"..."  # obtained out-of-band
        frames = mgr.initiate_session(42, uav_ek)
        for f in frames:
            radio.send(f.serialize())
    """

    def __init__(self, sys_id: int, comp_id: int) -> None:
        self._sys_id = sys_id
        self._comp_id = comp_id
        self._chunker = CleitonqChunker(sys_id, comp_id)

        # Session state — populated after SESSION_INIT.
        self.session_id: Optional[int] = None
        self.session_key: Optional[bytes] = None
        self.cmd_key: Optional[bytes] = None
        self.auth_key: Optional[bytes] = None

    # ------------------------------------------------------------------
    # Phase 1 — Session establishment (GCS → UAV)
    # ------------------------------------------------------------------

    def initiate_session(
        self, session_id: int, uav_encapsulation_key: bytes
    ) -> Tuple[List[MavlinkV2Frame], bytes]:
        """GCS: generate ML-KEM-1024 keys and encapsulate.

        Returns (chunked_frames, shared_secret_bytes).
        The caller should send the frames and retain *shared_secret*
        for key derivation.
        """
        ek = uav_encapsulation_key
        result: MlKemEncapsulation = mlkem_encapsulate(_KEM_ALGORITHM, ek)
        self._derive_keys(session_id, result.shared_secret)

        frames = self._chunker.fragment(
            session_id, result.ciphertext,
        )
        return frames, result.shared_secret

    def accept_session(
        self,
        uav_mlkem_keypair: MlKemKeyPair,
        reassembled_ciphertext: bytes,
    ) -> bytes:
        """UAV: decapsulate the ML-KEM-1024 ciphertext from the GCS.

        Returns the shared secret (same bytes the GCS derived).
        Call *set_session_from_secret()* to populate the session state.
        """
        ss = mlkem_decapsulate(
            _KEM_ALGORITHM,
            uav_mlkem_keypair.decapsulation_key,
            reassembled_ciphertext,
        )
        return ss

    # ------------------------------------------------------------------
    # Phase 2 — Command signing (GCS) & verification (UAV)
    # ------------------------------------------------------------------

    def sign_command(
        self,
        cmd_payload: bytes,
        gcs_signing_key: bytes,
    ) -> List[MavlinkV2Frame]:
        """GCS: ML-DSA-87 sign a command, return chunked SIGNED_CMD frames.

        *cmd_payload* is the *serialized* MAVLink command frame.
        """
        sig = mldsa_reference_sign(_SIG_ALGORITHM, gcs_signing_key, cmd_payload)
        return self._chunker.fragment(
            self.session_id or 0, sig,
        )

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
        """Compute a 32-byte HMAC-SHA3-256 tag over *data*.

        Raises ValueError if the session has not been established.
        """
        if self.auth_key is None:
            raise ValueError("x0tMQ session not established")
        return hmac.new(self.auth_key, data, hashlib.sha3_256).digest()

    def verify_telemetry(self, data: bytes, tag: bytes) -> bool:
        """Constant-time verification of a telemetry HMAC tag."""
        expected = self.authenticate_telemetry(data)
        return hmac.compare_digest(expected, tag)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def set_session_from_secret(
        self, session_id: int, shared_secret: bytes
    ) -> None:
        """Populate session state from raw ML-KEM shared secret.

        Call this on the UAV side after decapsulation.
        """
        self._derive_keys(session_id, shared_secret)

    def _derive_keys(self, session_id: int, pqc_shared_secret: bytes) -> None:
        """Derive directional keys via HKDF-SHA3-256 (draft Section 7)."""
        self.session_id = session_id

        # Use the existing x0tta6bl4 key-derivation machinery.
        material = PqcSessionMaterial.create(
            kem_algorithm=_KEM_ALGORITHM,
            signature_algorithm=_SIG_ALGORITHM,
            pqc_shared_secret=pqc_shared_secret,
            transcript=b"x0tmq-v1-session-init",
            client_identity_hash=hashlib.sha256(
                f"x0tmq:{_KEM_ALGORITHM}".encode()
            ).digest(),
            server_identity_hash=hashlib.sha256(
                f"x0tmq:{_SIG_ALGORITHM}".encode()
            ).digest(),
        )
        keys = derive_session_keys(material)

        # Map to x0tMQ naming (draft Section 7).
        self.session_key = keys.client_tx
        self.cmd_key = keys.control
        self.auth_key = keys.client_rx

    @staticmethod
    def generate_mlkem_keypair() -> MlKemKeyPair:
        """Generate a fresh ML-KEM-1024 keypair (GCS or UAV)."""
        return mlkem_keygen(_KEM_ALGORITHM)

    @staticmethod
    def generate_mldsa_keypair_65(
        seed: Optional[bytes] = None,
    ) -> Tuple[bytes, bytes]:
        """Generate an ML-DSA-65 keypair for the hybrid transition.

        Returns (signing_key, verification_key).
        """
        from src.network.firstparty_vpn.mldsa import mldsa_derive_reference_keypair

        seed = seed or secrets.token_bytes(32)
        kp = mldsa_derive_reference_keypair(seed, "ML-DSA-65")
        return kp.signing_key, kp.verification_key
