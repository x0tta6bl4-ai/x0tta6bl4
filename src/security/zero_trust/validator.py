"""
Zero Trust Validator Module
Implements validation logic for Zero Trust architecture using SPIFFE/SPIRE.
"""

import logging
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List, Optional

from src.security.spiffe.workload.api_client import X509SVID, WorkloadAPIClient

logger = logging.getLogger(__name__)


class ZeroTrustValidator:
    """
    Validates connections and identities based on Zero Trust principles.
    Integrates with SPIFFE Workload API for identity verification.
    """

    def __init__(self, trust_domain: str = "x0tta6bl4.mesh"):
        self.trust_domain = trust_domain
        # Late-bind WorkloadAPIClient so tests can patch
        # `src.security.zero_trust.WorkloadAPIClient` reliably.
        import src.security.zero_trust as zero_trust

        self.spiffe_client = zero_trust.WorkloadAPIClient()
        self._cached_identity: Optional[X509SVID] = None
        # Stats tracking
        self._validation_attempts: int = 0
        self._validation_successes: int = 0
        self._validation_failures: int = 0

    def get_validation_stats(self) -> Dict[str, float]:
        """
        Get statistics about validation success/failure rates.
        """
        if self._validation_attempts == 0:
            return {
                "success_rate": 1.0,
                "total_attempts": 0,
                "successes": 0,
                "failures": 0,
            }

        success_rate = self._validation_successes / self._validation_attempts
        return {
            "success_rate": success_rate,
            "total_attempts": self._validation_attempts,
            "successes": self._validation_successes,
            "failures": self._validation_failures,
        }

    def validate_connection(
        self, peer_spiffe_id: str, peer_svid: Optional[X509SVID] = None
    ) -> bool:
        """
        Validate a connection attempt from a peer.

        Args:
            peer_spiffe_id: The claimed SPIFFE ID of the peer
            peer_svid: The SVID object of the peer (optional, for deep validation)

        Returns:
            bool: True if connection is allowed, False otherwise
        """
        self._validation_attempts += 1

        # 1. Check Trust Domain
        if not peer_spiffe_id.startswith(f"spiffe://{self.trust_domain}/"):
            logger.warning(
                f"Peer claim {peer_spiffe_id} is outside trust domain {self.trust_domain}"
            )
            self._validation_failures += 1
            return False

        # 2. Validate SVID if provided
        if peer_svid:
            if not self.spiffe_client.validate_peer_svid(
                peer_svid, expected_id=peer_spiffe_id
            ):
                logger.warning(f"SVID validation failed for {peer_spiffe_id}")
                self._validation_failures += 1
                return False

        # 3. Policy Check
        # Note: Policy Engine integration can be added here in the future
        # For now, we use a simple allow-list approach
        if not self._check_policy(peer_spiffe_id):
            self._validation_failures += 1
            return False

        self._validation_successes += 1
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
                "trust_domain": self.trust_domain,
            }
        except Exception as e:
            logger.error(f"Failed to fetch identity: {e}")
            return {"error": str(e)}

    def _check_policy(
        self, peer_spiffe_id: str, resource: Optional[str] = None
    ) -> bool:
        """
        Check if traffic from peer is allowed by policy.

        Now integrates with advanced Policy Engine for fine-grained control.

        Args:
            peer_spiffe_id: SPIFFE ID of the peer
            resource: Optional resource being accessed

        Returns:
            True if access is allowed
        """
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            policy_engine = get_policy_engine()
            decision = policy_engine.evaluate(
                peer_spiffe_id=peer_spiffe_id, resource=resource
            )

            if decision.allowed:
                logger.debug(
                    f"Policy check passed for {peer_spiffe_id}: {decision.reason}"
                )
            else:
                logger.warning(
                    f"Policy check failed for {peer_spiffe_id}: {decision.reason}"
                )

            return decision.allowed
        except ImportError:
            # Fallback to basic policy if Policy Engine not available
            logger.debug("Policy Engine not available, using basic allow-list")
            return True
        except Exception as e:
            logger.error(f"Policy check error: {e}, defaulting to deny")
            return False  # Fail-closed for security
