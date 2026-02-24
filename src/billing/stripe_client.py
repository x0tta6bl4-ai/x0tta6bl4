"""
Stripe Integration for MaaS Billing.

Provides Stripe payment provider integration for:
- Customer management
- Subscription lifecycle
- Payment processing
- Webhook handling
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class StripeConfig:
    """Stripe API configuration."""
    
    api_key: str
    webhook_secret: str
    publishable_key: str
    api_version: str = "2024-11-20.acacia"
    
    # Product/Price IDs
    price_free: str = ""
    price_pro: str = ""
    price_enterprise: str = ""
    
    # Webhook tolerance (seconds)
    webhook_tolerance: int = 300
    
    @classmethod
    def from_env(cls) -> "StripeConfig":
        """Create config from environment variables."""
        return cls(
            api_key=os.getenv("STRIPE_API_KEY", ""),
            webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
            publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
            price_free=os.getenv("STRIPE_PRICE_FREE", ""),
            price_pro=os.getenv("STRIPE_PRICE_PRO", ""),
            price_enterprise=os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
        )
    
    def get_price_id(self, plan: str) -> str:
        """Get Stripe price ID for a plan."""
        prices = {
            "free": self.price_free,
            "starter": self.price_free,
            "pro": self.price_pro,
            "enterprise": self.price_enterprise,
        }
        return prices.get(plan, "")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StripeSubscriptionStatus(str, Enum):
    """Stripe subscription status."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    PAUSED = "paused"


class StripeInvoiceStatus(str, Enum):
    """Stripe invoice status."""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    UNCOLLECTIBLE = "uncollectible"
    VOID = "void"


class StripePaymentIntentStatus(str, Enum):
    """Stripe payment intent status."""
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    REQUIRES_CAPTURE = "requires_capture"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class StripeCustomer:
    """Stripe customer data."""
    
    customer_id: str
    email: str
    name: Optional[str] = None
    created: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "email": self.email,
            "name": self.name,
            "created": self.created.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class StripeSubscription:
    """Stripe subscription data."""
    
    subscription_id: str
    customer_id: str
    status: StripeSubscriptionStatus
    plan: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "customer_id": self.customer_id,
            "status": self.status.value,
            "plan": self.plan,
            "current_period_start": self.current_period_start.isoformat(),
            "current_period_end": self.current_period_end.isoformat(),
            "cancel_at_period_end": self.cancel_at_period_end,
            "metadata": self.metadata,
        }
    
    @property
    def is_active(self) -> bool:
        return self.status in (
            StripeSubscriptionStatus.ACTIVE,
            StripeSubscriptionStatus.TRIALING,
        )


@dataclass
class StripeInvoice:
    """Stripe invoice data."""
    
    invoice_id: str
    customer_id: str
    subscription_id: Optional[str]
    status: StripeInvoiceStatus
    amount_due: Decimal
    amount_paid: Decimal
    currency: str
    created: datetime
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "subscription_id": self.subscription_id,
            "status": self.status.value,
            "amount_due": str(self.amount_due),
            "amount_paid": str(self.amount_paid),
            "currency": self.currency,
            "created": self.created.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }


@dataclass
class StripePaymentMethod:
    """Stripe payment method data."""
    
    payment_method_id: str
    customer_id: str
    type: str  # card, us_bank_account, etc.
    is_default: bool = False
    
    # Card details (if type == card)
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "payment_method_id": self.payment_method_id,
            "customer_id": self.customer_id,
            "type": self.type,
            "is_default": self.is_default,
            "card_brand": self.card_brand,
            "card_last4": self.card_last4,
            "card_exp_month": self.card_exp_month,
            "card_exp_year": self.card_exp_year,
        }


# ---------------------------------------------------------------------------
# Stripe Client
# ---------------------------------------------------------------------------

