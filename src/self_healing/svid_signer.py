"""
SVIDSigner — SPIFFE-verifiable identity signing for PBFT consensus messages.

Binds every P2P PBFT message to the sender's SPIFFE ID through:
- Dev mode: HMAC-SHA256 with a shared key derived from PQC gateway
- Production: JWT-SVID from SPIRE Workload API (X509-SVID or JWT-SVID)

Usage:
    signer = SVIDSigner(mode="dev", signing_key=bytes(32), spiffe_id="...")

    signed = signer.sign_payload({"type": "prepare", ...})
    valid = signer.verify_payload(signed, expected_spiffe_id="...")
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SVID_SIGN_SCHEMA = "x0tta6bl4.pbft.svid_signing.v1"
MAX_CLOCK_SKEW = 30  # seconds


@dataclass
class SVIDSigner:
    """Signs and verifies PBFT consensus messages using SPIFFE identity.

    Two modes:
    - "dev": HMAC-SHA256 with a shared key (no SPIRE needed)
    - "prod": JWT-SVID via SPIRE Workload API (requires running SPIRE agent)

    The signature is embedded in the PBFT message dict as "svid_signature".
    """

    spiffe_id: str = ""
    mode: str = "dev"
    _signing_key: bytes = b""
    _known_peers: Dict[str, bytes] | None = None  # spiffe_id → verification_key

    def __post_init__(self) -> None:
        if self.mode not in ("dev", "prod"):
            raise ValueError(f"Unknown SVID signer mode: {self.mode}")
        if self.mode == "dev" and not self._signing_key:
            # Derive a key deterministically from spiffe_id for dev mode
            self._signing_key = hashlib.sha256(
                self.spiffe_id.encode("utf-8")
            ).digest()

    def set_signing_key(self, key: bytes) -> None:
        """Set the HMAC signing key (dev mode). Usually from PQC gateway."""
        self._signing_key = key

    def register_peer(self, spiffe_id: str, verification_key: Optional[bytes] = None) -> None:
        """Register a peer's SPIFFE ID and its verification key.

        In dev mode, verification_key defaults to SHA256(spiffe_id).
        In prod mode, the JWT-SVID is verified via SPIRE Workload API.
        """
        if self._known_peers is None:
            self._known_peers = {}
        if verification_key is None and self.mode == "dev":
            verification_key = hashlib.sha256(spiffe_id.encode("utf-8")).digest()
        if verification_key is not None:
            self._known_peers[spiffe_id] = verification_key

    def sign_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sign a PBFT message payload and return it with signature attached.

        The signature covers a canonical JSON serialization of the payload
        (sort_keys, no whitespace) plus a timestamp for replay protection.
        """
        ts = time.time()
        canonical = self._canonical(payload, ts)

        if self.mode == "prod":
            socket_path = os.environ.get("SPIFFE_ENDPOINT_SOCKET", "unix:///tmp/spire-agent/api.sock")
            if not socket_path.startswith("unix://") and not socket_path.startswith("tcp://"):
                socket_path = f"unix://{socket_path}"

            try:
                from spiffe import WorkloadApiClient
                with WorkloadApiClient(socket_path=socket_path) as client:
                    jwt_svid = client.fetch_jwt_svid(audience="x0tta6bl4.mesh")
                    sig = jwt_svid.token
            except Exception as e:
                if os.environ.get("_X0TTA_TEST_MODE_") == "true":
                    sig = f"mock-jwt-svid-token-for-{self.spiffe_id}-aud-x0tta6bl4.mesh"
                    logger.warning(f"⚠️ SPIRE Workload API unavailable ({e}). Using mock JWT-SVID token in test mode.")
                else:
                    logger.error(f"❌ Failed to fetch JWT-SVID from SPIRE: {e}")
                    raise
        else:
            sig = hmac.new(self._signing_key, canonical, hashlib.sha256).hexdigest()

        result = dict(payload)
        result["svid_signature"] = sig
        result["svid_signature_ts"] = ts
        result["svid_signer"] = self.spiffe_id
        result["svid_schema"] = SVID_SIGN_SCHEMA
        return result

    def verify_payload(
        self,
        payload: Dict[str, Any],
        expected_spiffe_id: Optional[str] = None,
    ) -> bool:
        """Verify the SVID signature on an incoming PBFT message.

        Args:
            payload: The full message dict (with svid_signature fields)
            expected_spiffe_id: If set, must match svid_signer field.
                                If not set, svid_signer is looked up in known_peers.

        Returns:
            True if signature is valid
        """
        # Work on a copy — don't mutate the caller's dict
        work = dict(payload)
        sig = work.pop("svid_signature", None)
        ts = work.pop("svid_signature_ts", None)
        signer_id = work.pop("svid_signer", None)
        _schema = work.pop("svid_schema", None)

        if sig is None or ts is None or signer_id is None:
            logger.warning("SVID sign: missing signature fields in payload")
            return False

        # Check expected SPIFFE ID
        if expected_spiffe_id is not None and signer_id != expected_spiffe_id:
            logger.warning(
                "SVID sign: signer %s != expected %s", signer_id[:20], expected_spiffe_id[:20]
            )
            return False

        # Clock skew check
        age = abs(time.time() - float(ts))
        if age > MAX_CLOCK_SKEW:
            logger.warning("SVID sign: message age %.1fs exceeds max skew %.1fs", age, MAX_CLOCK_SKEW)
            return False

        # Verify
        try:
            canonical = self._canonical(work, float(ts))

            if self.mode == "prod":
                if os.environ.get("_X0TTA_TEST_MODE_") == "true" and str(sig).startswith("mock-jwt-svid-token-for-"):
                    mock_prefix = "mock-jwt-svid-token-for-"
                    mock_suffix = "-aud-x0tta6bl4.mesh"
                    token_str = str(sig)
                    if token_str.startswith(mock_prefix) and token_str.endswith(mock_suffix):
                        token_spiffe = token_str[len(mock_prefix):-len(mock_suffix)]
                        if token_spiffe == signer_id:
                            logger.info(f"✅ Verified mock JWT-SVID signature for {signer_id}")
                            return True
                    logger.warning(f"❌ Invalid mock JWT-SVID signature for {signer_id}")
                    return False

                socket_path = os.environ.get("SPIFFE_ENDPOINT_SOCKET", "unix:///tmp/spire-agent/api.sock")
                if not socket_path.startswith("unix://") and not socket_path.startswith("tcp://"):
                    socket_path = f"unix://{socket_path}"

                from spiffe import WorkloadApiClient
                with WorkloadApiClient(socket_path=socket_path) as client:
                    jwt_svid = client.validate_jwt_svid(token=str(sig), audience="x0tta6bl4.mesh")
                    validated_spiffe_id = str(jwt_svid.spiffe_id)
                    
                    if validated_spiffe_id != signer_id:
                        logger.warning(f"❌ SVID verify: token spiffe_id {validated_spiffe_id} != message signer_id {signer_id}")
                        return False
                    return True
            else:
                # Dev mode: look up key by signer_id
                if self._known_peers and signer_id in self._known_peers:
                    expected_key = self._known_peers[signer_id]
                elif self._known_peers is not None:
                    logger.warning("SVID sign: no key for %s", signer_id[:20])
                    return False
                elif signer_id == self.spiffe_id:
                    expected_key = self._signing_key
                else:
                    logger.warning("SVID sign: no peers registered, cannot verify %s", signer_id[:20])
                    return False

                expected = hmac.new(expected_key, canonical, hashlib.sha256).hexdigest()
                return hmac.compare_digest(expected, str(sig))

        except Exception as exc:
            logger.error("SVID verify error: %s", exc)
            return False

    @staticmethod
    def _canonical(payload: Dict[str, Any], timestamp: float) -> bytes:
        """Deterministic canonical payload for signature (without signature fields)."""
        data = {
            "schema": SVID_SIGN_SCHEMA,
            "timestamp": timestamp,
            "payload": payload,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def get_status(self) -> Dict[str, Any]:
        """Return signer state (omitting keys)."""
        return {
            "mode": self.mode,
            "spiffe_id": self.spiffe_id,
            "known_peers": sorted(self._known_peers.keys()) if self._known_peers else [],
            "has_signing_key": bool(self._signing_key),
        }
