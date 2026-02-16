"""
Kubernetes authentication handler for Vault.

This module provides utilities for authenticating with Vault using
Kubernetes service account tokens, including JWT token management
and K8s environment validation.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class K8sAuthConfig:
    """Kubernetes authentication configuration.

    Attributes:
        role: Vault Kubernetes auth role name
        jwt_path: Path to service account JWT token
        ca_cert_path: Path to K8s CA certificate
        namespace_path: Path to namespace file
        token_expiry_days: Days before JWT token is considered expired
    """

    role: str
    jwt_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ca_cert_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    namespace_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    token_expiry_days: int = 80  # Safe margin before 90-day K8s token expiry


class K8sAuthHandler:
    """Handle Kubernetes service account authentication with Vault.

    This class manages:
    - JWT token reading and caching
    - Namespace discovery
    - CA certificate retrieval
    - K8s environment validation

    Example:
        >>> config = K8sAuthConfig(role="proxy-api")
        >>> handler = K8sAuthHandler(config)
        >>> jwt = handler.get_jwt()
        >>> namespace = handler.get_namespace()
        >>> if handler.validate_running_in_k8s():
        ...     print("Running in Kubernetes")
    """

    def __init__(self, config: K8sAuthConfig):
        """Initialize K8s auth handler.

        Args:
            config: K8s authentication configuration
        """
        self.config = config
        self._namespace: Optional[str] = None
        self._jwt: Optional[str] = None
        self._jwt_expiry: Optional[datetime] = None
        self._ca_cert: Optional[str] = None

    def get_jwt(self) -> str:
        """Get K8s service account JWT token.

        The token is cached until it approaches expiry (80 days by default,
        leaving a 10-day safety margin before the standard 90-day K8s token
        expiration).

        Returns:
            JWT token string

        Raises:
            FileNotFoundError: If token file doesn't exist
            IOError: If token file cannot be read
        """
        # Return cached JWT if still valid
        if self._jwt and self._jwt_expiry:
            if datetime.now() < self._jwt_expiry:
                logger.debug("Returning cached JWT token")
                return self._jwt
            else:
                logger.info("JWT token cache expired, reloading")

        try:
            with open(self.config.jwt_path, "r") as f:
                self._jwt = f.read().strip()

            # Set expiry to configured days (safe margin before 90 days)
            self._jwt_expiry = datetime.now() + timedelta(
                days=self.config.token_expiry_days
            )

            logger.info(
                "Loaded K8s JWT token from %s (expires cache at %s)",
                self.config.jwt_path,
                self._jwt_expiry.isoformat(),
            )
            return self._jwt

        except FileNotFoundError:
            logger.error(
                "JWT token not found at %s. "
                "Ensure the pod has a service account with token mounted.",
                self.config.jwt_path,
            )
            raise
        except IOError as e:
            logger.error("Failed to read JWT token: %s", e)
            raise

    def get_namespace(self) -> str:
        """Get K8s namespace from service account info.

        Returns:
            Namespace string

        Raises:
            FileNotFoundError: If namespace file doesn't exist
        """
        if self._namespace:
            return self._namespace

        try:
            with open(self.config.namespace_path, "r") as f:
                self._namespace = f.read().strip()

            logger.info("Loaded namespace: %s", self._namespace)
            return self._namespace

        except FileNotFoundError:
            logger.error(
                "Namespace file not found at %s. "
                "Ensure running in a Kubernetes pod.",
                self.config.namespace_path,
            )
            raise

    def get_ca_cert(self) -> str:
        """Get K8s CA certificate for TLS verification.

        Returns:
            CA certificate as PEM string

        Raises:
            FileNotFoundError: If CA cert file doesn't exist
        """
        if self._ca_cert:
            return self._ca_cert

        try:
            with open(self.config.ca_cert_path, "r") as f:
                self._ca_cert = f.read()

            logger.debug("Loaded CA cert from %s", self.config.ca_cert_path)
            return self._ca_cert

        except FileNotFoundError:
            logger.error("CA certificate not found at %s", self.config.ca_cert_path)
            raise

    def validate_running_in_k8s(self) -> bool:
        """Verify we're running in a Kubernetes environment.

        Checks for the presence of standard K8s service account files.

        Returns:
            True if all required files exist, False otherwise
        """
        required_files = [
            self.config.jwt_path,
            self.config.namespace_path,
            self.config.ca_cert_path,
        ]

        missing = [f for f in required_files if not os.path.exists(f)]

        if missing:
            logger.warning(
                "Not running in Kubernetes (missing files: %s)", ", ".join(missing)
            )
            return False

        return True

    def get_pod_info(self) -> dict:
        """Get comprehensive pod information.

        Returns:
            Dictionary with pod metadata
        """
        info = {
            "in_kubernetes": self.validate_running_in_k8s(),
            "namespace": None,
            "jwt_available": False,
            "ca_cert_available": False,
        }

        try:
            info["namespace"] = self.get_namespace()
        except FileNotFoundError:
            pass

        try:
            self.get_jwt()
            info["jwt_available"] = True
        except (FileNotFoundError, IOError):
            pass

        try:
            self.get_ca_cert()
            info["ca_cert_available"] = True
        except FileNotFoundError:
            pass

        return info

    def clear_cache(self) -> None:
        """Clear cached JWT and namespace data.

        Call this if you suspect the service account token has been rotated.
        """
        self._jwt = None
        self._jwt_expiry = None
        self._namespace = None
        self._ca_cert = None
        logger.debug("K8s auth cache cleared")
