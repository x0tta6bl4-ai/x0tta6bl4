"""
MaaS Billing Helpers - Utility functions for billing operations.

Provides HMAC verification, idempotency handling, and billing calculations.
"""

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pricing per node per hour (in USD)
NODE_PRICING = {
    "standard": Decimal("0.05"),
    "high_memory": Decimal("0.10"),
    "gpu": Decimal("0.50"),
    "quantum_safe": Decimal("0.15"),
}

# Plan multipliers
PLAN_MULTIPLIERS = {
    "free": Decimal("1.0"),
    "pro": Decimal("0.8"),  # 20% discount
    "enterprise": Decimal("0.6"),  # 40% discount
}

# Region surcharges
REGION_SURCHARGES = {
    "us-east-1": Decimal("1.0"),
    "us-west-1": Decimal("1.0"),
    "eu-west-1": Decimal("1.1"),
    "eu-central-1": Decimal("1.1"),
    "ap-southeast-1": Decimal("1.15"),
    "ap-northeast-1": Decimal("1.15"),
}


# ---------------------------------------------------------------------------
# HMAC Verification
# ---------------------------------------------------------------------------

@dataclass
class HMACConfig:
    """Configuration for HMAC verification."""

    secret: str
    algorithm: str = "sha256"
    max_timestamp_skew: int = 300  # 5 minutes

    @classmethod
    def from_env(cls) -> "HMACConfig":
        """Create config from environment variables."""
        import os

        return cls(
            secret=os.getenv("MAAS_WEBHOOK_SECRET", secrets.token_hex(32)),
            algorithm=os.getenv("MAAS_HMAC_ALGORITHM", "sha256"),
            max_timestamp_skew=int(os.getenv("MAAS_MAX_TIMESTAMP_SKEW", "300")),
        )


def compute_hmac_signature(
    payload: Union[str, bytes],
    secret: str,
    algorithm: str = "sha256",
) -> str:
    """
    Compute HMAC signature for a payload.

    Args:
        payload: Data to sign
        secret: HMAC secret
        algorithm: Hash algorithm (sha256, sha384, sha512)

    Returns:
        Hex-encoded signature with algorithm prefix
    """
    if isinstance(payload, str):
        payload = payload.encode()

    hash_func = getattr(hashlib, algorithm, hashlib.sha256)
    signature = hmac.new(
        secret.encode(),
        payload,
        hash_func,
    ).hexdigest()

    return f"{algorithm}={signature}"


