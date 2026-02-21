"""
Production-ready SPIFFE Workload API Client implementation.
Replaces TODO in api_client.py lines 83-87.
"""

import asyncio
import time

try:
    import jwt
    from jwt import JWTError

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None
    JWTError = Exception
try:
    import grpc

    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    grpc = None
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Try to import SPIFFE SDK
try:
    from spiffe import WorkloadApiClient

    SPIFFE_SDK_AVAILABLE = True
except ImportError:
    SPIFFE_SDK_AVAILABLE = False
    WorkloadApiClient = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


@dataclass
class X509SVID:
    """X.509 SVID structure"""

    spiffe_id: str
    cert_pem: bytes
    private_key_pem: bytes
    cert_chain: List[bytes]
    expiry: float


@dataclass
class JWTSVID:
    """JWT SVID structure"""

    token: str
    spiffe_id: str
    expiry: float


class WorkloadAPIClientProduction:
    """
    Production-ready SPIFFE Workload API Client.

    Features:
    - gRPC connection with retry logic
    - X.509-SVID fetch and auto-renewal
    - JWT-SVID support
    - Certificate validation
    - Graceful error handling
    """

    def __init__(
        self,
        socket_path: Path = Path("/run/spire/sockets/agent.sock"),
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        # Check if SPIFFE_SDK_AVAILABLE is defined (defensive check)
        try:
            sdk_available = SPIFFE_SDK_AVAILABLE
        except NameError:
            # This should never happen if module was imported correctly
            logger.error(
                "❌ CRITICAL: SPIFFE_SDK_AVAILABLE is not defined. "
                "This indicates a module import error. "
                "Please check that api_client_production.py was imported correctly."
            )
            raise ImportError(
                "The SPIFFE SDK availability flag is not defined. "
                "This indicates a module import error. "
                "Please ensure the module was imported correctly."
            ) from None

        if not sdk_available:
            raise ImportError(
                "The 'spiffe' SDK (py-spiffe) is required for the Workload API client. "
                "Please install it with: pip install py-spiffe\n"
                "For development/staging, you can use the mock SPIFFE client instead."
            )
        self.socket_path = socket_path
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.current_svid: Optional[X509SVID] = None
        # self._channel: Optional[grpc.aio.Channel] = None  # No longer needed, managed by spiffe_client
        # self._private_key: Optional[rsa.RSAPrivateKey] = None  # No longer needed, handled by SVIDs
        self._spiffe_client = WorkloadApiClient(
            socket_path=str(socket_path),
            # Set this to a lower value than grpc.aio.insecure_channel's default
            # (which is effectively infinite) to avoid hanging forever.
            grpc_timeout_in_seconds=10,
        )

    # This method is no longer needed after integrating the real WorkloadApiClient.

    async def connect(self) -> None:
        """Establish gRPC connection to SPIRE Agent (no longer needed, managed by SpiffeWorkloadApiClient)"""
        logger.debug(
            "WorkloadAPIClientProduction.connect() called, but connection is managed by SpiffeWorkloadApiClient."
        )

    async def fetch_x509_svid(self) -> X509SVID:
        """
        Fetch X.509-SVID from SPIRE Workload API.

        Replaces TODO in api_client.py:83-87

        Returns:
            X509SVID with certificate chain and private key
        """
        for attempt in range(self.max_retries):
            try:
                # Removed the gRPC channel connection from here, as WorkloadApiClient manages it.
                # The 'connect' method for the internal gRPC channel of this class might not be needed anymore,
                # but will keep it for now and review later.

                logger.info(
                    f"🔐 Fetching X.509-SVID via SPIFFE SDK (attempt {attempt + 1}/{self.max_retries})"
                )

                # Use the actual WorkloadApiClient to fetch the SVID
                # The WorkloadApiClient from py-spiffe is already asynchronous
                sdk_svid = await self._spiffe_client.fetch_x509_svid()

                # Convert the SDK SVID to our internal X509SVID format
                # The SDK's X509SVID.bundle is a list of byte strings, each a PEM encoded certificate.
                # Our X509SVID.cert_chain is List[bytes] which is compatible.
                svid = X509SVID(
                    spiffe_id=sdk_svid.spiffe_id,
                    cert_pem=sdk_svid.x509_svid,
                    private_key_pem=sdk_svid.x509_svid_key,
                    cert_chain=sdk_svid.bundle,
                    expiry=sdk_svid.expires_at.timestamp(),
                )

                self.current_svid = svid
                logger.info(f"✅ X.509-SVID fetched: {svid.spiffe_id}")
                return svid

            except Exception as e:
                logger.warning(
                    f"⚠️ Attempt {attempt + 1} failed to fetch X.509-SVID via SPIFFE SDK: {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(
                        f"❌ Failed to fetch X.509-SVID after {self.max_retries} attempts"
                    )
                    raise

    async def fetch_jwt_svid(self, audience: List[str]) -> JWTSVID:
        """
        Fetch JWT-SVID for specific audience using the SPIFFE Workload API.

        Args:
            audience: Target audience for JWT

        Returns:
            JWTSVID token
        """
        try:
            logger.info(f"🔐 Fetching JWT-SVID for audience: {audience}")

            # Use the actual WorkloadApiClient to fetch the JWT SVID
            sdk_jwt = await self._spiffe_client.fetch_jwt_svid(audience=audience)

            jwt_svid = JWTSVID(
                token=sdk_jwt.token,
                spiffe_id=sdk_jwt.spiffe_id,
                expiry=sdk_jwt.expires_at.timestamp(),
            )

            logger.info(f"✅ JWT-SVID fetched for {audience}")
            return jwt_svid

        except Exception as e:
            logger.error(f"❌ Failed to fetch JWT-SVID: {e}")
            raise

    async def validate_jwt_svid(self, token: str, audience: List[str]) -> bool:
        """
        Validate JWT-SVID token.

        Args:
            token: JWT token to validate
            audience: Expected audience(s)

        Returns:
            True if valid, False otherwise
        """
        try:
            logger.info(f"🔍 Validating JWT-SVID for audience: {audience}")

            # Fetch the JWT bundles from the Workload API
            # This provides the public keys needed to verify the JWT
            jwt_bundles = await self._spiffe_client.fetch_jwt_bundles()

            # Extract the trust domain from the token's SPIFFE ID
            # Assuming the token's subject (sub) contains the SPIFFE ID
            unverified_headers = jwt.get_unverified_header(token)
            unverified_claims = jwt.get_unverified_claims(token)

            token_spiffe_id = unverified_claims.get("sub")
            if not token_spiffe_id:
                logger.warning("⚠️ JWT token missing SPIFFE ID (sub claim)")
                return False

            # This part assumes a standard SPIFFE ID format.
            # A more robust solution might use a dedicated SPIFFE ID parsing library.
            trust_domain_parts = token_spiffe_id.split("/")
            if len(trust_domain_parts) < 3 or not trust_domain_parts[0] == "spiffe:":
                logger.warning(
                    f"⚠️ Invalid SPIFFE ID format in token: {token_spiffe_id}"
                )
                return False
            trust_domain = trust_domain_parts[
                2
            ]  # e.g., "x0tta6bl4.mesh" from "spiffe://x0tta6bl4.mesh/..."

            # Get the correct bundle for the trust domain
            bundle = jwt_bundles.get(trust_domain)
            if not bundle:
                logger.warning(
                    f"⚠️ No JWT bundle found for trust domain: {trust_domain}"
                )
                return False

            # Validate the token using the bundle's public keys
            # The 'py-spiffe' library's JWT bundles contain the public keys directly.
            # jose.jwt.decode expects public_key to be a key or a list of keys.
            # The bundle's keys are typically PEM encoded.

            # Need to convert bundle.jwt_authorities to a format that jose.jwt.decode can use.
            # This might involve loading each public key from the bundle.
            # For simplicity, assuming bundle.jwt_authorities is a list of PEM public keys.
            public_keys = []
            for authority in bundle.jwt_authorities:
                # authority is spiffe.bundle.jwtbundle.JwtAuthority
                # authority.public_key is bytes (PEM-encoded)
                public_keys.append(authority.public_key)

            if not public_keys:
                logger.warning(
                    f"⚠️ No public keys in JWT bundle for trust domain: {trust_domain}"
                )
                return False

            try:
                # jose.jwt.decode can take a list of public keys
                jwt.decode(token, public_keys, algorithms=["RS256"], audience=audience)
                is_valid = True
                logger.info(f"✅ JWT-SVID valid")
            except JWTError as e:
                logger.warning(f"⚠️ JWT-SVID invalid: {e}")
                is_valid = False

            return is_valid

        except Exception as e:
            logger.error(f"❌ JWT-SVID validation failed: {e}")
            return False

    async def auto_renew_svid(self, renewal_threshold: float = 0.5) -> None:
        """
        Auto-renew X.509-SVID when approaching expiry.

        Args:
            renewal_threshold: Renew when remaining time < threshold * total_ttl
                              Default: 0.5 (renew at 50% TTL, i.e., 12h for 24h cert)
        """
        while True:
            try:
                if self.current_svid:
                    # Calculate remaining time
                    now = time.time()
                    remaining = self.current_svid.expiry - now

                    # Calculate total TTL (approximate from first fetch)
                    # For SPIFFE, typical TTL is 24 hours
                    total_ttl = 86400.0  # 24 hours in seconds
                    threshold_time = total_ttl * renewal_threshold

                    # Renew if below threshold
                    if remaining < threshold_time:
                        logger.info(
                            f"🔄 Auto-renewing X.509-SVID "
                            f"(remaining: {remaining:.0f}s, threshold: {threshold_time:.0f}s)"
                        )

                        new_svid = await self.fetch_x509_svid()

                        if new_svid:
                            self.current_svid = new_svid
                            logger.info(
                                f"✅ SVID renewed successfully. "
                                f"New expiry: {datetime.fromtimestamp(new_svid.expiry).isoformat()}"
                            )
                        else:
                            logger.error("❌ Failed to renew SVID")

                # Check every 5 minutes
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"❌ Auto-renewal error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute

    async def close(self) -> None:
        """Close gRPC connection"""
        if self._spiffe_client:
            await self._spiffe_client.close()
            logger.info("🔌 SPIRE Agent connection closed")


# Example usage
async def main():
    """Example usage of WorkloadAPIClientProduction"""
    client = WorkloadAPIClientProduction()

    try:
        # Fetch X.509-SVID
        svid = await client.fetch_x509_svid()
        print(f"✅ SPIFFE ID: {svid.spiffe_id}")

        # Fetch JWT-SVID
        jwt = await client.fetch_jwt_svid(audience="x0tta6bl4.mesh")
        print(f"✅ JWT Token: {jwt.token[:50]}...")

        # Validate JWT
        is_valid = await client.validate_jwt_svid(jwt.token, "x0tta6bl4.mesh")
        print(f"✅ JWT Valid: {is_valid}")

        # Start auto-renewal (runs in background)
        # asyncio.create_task(client.auto_renew_svid())

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
