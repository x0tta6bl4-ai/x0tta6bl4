"""
Zero Trust Validator Module
Implements validation logic for Zero Trust architecture using SPIFFE/SPIRE.
"""
import logging
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import asdict

from src.security.spiffe.workload.api_client import WorkloadAPIClient, X509SVID

logger = logging.getLogger(__name__)

class ZeroTrustValidator:
    """
    Validates connections and identities based on Zero Trust principles.
    Integrates with SPIFFE Workload API for identity verification.
    """
    
    def __init__(self, trust_domain: str = "x0tta6bl4.mesh"):
        self.trust_domain = trust_domain
        self.spiffe_client = WorkloadAPIClient()
        self._cached_identity: Optional[X509SVID] = None

    def get_validation_stats(self) -> Dict[str, float]:
        """
        Get statistics about validation success/failure rates.
        Kept for backward compatibility.
        """
        # TODO: Implement real stats tracking
        return {'success_rate': 1.0}

    def validate_connection(self, peer_spiffe_id: str, peer_svid: Optional[X509SVID] = None) -> bool:
        """
        Validate a connection attempt from a peer.
        
        Args:
            peer_spiffe_id: The claimed SPIFFE ID of the peer
            peer_svid: The SVID object of the peer (optional, for deep validation)
            
        Returns:
            bool: True if connection is allowed, False otherwise
        """
        # 1. Check Trust Domain
        if not peer_spiffe_id.startswith(f"spiffe://{self.trust_domain}/"):
            logger.warning(f"Peer claim {peer_spiffe_id} is outside trust domain {self.trust_domain}")
            return False

        # 2. Validate SVID if provided
        if peer_svid:
            if not self.spiffe_client.validate_peer_svid(peer_svid, expected_id=peer_spiffe_id):
                logger.warning(f"SVID validation failed for {peer_spiffe_id}")
                return False

        # 3. Policy Check (Stub for Policy Engine integration)
        # TODO: Integrate with Policy Engine
        if not self._check_policy(peer_spiffe_id):
            return False

        return True

    def get_my_identity(self) -> Dict[str, str]:
        """
        Get current workload identity.
        """
        try:
            svid = self.spiffe_client.fetch_x509_svid()
            self._cached_identity = svid
            return {
                "spiffe_id": svid.spiffe_id,
                "expiry": svid.expiry.isoformat(),
                "trust_domain": self.trust_domain
            }
        except Exception as e:
            logger.error(f"Failed to fetch identity: {e}")
            return {"error": str(e)}

    def _check_policy(self, peer_spiffe_id: str) -> bool:
        """
        Check if traffic from peer is allowed by policy.
        """
        # Default allow for now, but log
        # In production this should default to deny
        return True