def verify_hmac_signature(
    payload: Union[str, bytes],
    signature: str,
    secret: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify HMAC signature.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        payload: Original data
        signature: Signature to verify (with or without algorithm prefix)
        secret: HMAC secret
        algorithm: Expected algorithm

    Returns:
        True if signature is valid
    """
    if isinstance(payload, str):
        payload = payload.encode()

    # Parse signature
    if "=" in signature:
        sig_algorithm, sig_value = signature.split("=", 1)
        algorithm = sig_algorithm
    else:
        sig_value = signature

    # Compute expected signature
    expected = compute_hmac_signature(payload, secret, algorithm)
    _, expected_value = expected.split("=", 1)

    # Constant-time comparison
    return hmac.compare_digest(expected_value, sig_value)


def verify_webhook_with_timestamp(
    payload: Union[str, bytes],
    signature: str,
    timestamp: str,
    secret: str,
    max_skew: int = 300,
) -> bool:
    """
    Verify webhook with timestamp for replay protection.

    Args:
        payload: Request body
        signature: Signature from header
        timestamp: Timestamp from header
        secret: HMAC secret
        max_skew: Maximum allowed timestamp skew in seconds

    Returns:
        True if signature is valid and timestamp is within skew
    """
    # Check timestamp
    try:
        ts = int(timestamp)
        current_time = int(time.time())

        if abs(current_time - ts) > max_skew:
            logger.warning(
                f"Timestamp skew too large: {abs(current_time - ts)}s > {max_skew}s"
            )
            return False
    except ValueError:
        logger.warning(f"Invalid timestamp: {timestamp}")
        return False

    # Construct signed payload
    if isinstance(payload, bytes):
        payload = payload.decode()

    signed_payload = f"{timestamp}.{payload}"

    return verify_hmac_signature(signed_payload, signature, secret)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@dataclass
class IdempotencyRecord:
    """Record of an idempotent operation."""

    key: str
    status: str  # "pending", "completed", "failed"
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    ttl_seconds: int = 86400  # 24 hours

    def is_expired(self) -> bool:
        """Check if record has expired."""
        expires_at = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() > expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class IdempotencyStore:
    """
    In-memory idempotency store.

    For production, replace with Redis or database-backed store.
    """

    def __init__(self, default_ttl: int = 86400):
        self._records: Dict[str, IdempotencyRecord] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[IdempotencyRecord]:
        """Get an idempotency record."""
        record = self._records.get(key)

        if record and record.is_expired():
            del self._records[key]
            return None

        return record

    def set_pending(self, key: str) -> IdempotencyRecord:
        """Mark an operation as pending."""
        record = IdempotencyRecord(
            key=key,
            status="pending",
            ttl_seconds=self._default_ttl,
        )
        self._records[key] = record
        return record

    def set_completed(
        self,
        key: str,
        result: Dict[str, Any],
    ) -> IdempotencyRecord:
        """Mark an operation as completed with result."""
        record = self._records.get(key)

        if not record:
            record = IdempotencyRecord(
                key=key,
                status="completed",
                result=result,
                ttl_seconds=self._default_ttl,
            )
        else:
            record.status = "completed"
            record.result = result
            record.completed_at = datetime.utcnow()

        self._records[key] = record
        return record

    def set_failed(self, key: str, error: str) -> IdempotencyRecord:
        """Mark an operation as failed."""
        record = self._records.get(key)

        if record:
            record.status = "failed"
            record.result = {"error": error}
            record.completed_at = datetime.utcnow()

        return record

    def cleanup_expired(self) -> int:
        """Remove expired records. Returns count of removed records."""
        expired_keys = [
            key for key, record in self._records.items()
            if record.is_expired()
        ]

        for key in expired_keys:
            del self._records[key]

        return len(expired_keys)


# Global idempotency store
_idempotency_store: Optional[IdempotencyStore] = None


def get_idempotency_store() -> IdempotencyStore:
    """Get or create the global idempotency store."""
    global _idempotency_store
    if _idempotency_store is None:
        _idempotency_store = IdempotencyStore()
    return _idempotency_store


T = TypeVar("T")


async def with_idempotency(
    key: str,
    operation: Callable[[], T],
    store: Optional[IdempotencyStore] = None,
) -> Dict[str, Any]:
    """
    Execute an operation with idempotency protection.

    Args:
        key: Idempotency key
        operation: Async function to execute
        store: Optional idempotency store (uses global if not provided)

    Returns:
        Operation result with idempotency metadata
    """
    if store is None:
        store = get_idempotency_store()

    # Check for existing record
    existing = store.get(key)

    if existing:
        if existing.status == "completed":
            logger.info(f"Returning cached result for idempotency key: {key}")
            return {
                **existing.result,
                "_idempotent": True,
                "_cached_at": existing.completed_at.isoformat(),
            }
        elif existing.status == "pending":
            # Operation in progress - could wait or reject
            logger.warning(f"Operation already in progress: {key}")
            return {
                "error": "operation_in_progress",
                "_idempotent": False,
            }

    # Mark as pending
    store.set_pending(key)

    try:
        # Execute operation
        import asyncio
        if asyncio.iscoroutinefunction(operation):
            result = await operation()
        else:
            result = operation()

        # Store result
        store.set_completed(key, result if isinstance(result, dict) else {"data": result})

        return {
            **(result if isinstance(result, dict) else {"data": result}),
            "_idempotent": False,
        }

    except Exception as e:
        store.set_failed(key, str(e))
        raise


# ---------------------------------------------------------------------------
# Billing Calculations
# ---------------------------------------------------------------------------

def calculate_node_cost(
    node_type: str,
    plan: str,
    region: str,
    hours: float,
) -> Decimal:
    """
    Calculate cost for a node.

    Args:
        node_type: Type of node (standard, high_memory, gpu, quantum_safe)
        plan: Subscription plan
        region: Deployment region
        hours: Number of hours

    Returns:
        Cost in USD
    """
    base_rate = NODE_PRICING.get(node_type, NODE_PRICING["standard"])
    plan_multiplier = PLAN_MULTIPLIERS.get(plan, Decimal("1.0"))
    region_surcharge = REGION_SURCHARGES.get(region, Decimal("1.0"))

    cost = base_rate * plan_multiplier * region_surcharge * Decimal(str(hours))

    # Round to 2 decimal places
    return cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_mesh_cost(
    node_count: int,
    node_type: str,
    plan: str,
    region: str,
    hours: float,
) -> Decimal:
    """
    Calculate total cost for a mesh.

    Args:
        node_count: Number of nodes
        node_type: Type of nodes
        plan: Subscription plan
        region: Deployment region
        hours: Number of hours

    Returns:
        Total cost in USD
    """
    per_node = calculate_node_cost(node_type, plan, region, hours)
    return per_node * node_count


def estimate_monthly_cost(
    node_count: int,
    node_type: str,
    plan: str,
    region: str,
) -> Decimal:
    """
    Estimate monthly cost for a mesh.

    Assumes 730 hours per month (average).

    Args:
        node_count: Number of nodes
        node_type: Type of nodes
        plan: Subscription plan
        region: Deployment region

    Returns:
        Estimated monthly cost in USD
    """
    return calculate_mesh_cost(
        node_count, node_type, plan, region, 730
    )


def format_currency(amount: Decimal, currency: str = "USD") -> str:
    """Format a decimal as currency string."""
    return f"${amount:.2f} {currency}"


# ---------------------------------------------------------------------------
# Invoice Generation
# ---------------------------------------------------------------------------

@dataclass
class InvoiceLineItem:
    """A line item on an invoice."""

    description: str
    quantity: int
    unit_price: Decimal
    total: Decimal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": str(self.unit_price),
            "total": str(self.total),
        }


@dataclass
class Invoice:
    """An invoice for billing."""

    invoice_id: str
    customer_id: str
    line_items: List[InvoiceLineItem]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    currency: str = "USD"
    due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "line_items": [item.to_dict() for item in self.line_items],
            "subtotal": str(self.subtotal),
            "tax": str(self.tax),
            "total": str(self.total),
            "currency": self.currency,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
        }


def generate_invoice(
    customer_id: str,
    mesh_usage: List[Dict[str, Any]],
    tax_rate: Decimal = Decimal("0.0"),
) -> Invoice:
    """
    Generate an invoice from mesh usage data.

    Args:
        customer_id: Customer ID
        mesh_usage: List of mesh usage records
        tax_rate: Tax rate (e.g., 0.1 for 10%)

    Returns:
        Generated invoice
    """
    import secrets

    line_items = []
    subtotal = Decimal("0")

    for usage in mesh_usage:
        mesh_id = usage["mesh_id"]
        node_count = usage["node_count"]
        node_type = usage.get("node_type", "standard")
        plan = usage["plan"]
        region = usage["region"]
        hours = usage["hours"]

        cost = calculate_mesh_cost(
            node_count, node_type, plan, region, hours
        )

        line_item = InvoiceLineItem(
            description=f"Mesh {mesh_id}: {node_count}x {node_type} nodes ({hours:.1f}h)",
            quantity=1,
            unit_price=cost,
            total=cost,
        )

        line_items.append(line_item)
        subtotal += cost

    tax = subtotal * tax_rate
    total = subtotal + tax

    return Invoice(
        invoice_id=f"inv-{secrets.token_hex(8)}",
        customer_id=customer_id,
        line_items=line_items,
        subtotal=subtotal,
        tax=tax,
        total=total,
        due_date=datetime.utcnow() + timedelta(days=30),
    )


__all__ = [
    # HMAC
    "HMACConfig",
    "compute_hmac_signature",
    "verify_hmac_signature",
    "verify_webhook_with_timestamp",
    # Idempotency
    "IdempotencyRecord",
    "IdempotencyStore",
    "get_idempotency_store",
    "with_idempotency",
    # Billing
    "NODE_PRICING",
    "PLAN_MULTIPLIERS",
    "REGION_SURCHARGES",
    "calculate_node_cost",
    "calculate_mesh_cost",
    "estimate_monthly_cost",
    "format_currency",
    # Invoice
    "InvoiceLineItem",
    "Invoice",
    "generate_invoice",
]
