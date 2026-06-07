"""
MaaS Billing API Shim — x0tta6bl4
=================================

Compatibility shim for v4.0 architecture.
Redirects to modular billing router in src/api/maas/endpoints/billing.py.

DEPRECATED: Use src.api.maas.endpoints.billing instead.
"""

import logging
import os
import warnings
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

# Import from modular router
from .maas.endpoints.billing import (
    router,
    # Compatibility aliases
    list_invoices,
    generate_invoice_modular,
    pay_invoice_manual,
)

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
APP_DOMAIN = os.getenv("APP_DOMAIN", "https://app.x0tta6bl4.com")
STRIPE_PLANS = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),
    "pro": os.getenv("STRIPE_PRICE_PRO"),
    "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
}

warnings.warn(
    "src.api.maas_billing is deprecated. Use src.api.maas.endpoints.billing instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-exports for existing imports
__all__ = [
    "router",
    "list_invoices",
    "generate_invoice_modular",
    "pay_invoice_manual",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "APP_DOMAIN",
    "STRIPE_PLANS",
]
