"""
PQC Fallback Handler with Alerting
"""

import logging
import time
from typing import Optional

from src.monitoring.pqc_metrics import (check_fallback_ttl, disable_fallback,
                                        enable_fallback, is_fallback_enabled,
                                        record_handshake_failure)

logger = logging.getLogger(__name__)


class PQCFallbackHandler:
    """
    Handles PQC fallback with strict TTL and alerting.

    Usage:
        handler = PQCFallbackHandler()

        try:
            # Try real PQC
            result = liboqs_backend.kem_encapsulate(...)
        except Exception as e:
            # Fallback to classical
            handler.handle_fallback("liboqs_error", str(e))
            result = classical_backend.encapsulate(...)
    """

    def __init__(self):
        self.fallback_ttl = 3600  # 1 hour

    def handle_fallback(self, reason: str, details: str = ""):
        """
        Handle PQC fallback event.

        Args:
            reason: Reason for fallback (e.g., 'liboqs_error', 'timeout', 'invalid_key')
            details: Additional details about the failure
        """
        if not is_fallback_enabled():
            enable_fallback(reason)
            record_handshake_failure(reason)

        logger.warning(f"⚠️ PQC fallback active: {reason}. Details: {details}")

    def check_ttl(self) -> bool:
        """Check if fallback TTL expired."""
        return check_fallback_ttl()

    def restore_normal(self):
        """Restore normal PQC operation."""
        if is_fallback_enabled():
            disable_fallback()
            logger.info("✅ PQC fallback disabled - normal operation restored")