class StripeClient:
    """
    Stripe API client for MaaS billing.
    
    Provides high-level methods for:
    - Customer CRUD
    - Subscription management
    - Payment processing
    - Webhook signature verification
    """
    
    def __init__(self, config: Optional[StripeConfig] = None):
        self._config = config or StripeConfig.from_env()
        self._stripe = None  # Lazy-loaded stripe module
    
    @property
    def stripe(self):
        """Lazy-load stripe module."""
        if self._stripe is None:
            try:
                import stripe
                stripe.api_key = self._config.api_key
                stripe.api_version = self._config.api_version
                self._stripe = stripe
            except ImportError:
                raise RuntimeError(
                    "Stripe library not installed. Run: pip install stripe"
                )
        return self._stripe

    @stripe.setter
    def stripe(self, value) -> None:
        """Allow tests and callers to inject a mocked stripe adapter."""
        self._stripe = value

    @stripe.deleter
    def stripe(self) -> None:
        """Support patch cleanup by resetting injected stripe adapter."""
        self._stripe = None
    
    # -----------------------------------------------------------------------
    # Customer Methods
    # -----------------------------------------------------------------------
    
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeCustomer:
        """
        Create a new Stripe customer.
        
        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata
            
        Returns:
            Created StripeCustomer
        """
        customer = self.stripe.Customer.create(
            email=email,
            name=name,
            metadata=metadata or {},
        )

        customer_name = getattr(customer, "name", None)
        if not isinstance(customer_name, str):
            customer_name = name

        return StripeCustomer(
            customer_id=customer.id,
            email=customer.email,
            name=customer_name,
            created=datetime.fromtimestamp(customer.created),
            metadata=customer.metadata,
        )
    
    async def get_customer(self, customer_id: str) -> Optional[StripeCustomer]:
        """Get a Stripe customer by ID."""
        try:
            customer = self.stripe.Customer.retrieve(customer_id)
            return StripeCustomer(
                customer_id=customer.id,
                email=customer.email,
                name=customer.name,
                created=datetime.fromtimestamp(customer.created),
                metadata=customer.metadata,
            )
        except self.stripe.error.InvalidRequestError:
            return None
    
    async def update_customer(
        self,
        customer_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeCustomer:
        """Update a Stripe customer."""
        update_data = {}
        if email:
            update_data["email"] = email
        if name:
            update_data["name"] = name
        if metadata:
            update_data["metadata"] = metadata
        
        customer = self.stripe.Customer.modify(customer_id, **update_data)
        
        return StripeCustomer(
            customer_id=customer.id,
            email=customer.email,
            name=customer.name,
            created=datetime.fromtimestamp(customer.created),
            metadata=customer.metadata,
        )
    
    async def delete_customer(self, customer_id: str) -> bool:
        """Delete a Stripe customer."""
        try:
            self.stripe.Customer.delete(customer_id)
            return True
        except self.stripe.error.InvalidRequestError:
            return False
    
    # -----------------------------------------------------------------------
    # Subscription Methods
    # -----------------------------------------------------------------------
    
    async def create_subscription(
        self,
        customer_id: str,
        plan: str,
        trial_days: int = 0,
        metadata: Optional[Dict[str, str]] = None,
    ) -> StripeSubscription:
        """
        Create a new subscription.
        
        Args:
            customer_id: Stripe customer ID
            plan: Plan name (free, pro, enterprise)
            trial_days: Number of trial days
            metadata: Additional metadata
            
        Returns:
            Created StripeSubscription
        """
        price_id = self._config.get_price_id(plan)
        
        if not price_id:
            raise ValueError(f"No price ID configured for plan: {plan}")
        
        subscription_data = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": metadata or {},
        }
        
        if trial_days > 0:
            subscription_data["trial_period_days"] = trial_days
        
        subscription = self.stripe.Subscription.create(**subscription_data)
        
        return self._parse_subscription(subscription)
    
    async def get_subscription(self, subscription_id: str) -> Optional[StripeSubscription]:
        """Get a subscription by ID."""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            return self._parse_subscription(subscription)
        except self.stripe.error.InvalidRequestError:
            return None
    
    async def cancel_subscription(
        self,
        subscription_id: str,
        immediately: bool = False,
    ) -> StripeSubscription:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Subscription to cancel
            immediately: Cancel immediately vs at period end
            
        Returns:
            Canceled StripeSubscription
        """
        if immediately:
            subscription = self.stripe.Subscription.delete(subscription_id)
        else:
            subscription = self.stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
        
        return self._parse_subscription(subscription)
    
    async def update_subscription_plan(
        self,
        subscription_id: str,
        new_plan: str,
    ) -> StripeSubscription:
        """
        Update subscription plan (upgrade/downgrade).
        
        Args:
            subscription_id: Subscription to update
            new_plan: New plan name
            
        Returns:
            Updated StripeSubscription
        """
        subscription = self.stripe.Subscription.retrieve(subscription_id)
        
        new_price_id = self._config.get_price_id(new_plan)
        if not new_price_id:
            raise ValueError(f"No price ID configured for plan: {new_plan}")
        
        # Update the subscription item
        updated = self.stripe.Subscription.modify(
            subscription_id,
            items=[{
                "id": subscription["items"]["data"][0].id,
                "price": new_price_id,
            }],
            metadata={**subscription.metadata, "plan": new_plan},
        )
        
        return self._parse_subscription(updated)
    
    def _parse_subscription(self, sub) -> StripeSubscription:
        """Parse Stripe subscription object."""
        # Extract plan from metadata or price
        plan = sub.metadata.get("plan", "unknown")
        
        return StripeSubscription(
            subscription_id=sub.id,
            customer_id=sub.customer,
            status=StripeSubscriptionStatus(sub.status),
            plan=plan,
            current_period_start=datetime.fromtimestamp(sub.current_period_start),
            current_period_end=datetime.fromtimestamp(sub.current_period_end),
            cancel_at_period_end=sub.cancel_at_period_end,
            metadata=sub.metadata,
        )
    
    # -----------------------------------------------------------------------
    # Payment Methods
    # -----------------------------------------------------------------------
    
    async def attach_payment_method(
        self,
        customer_id: str,
        payment_method_id: str,
    ) -> StripePaymentMethod:
        """Attach a payment method to a customer."""
        pm = self.stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
        )
        
        # Set as default
        self.stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )
        
        return self._parse_payment_method(pm, customer_id, is_default=True)
    
    async def list_payment_methods(
        self,
        customer_id: str,
        type: str = "card",
    ) -> List[StripePaymentMethod]:
        """List customer's payment methods."""
        methods = self.stripe.PaymentMethod.list(
            customer=customer_id,
            type=type,
        )
        
        # Get default payment method
        customer = self.stripe.Customer.retrieve(customer_id)
        default_pm = customer.invoice_settings.default_payment_method
        
        return [
            self._parse_payment_method(
                pm,
                customer_id,
                is_default=(pm.id == default_pm),
            )
            for pm in methods.data
        ]
    
    def _parse_payment_method(
        self,
        pm,
        customer_id: str,
        is_default: bool = False,
    ) -> StripePaymentMethod:
        """Parse Stripe payment method object."""
        card_data = {}
        if pm.type == "card" and pm.card:
            card_data = {
                "card_brand": pm.card.brand,
                "card_last4": pm.card.last4,
                "card_exp_month": pm.card.exp_month,
                "card_exp_year": pm.card.exp_year,
            }
        
        return StripePaymentMethod(
            payment_method_id=pm.id,
            customer_id=customer_id,
            type=pm.type,
            is_default=is_default,
            **card_data,
        )
    
    # -----------------------------------------------------------------------
    # Webhooks
    # -----------------------------------------------------------------------
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> Any:
        """
        Verify and parse webhook signature.
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header value
            
        Returns:
            Parsed event object
            
        Raises:
            stripe.error.SignatureVerificationError: If signature is invalid
        """
        return self.stripe.Webhook.construct_event(
            payload,
            signature,
            self._config.webhook_secret,
        )
    
    async def handle_webhook_event(
        self,
        event: Any,
    ) -> Dict[str, Any]:
        """
        Handle a Stripe webhook event.
        
        Args:
            event: Parsed Stripe event
            
        Returns:
            Processing result
        """
        event_type = event["type"]
        event_data = event["data"]["object"]
        
        handlers = {
            "customer.created": self._handle_customer_created,
            "customer.updated": self._handle_customer_updated,
            "customer.deleted": self._handle_customer_deleted,
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
            "payment_intent.succeeded": self._handle_payment_succeeded,
            "payment_intent.payment_failed": self._handle_payment_failed,
        }
        
        handler = handlers.get(event_type)
        if handler:
            return await handler(event_data)
        
        logger.info(f"Unhandled webhook event type: {event_type}")
        return {"status": "unhandled", "event_type": event_type}
    
    async def _handle_customer_created(self, data: Dict) -> Dict[str, Any]:
        """Handle customer.created event."""
        logger.info(f"Customer created: {data.get('id')}")
        return {"status": "processed", "action": "customer_created"}
    
    async def _handle_customer_updated(self, data: Dict) -> Dict[str, Any]:
        """Handle customer.updated event."""
        logger.info(f"Customer updated: {data.get('id')}")
        return {"status": "processed", "action": "customer_updated"}
    
    async def _handle_customer_deleted(self, data: Dict) -> Dict[str, Any]:
        """Handle customer.deleted event."""
        logger.info(f"Customer deleted: {data.get('id')}")
        return {"status": "processed", "action": "customer_deleted"}
    
    async def _handle_subscription_created(self, data: Dict) -> Dict[str, Any]:
        """Handle subscription created event."""
        logger.info(f"Subscription created: {data.get('id')}")
        return {"status": "processed", "action": "subscription_created"}
    
    async def _handle_subscription_updated(self, data: Dict) -> Dict[str, Any]:
        """Handle subscription updated event."""
        logger.info(f"Subscription updated: {data.get('id')}")
        return {"status": "processed", "action": "subscription_updated"}
    
    async def _handle_subscription_deleted(self, data: Dict) -> Dict[str, Any]:
        """Handle subscription deleted event."""
        logger.info(f"Subscription deleted: {data.get('id')}")
        return {"status": "processed", "action": "subscription_deleted"}
    
    async def _handle_invoice_paid(self, data: Dict) -> Dict[str, Any]:
        """Handle invoice.paid event."""
        logger.info(f"Invoice paid: {data.get('id')}")
        return {"status": "processed", "action": "invoice_paid"}
    
    async def _handle_invoice_payment_failed(self, data: Dict) -> Dict[str, Any]:
        """Handle invoice.payment_failed event."""
        logger.warning(f"Invoice payment failed: {data.get('id')}")
        return {"status": "processed", "action": "invoice_payment_failed"}
    
    async def _handle_payment_succeeded(self, data: Dict) -> Dict[str, Any]:
        """Handle payment_intent.succeeded event."""
        logger.info(f"Payment succeeded: {data.get('id')}")
        return {"status": "processed", "action": "payment_succeeded"}
    
    async def _handle_payment_failed(self, data: Dict) -> Dict[str, Any]:
        """Handle payment_intent.payment_failed event."""
        logger.warning(f"Payment failed: {data.get('id')}")
        return {"status": "processed", "action": "payment_failed"}


__all__ = [
    # Config
    "StripeConfig",
    # Enums
    "StripeSubscriptionStatus",
    "StripeInvoiceStatus",
    "StripePaymentIntentStatus",
    # Data classes
    "StripeCustomer",
    "StripeSubscription",
    "StripeInvoice",
    "StripePaymentMethod",
    # Client
    "StripeClient",
]
