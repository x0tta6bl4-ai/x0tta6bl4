"""
Billing Module - Payment processing and subscription management.

Provides integration with payment providers (Stripe) for MaaS billing.
"""

from typing import Any

__all__ = [
    "StripeConfig",
    "StripeClient",
    "StripeCustomer",
    "StripeSubscription",
    "StripeInvoice",
    "StripePaymentMethod",
    "StripeSubscriptionStatus",
    "StripeInvoiceStatus",
    "StripePaymentIntentStatus",
]


def __getattr__(name: str) -> Any:
    """Lazy loading for billing components."""
    if name in (
        "StripeConfig", "StripeClient",
        "StripeCustomer", "StripeSubscription", "StripeInvoice", "StripePaymentMethod",
        "StripeSubscriptionStatus", "StripeInvoiceStatus", "StripePaymentIntentStatus",
    ):
        from .stripe_client import (
            StripeConfig, StripeClient,
            StripeCustomer, StripeSubscription, StripeInvoice, StripePaymentMethod,
            StripeSubscriptionStatus, StripeInvoiceStatus, StripePaymentIntentStatus,
        )
        return locals().get(name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__version__ = "1.0.0"
