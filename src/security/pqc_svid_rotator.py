"""
Automated PQC + SPIRE SVID Key & Certificate Rotator.
=====================================================

Monitors SPIRE SVID TTL and automatically triggers ML-DSA-65 post-quantum
certificate rotation using the PQC Certificate Authority.

Compliance: Chief Engineer Mandate & 3-Tier Status Taxonomy.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.security.pqc import PQCDigitalSignature
from src.security.spiffe.mtls.mtls_controller_production import MTLSControllerProduction
from src.self_healing.svid_signer import SVIDSigner

logger = logging.getLogger(__name__)


@dataclass
class PQCSVIDCertBundle:
    """Certificate bundle containing rotated SVID and ML-DSA-65 PQC identity."""

    spiffe_id: str
    pqc_algorithm: str
    public_key_hex: str
    secret_key_hex: str
    issued_at_utc: str
    expires_at_utc: str
    rotation_count: int


class PQCSVIDRotator:
    """Automates PQC ML-DSA-65 certificate rotation aligned with SPIRE SVID lifecycles."""

    def __init__(
        self,
        spiffe_id: str = "spiffe://x0tta6bl4.mesh/node/default",
        validity_seconds: int = 3600,
    ):
        self.spiffe_id = spiffe_id
        self.validity_seconds = validity_seconds
        self.rotation_count = 0
        self.dsa = PQCDigitalSignature()
        self.svid_signer = SVIDSigner(spiffe_id=spiffe_id)
        self.current_bundle: Optional[PQCSVIDCertBundle] = None

    def rotate_identity_now(self) -> PQCSVIDCertBundle:
        """Perform immediate ML-DSA-65 PQC certificate rotation for this node."""
        logger.info("🔄 [PQC-Rotator] Rotating ML-DSA-65 PQC identity for %s...", self.spiffe_id)

        keypair = self.dsa.generate_keypair()
        self.rotation_count += 1

        now = datetime.now(timezone.utc)
        expires = datetime.fromtimestamp(now.timestamp() + self.validity_seconds, timezone.utc)

        pub_hex = keypair.public_key.hex() if isinstance(keypair.public_key, bytes) else str(keypair.public_key)
        sec_hex = keypair.secret_key.hex() if isinstance(keypair.secret_key, bytes) else str(keypair.secret_key)
        sec_bytes = keypair.secret_key if isinstance(keypair.secret_key, bytes) else str(keypair.secret_key).encode("utf-8")

        bundle = PQCSVIDCertBundle(
            spiffe_id=self.spiffe_id,
            pqc_algorithm="ML-DSA-65",
            public_key_hex=pub_hex,
            secret_key_hex=sec_hex,
            issued_at_utc=now.isoformat(),
            expires_at_utc=expires.isoformat(),
            rotation_count=self.rotation_count,
        )

        self.current_bundle = bundle
        # Update svid_signer key
        self.svid_signer.set_signing_key(sec_bytes[:32])

        logger.info("✅ [PQC-Rotator] Identity rotated (Rotation #%d). Valid until %s", self.rotation_count, bundle.expires_at_utc)
        return bundle

    def check_and_rotate(self, force: bool = False) -> tuple[bool, PQCSVIDCertBundle]:
        """Check if current bundle is expired or force rotation."""
        if force or self.current_bundle is None:
            bundle = self.rotate_identity_now()
            return True, bundle

        exp_dt = datetime.fromisoformat(self.current_bundle.expires_at_utc)
        if datetime.now(timezone.utc) >= exp_dt:
            bundle = self.rotate_identity_now()
            return True, bundle

        return False, self.current_bundle
