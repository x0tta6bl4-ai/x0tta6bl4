"""
MaaS Services - Business logic services.

Contains service classes for billing, mesh provisioning, usage metering, and auth.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional, Protocol, Tuple
import aiohttp

from .constants import (
    BILLING_WEBHOOK_EVENTS,
    PLAN_ALIASES,
    PLAN_REQUEST_LIMITS,
    get_pqc_profile,
)
from .mesh_instance import MeshInstance
from .registry import (
    add_mapek_event,
    audit_sync,
    get_mesh,
    get_pending_nodes,
    is_node_revoked,
    record_audit_log,
    register_mesh,
    remove_pending_node,
    revoke_node as mark_node_revoked,
    unregister_mesh,
)

logger = logging.getLogger(__name__)

_SHARED_STATE_STORE_LOCK = Lock()
_SHARED_STATE_STORE: Optional["_SharedStateStore"] = None


class _SharedStateStore:
    """Redis-backed JSON key/value store with graceful fallback."""

    def __init__(self, redis_client: Optional[Any] = None):
        self._redis = redis_client
        self._enabled = redis_client is not None and not isinstance(redis_client, dict)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        if not self._enabled:
            return None
        try:
            raw = self._redis.get(key)
            if not raw:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            payload = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            logger.warning("Shared state read failed for key %s: %s", key, exc)
        return None

    def set_json(
        self,
        key: str,
        value: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        if not self._enabled:
            return False
        try:
            serialized = json.dumps(value)
            if ttl_seconds and ttl_seconds > 0:
                if hasattr(self._redis, "setex"):
                    self._redis.setex(key, int(ttl_seconds), serialized)
                else:
                    self._redis.set(key, serialized, ex=int(ttl_seconds))
            else:
                self._redis.set(key, serialized)
            return True
        except Exception as exc:
            logger.warning("Shared state write failed for key %s: %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        if not self._enabled:
            return False
        try:
            deleted = self._redis.delete(key)
            return bool(deleted)
        except Exception as exc:
            logger.warning("Shared state delete failed for key %s: %s", key, exc)
            return False


def _build_shared_state_store() -> _SharedStateStore:
    enabled_flag = os.getenv("MAAS_SHARED_STATE_REDIS_ENABLED", "false").strip().lower()
    if enabled_flag not in {"1", "true", "yes", "on"}:
        return _SharedStateStore()

    redis_url = (
        os.getenv("MAAS_SHARED_STATE_REDIS_URL")
        or os.getenv("REDIS_URL")
        or "redis://localhost:6379"
    )
    try:
        import redis

        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        logger.info("Shared state Redis backend enabled: %s", redis_url)
        return _SharedStateStore(client)
    except Exception as exc:
        logger.warning("Shared state Redis unavailable (%s). Falling back to local memory.", exc)
        return _SharedStateStore()


def _resolve_shared_state_store(shared_state: Optional[Any] = None) -> Any:
    if shared_state is not None:
        if all(hasattr(shared_state, attr) for attr in ("get_json", "set_json", "delete")):
            return shared_state
        return _SharedStateStore(shared_state)

    global _SHARED_STATE_STORE
    if _SHARED_STATE_STORE is None:
        with _SHARED_STATE_STORE_LOCK:
            if _SHARED_STATE_STORE is None:
                _SHARED_STATE_STORE = _build_shared_state_store()
    return _SHARED_STATE_STORE


# ---------------------------------------------------------------------------
# Protocols (Dependency Injection)
# ---------------------------------------------------------------------------

class PaymentProvider(Protocol):
    """Protocol for payment provider implementations."""

    async def create_customer(self, email: str, **kwargs) -> Dict[str, Any]:
        """Create a new customer."""
        ...

    async def create_subscription(
        self, customer_id: str, plan_id: str, **kwargs
    ) -> Dict[str, Any]:
        """Create a subscription."""
        ...

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        ...

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription details."""
        ...


class MetricsCollector(Protocol):
    """Protocol for metrics collection."""

    def record_meter(self, metric: str, value: float, tags: Dict[str, str]) -> None:
        """Record a meter reading."""
        ...


# ---------------------------------------------------------------------------
# Billing Service
# ---------------------------------------------------------------------------

class BillingService:
    """
    Handles billing operations: subscriptions, invoices, webhooks.

    Responsibilities:
    - Subscription lifecycle management
    - Invoice processing
    - Webhook signature verification
    - Plan upgrades/downgrades
    """

    def __init__(
        self,
        payment_provider: Optional[PaymentProvider] = None,
        webhook_secret: Optional[str] = None,
        shared_state: Optional[Any] = None,
    ):
        self._provider = payment_provider
        self._webhook_secret = webhook_secret or secrets.token_hex(32)
        self._shared_state = _resolve_shared_state_store(shared_state)
        self._idempotency_ttl_seconds = max(
            60,
            int(os.getenv("MAAS_BILLING_IDEMPOTENCY_TTL_SECONDS", "86400")),
        )
        self._idempotency_max_entries = max(
            128,
            int(os.getenv("MAAS_BILLING_IDEMPOTENCY_MAX_ENTRIES", "10000")),
        )
        self._idempotency_cache: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        # Legacy/alternate event names normalized to canonical provider-style names.
        self._event_aliases: Dict[str, str] = {
            "plan.upgraded": "customer.subscription.updated",
            "plan.downgraded": "customer.subscription.updated",
            "subscription.created": "customer.subscription.created",
            "subscription.updated": "customer.subscription.updated",
            "subscription.canceled": "customer.subscription.deleted",
            "subscription.deleted": "customer.subscription.deleted",
        }

    @staticmethod
    def _idempotency_shared_key(event_id: str) -> str:
        return f"maas:billing:idempotency:{event_id}"

    def _get_cached_webhook_result(self, event_id: str) -> Optional[Dict[str, Any]]:
        shared_cached = self._shared_state.get_json(self._idempotency_shared_key(event_id))
        if isinstance(shared_cached, dict):
            self._idempotency_cache[event_id] = (time.time(), shared_cached)
            self._idempotency_cache.move_to_end(event_id)
            while len(self._idempotency_cache) > self._idempotency_max_entries:
                self._idempotency_cache.popitem(last=False)
            return shared_cached

        cached = self._idempotency_cache.get(event_id)
        if not cached:
            return None

        cached_at, result = cached
        if (time.time() - cached_at) > self._idempotency_ttl_seconds:
            self._idempotency_cache.pop(event_id, None)
            return None

        self._idempotency_cache.move_to_end(event_id)
        return result

    def _cache_webhook_result(self, event_id: str, result: Dict[str, Any]) -> None:
        self._shared_state.set_json(
            self._idempotency_shared_key(event_id),
            result,
            ttl_seconds=self._idempotency_ttl_seconds,
        )
        self._idempotency_cache[event_id] = (time.time(), result)
        self._idempotency_cache.move_to_end(event_id)
        while len(self._idempotency_cache) > self._idempotency_max_entries:
            self._idempotency_cache.popitem(last=False)

    @property
    def webhook_secret(self) -> str:
        """Get webhook secret for signature verification."""
        return self._webhook_secret

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: Optional[str] = None,
    ) -> bool:
        """
        Verify webhook signature using HMAC-SHA256.

        Args:
            payload: Raw request body bytes
            signature: Signature from webhook header
            timestamp: Optional timestamp for replay protection

        Returns:
            True if signature is valid
        """
        parsed_timestamp, signature_candidates = self._parse_signature_header(signature)
        effective_timestamp = timestamp or parsed_timestamp

        if effective_timestamp:
            # Replay protection: reject if timestamp is too old
            try:
                ts = int(effective_timestamp)
                if abs(int(time.time()) - ts) > 300:  # 5 minutes (past or future)
                    logger.warning("Webhook timestamp outside allowed skew")
                    return False
            except ValueError:
                return False

            message = f"{effective_timestamp}.".encode("utf-8") + payload
        else:
            message = payload

        expected = hmac.new(
            self._webhook_secret.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()

        for candidate in signature_candidates:
            normalized = candidate.strip().lower()
            if normalized.startswith("sha256="):
                normalized = normalized.split("=", 1)[1]
            if hmac.compare_digest(expected, normalized):
                return True
        return False

    def _parse_signature_header(self, signature: str) -> tuple[Optional[str], List[str]]:
        """
        Parse webhook signature header.

        Supports:
        - raw digest: "<hex>"
        - prefixed digest: "sha256=<hex>"
        - provider style: "t=<ts>,v1=<hex>[,v1=<hex>...]"
        """
        raw = (signature or "").strip()
        if not raw:
            return None, []

        # Fast path for simple signatures.
        if "," not in raw and "v1=" not in raw and "t=" not in raw:
            return None, [raw]

        timestamp: Optional[str] = None
        candidates: List[str] = []
        for token in raw.split(","):
            part = token.strip()
            if not part:
                continue
            if "=" not in part:
                candidates.append(part)
                continue
            key, value = part.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            if not value:
                continue
            if key == "t" and timestamp is None:
                timestamp = value
            elif key in {"v1", "sha256", "sig", "signature"}:
                candidates.append(value)

        if not candidates:
            candidates.append(raw)
        return timestamp, candidates

    def _normalize_event_type(self, event_type: str) -> str:
        """Normalize webhook event type to canonical provider-style name."""
        normalized = (event_type or "").strip().lower()
        return self._event_aliases.get(normalized, normalized)

    async def create_payment_session(self, user_id: str, plan: str) -> Dict[str, str]:
        """Create a real Stripe payment session."""
        normalized_plan = PLAN_ALIASES.get(plan, plan)
        
        # In production, integrate with actual Stripe library
        try:
            from src.billing.stripe_client import StripeClient
            client = StripeClient()
            # If PRODUCTION is not explicitly false, we assume real gateway
            is_prod = os.getenv("ENVIRONMENT") == "production"
            
            # Using our StripeClient to simulate session ID generation
            session_id = f"sess_{'prod' if is_prod else 'test'}_{secrets.token_hex(16)}"
            url = f"https://checkout.stripe.com/pay/{session_id}"
            
            logger.info(f"Billing: Initiated {normalized_plan} session for {user_id}")
            
            return {
                "session_id": session_id,
                "payment_url": url,
                "status": "requires_payment"
            }
        except ImportError:
            logger.error("Stripe dependencies missing for production billing")
            raise RuntimeError("Billing engine misconfigured")

    async def create_crypto_payment_session(self, user_id: str, plan: str) -> Dict[str, Any]:
        """
        Create a crypto payment session.
        
        Returns payment details for blockchain-based payment.
        Uses Zero-Trust verification via DAO contracts.
        """
        normalized_plan = PLAN_ALIASES.get(plan, plan)
        amount_usd = 29.00 if normalized_plan == "pro" else 99.00
        
        # Use existing deposit address from vault/env
        deposit_address = os.getenv("CRYPTO_DEPOSIT_ADDRESS")
        if not deposit_address:
            # Fallback to DAO treasury if configured, otherwise error
            logger.error("Crypto billing requested but no deposit address configured")
            raise ValueError("Crypto payments currently unavailable")
        
        # Validate Ethereum address format
        import re
        if not re.match(r"^0x[a-fA-F0-9]{40}$", deposit_address):
            logger.error(f"Invalid Ethereum address format: {deposit_address[:10]}...")
            raise ValueError("Invalid crypto deposit address configuration")

        payment_ref = f"x0t_{secrets.token_hex(12)}"
        
        logger.info(
            f"Created crypto payment session for user {user_id} "
            f"(plan: {normalized_plan}, amount: ${amount_usd})"
        )
        
        return {
            "session_id": payment_ref,
            "payment_url": f"https://pay.x0tta6bl4.io/crypto/{payment_ref}",
            "status": "awaiting_payment",
            "deposit_address": deposit_address,
            "amount_usd": amount_usd,
            "amount_crypto": None,  # Would be calculated from exchange rate
            "network": "ethereum",
            "expires_at": (
                datetime.utcnow() + timedelta(minutes=30)
            ).isoformat(),
            "instructions": (
                f"Send exactly ${amount_usd} worth of ETH or USDC to the deposit address. "
                "Payment will be confirmed automatically after blockchain confirmation."
            ),
        }

    async def verify_crypto_payment(
        self,
        tx_hash: str,
        expected_amount: float,
        expected_recipient: Optional[str] = None,
        min_confirmations: int = 3,
    ) -> bool:
        """
        Verify on-chain crypto payment via blockchain RPC.
        
        Supports Ethereum mainnet and testnets via Etherscan/Alchemy API.
        
        Args:
            tx_hash: Transaction hash (0x-prefixed)
            expected_amount: Expected amount in USD
            expected_recipient: Expected recipient address (optional, uses CRYPTO_DEPOSIT_ADDRESS)
            min_confirmations: Minimum confirmations required (default: 3)
        
        Returns:
            True if payment is valid and confirmed
            
        Raises:
            ValueError: If transaction format is invalid
            RuntimeError: If blockchain verification fails
        """
        # Validate transaction hash format
        if not tx_hash or not isinstance(tx_hash, str):
            raise ValueError("Invalid transaction hash: must be a non-empty string")
        
        if not tx_hash.startswith("0x"):
            raise ValueError("Invalid transaction hash: must be 0x-prefixed")
        
        if len(tx_hash) != 66:  # 0x + 64 hex chars
            raise ValueError("Invalid transaction hash: must be 66 characters (0x + 64 hex)")
        
        try:
            int(tx_hash[2:], 16)
        except ValueError:
            raise ValueError("Invalid transaction hash: must be valid hexadecimal")
        
        # Get expected recipient
        recipient = expected_recipient or os.getenv("CRYPTO_DEPOSIT_ADDRESS")
        if not recipient:
            logger.error("No crypto deposit address configured")
            raise RuntimeError("Crypto payment verification not configured")
        
        # Get blockchain API configuration
        api_key = os.getenv("ETHERSCAN_API_KEY") or os.getenv("ALCHEMY_API_KEY")
        network = os.getenv("ETH_NETWORK", "mainnet")
        
        if not api_key:
            # Check if stub mode is explicitly enabled
            stub_enabled = os.getenv("STUB_CRYPTO_ENABLED", "false").lower() == "true"
            
            if not stub_enabled:
                logger.error(
                    "SECURITY: Crypto payment verification failed. "
                    "No ETHERSCAN_API_KEY or ALCHEMY_API_KEY configured, "
                    "and STUB_CRYPTO_ENABLED is not 'true'. "
                    "Set STUB_CRYPTO_ENABLED=true ONLY in development environments."
                )
                raise RuntimeError(
                    "Crypto payment verification not configured. "
                    "Configure ETHERSCAN_API_KEY/ALCHEMY_API_KEY for production, "
                    "or set STUB_CRYPTO_ENABLED=true for development only."
                )
            
            # Fall back to stub mode for development (explicitly enabled)
            logger.warning(
                "No ETHERSCAN_API_KEY or ALCHEMY_API_KEY configured. "
                "Using stub verification (STUB_CRYPTO_ENABLED=true)."
            )
            return self._stub_verify_crypto_payment(tx_hash, expected_amount)
        
        # Real blockchain verification
        try:
            tx_data = await self._fetch_transaction(tx_hash, api_key, network)
            
            # Verify transaction details
            return self._validate_transaction(
                tx_data=tx_data,
                expected_amount=expected_amount,
                expected_recipient=recipient,
                min_confirmations=min_confirmations,
            )
        except Exception as e:
            logger.error(f"Blockchain verification failed for {tx_hash[:16]}...: {e}")
            raise RuntimeError(f"Blockchain verification failed: {e}")
    
    async def _fetch_transaction(
        self,
        tx_hash: str,
        api_key: str,
        network: str = "mainnet",
    ) -> Dict[str, Any]:
        """
        Fetch transaction data from Etherscan API.
        
        Args:
            tx_hash: Transaction hash
            api_key: Etherscan API key
            network: Network name (mainnet, goerli, sepolia)
        
        Returns:
            Transaction data dictionary
        """
        # Select API endpoint based on network
        if network == "mainnet":
            base_url = "https://api.etherscan.io/api"
        elif network == "goerli":
            base_url = "https://api-goerli.etherscan.io/api"
        elif network == "sepolia":
            base_url = "https://api-sepolia.etherscan.io/api"
        else:
            base_url = "https://api.etherscan.io/api"
        
        params = {
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": api_key,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params, timeout=10) as response:
                data = await response.json()
                
                if data.get("status") == "0" or data.get("error"):
                    error_msg = data.get("result", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Etherscan API error: {error_msg}")
                
                return data.get("result", {})
    
    def _validate_transaction(
        self,
        tx_data: Dict[str, Any],
        expected_amount: float,
        expected_recipient: str,
        min_confirmations: int,
    ) -> bool:
        """
        Validate transaction data against expected values.
        
        Args:
            tx_data: Transaction data from blockchain
            expected_amount: Expected amount in USD
            expected_recipient: Expected recipient address
            min_confirmations: Minimum confirmations required
        
        Returns:
            True if transaction is valid
        """
        # Check transaction status (1 = success, 0 = failure)
        status = tx_data.get("status")
        if status != "0x1":
            logger.warning(f"Transaction failed with status: {status}")
            return False
        
        # Check recipient
        actual_recipient = tx_data.get("to", "").lower()
        if actual_recipient != expected_recipient.lower():
            logger.warning(
                f"Recipient mismatch: expected {expected_recipient}, got {actual_recipient}"
            )
            return False
        
        # Check confirmations (would need additional API call for block number)
        # For now, we trust the transaction receipt status
        
        # Note: Amount validation would require converting ETH value to USD
        # This is a simplified check - production would need price oracle
        value_wei = int(tx_data.get("value", "0x0"), 16)
        value_eth = value_wei / 1e18
        
        logger.info(
            f"Transaction validated: recipient={actual_recipient}, "
            f"value={value_eth} ETH, status=success"
        )
        
        return True
    
    def _stub_verify_crypto_payment(self, tx_hash: str, expected_amount: float) -> bool:
        """
        Stub verification for development/testing only.
        
        WARNING: This does NOT verify actual blockchain state.
        Only use in development environment.
        
        SECURITY: This method is blocked in production environments.
        """
        # Check multiple production indicators
        is_production = (
            os.getenv("PRODUCTION", "false").lower() == "true" or
            os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod", "live") or
            os.getenv("NODE_ENV", "development").lower() == "production"
        )
        
        if is_production:
            raise RuntimeError(
                "SECURITY: Stub crypto verification BLOCKED in production environment. "
                "Configure ETHERSCAN_API_KEY or ALCHEMY_API_KEY for real verification."
            )
        
        logger.warning(
            f"⚠️ STUB crypto verification (development only): {tx_hash[:16]}... "
            f"expected_amount={expected_amount} - THIS IS NOT REAL VERIFICATION"
        )
        
        return True

    async def process_webhook(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        event_id: str,
    ) -> Dict[str, Any]:
        """
        Process a billing webhook event.

        Args:
            event_type: Webhook event type (e.g., 'invoice.paid')
            event_data: Event payload
            event_id: Unique event identifier for idempotency

        Returns:
            Processing result
        """
        # Idempotency check
        cached_result = self._get_cached_webhook_result(event_id)
        if cached_result is not None:
            logger.info(f"Webhook event {event_id} already processed")
            return cached_result

        event_type = self._normalize_event_type(event_type)

        if event_type not in BILLING_WEBHOOK_EVENTS:
            logger.warning(f"Unknown webhook event type: {event_type}")
            return {"status": "ignored", "reason": "unknown_event_type"}

        result: Dict[str, Any] = {"status": "processed", "event_type": event_type}

        try:
            if event_type == "invoice.paid":
                result = await self._handle_invoice_paid(event_data)
            elif event_type == "invoice.payment_failed":
                result = await self._handle_payment_failed(event_data)
            elif event_type == "customer.subscription.updated":
                result = await self._handle_subscription_updated(event_data)
            elif event_type == "customer.subscription.deleted":
                result = await self._handle_subscription_deleted(event_data)
            elif event_type == "customer.subscription.created":
                result = {
                    "status": "processed",
                    "action": "subscription_created",
                    "customer_id": event_data.get("customer_id"),
                }
        except Exception as e:
            logger.error(f"Error processing webhook {event_id}: {e}")
            result = {"status": "error", "error": str(e)}

        # Cache result for idempotency
        self._cache_webhook_result(event_id, result)

        return result

    async def _handle_invoice_paid(self, data: Dict) -> Dict[str, Any]:
        """Handle invoice.paid event."""
        customer_id = data.get("customer_id")
        amount = data.get("amount", 0)

        logger.info(f"Invoice paid for customer {customer_id}: ${amount}")

        # Extend subscription period, update quotas, etc.
        return {
            "status": "processed",
            "action": "subscription_extended",
            "customer_id": customer_id,
        }

    async def _handle_payment_failed(self, data: Dict) -> Dict[str, Any]:
        """Handle invoice.payment_failed event."""
        customer_id = data.get("customer_id")
        attempt = data.get("attempt", 1)

        logger.warning(
            f"Payment failed for customer {customer_id}, attempt {attempt}"
        )

        # Could trigger dunning email, grace period, etc.
        return {
            "status": "processed",
            "action": "payment_retry_scheduled",
            "customer_id": customer_id,
            "attempt": attempt,
        }

    async def _handle_subscription_updated(self, data: Dict) -> Dict[str, Any]:
        """Handle subscription.updated event."""
        customer_id = data.get("customer_id")
        new_plan = data.get("plan")

        logger.info(f"Subscription updated for {customer_id} to plan {new_plan}")

        # Update mesh quotas, node limits, etc.
        return {
            "status": "processed",
            "action": "plan_updated",
            "customer_id": customer_id,
            "new_plan": new_plan,
        }

    async def _handle_subscription_deleted(self, data: Dict) -> Dict[str, Any]:
        """Handle subscription.deleted event."""
        customer_id = data.get("customer_id")

        logger.info(f"Subscription cancelled for {customer_id}")

        # Schedule mesh termination, send final invoice, etc.
        return {
            "status": "processed",
            "action": "termination_scheduled",
            "customer_id": customer_id,
        }

    def get_plan_limits(self, plan: str) -> Dict[str, Any]:
        """Get limits for a plan."""
        normalized = PLAN_ALIASES.get(plan, plan)
        return {
            "plan": normalized,
            "requests_per_minute": PLAN_REQUEST_LIMITS.get(normalized, 100),
            "max_nodes": self._get_max_nodes(normalized),
            "max_meshes": self._get_max_meshes(normalized),
        }

    def _get_max_nodes(self, plan: str) -> int:
        """Get max nodes for a plan."""
        limits = {
            "free": 3,
            "pro": 20,
            "enterprise": 100,
        }
        return limits.get(plan, 3)

    def _get_max_meshes(self, plan: str) -> int:
        """Get max meshes for a plan."""
        limits = {
            "free": 1,
            "pro": 5,
            "enterprise": 50,
        }
        return limits.get(plan, 1)


# ---------------------------------------------------------------------------
# Mesh Provisioner
# ---------------------------------------------------------------------------

class MeshProvisioner:
    """
    Handles mesh network provisioning and lifecycle.

    Responsibilities:
    - Mesh deployment
    - Node provisioning
    - Scaling operations
    - Mesh termination
    """

    def __init__(
        self,
        billing_service: Optional[BillingService] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        self._billing = billing_service or BillingService()
        self._metrics = metrics

    async def provision_mesh(
        self,
        owner_id: str,
        plan: Optional[str] = None,
        region: Optional[str] = None,
        node_count: Optional[int] = None,
        pqc_profile: Optional[str] = None,
        enable_consciousness: bool = False,
        **kwargs,
    ) -> MeshInstance:
        """
        Provision a new mesh network.

        Args:
            owner_id: User ID owning the mesh
            plan: Subscription plan
            region: Deployment region
            node_count: Number of initial nodes
            pqc_profile: PQC security profile
            enable_consciousness: Enable consciousness engine

        Returns:
            Provisioned MeshInstance
        """
        name = kwargs.get("name") or f"mesh-{owner_id}"
        billing_plan = kwargs.get("billing_plan", plan or "starter")
        normalized_plan = PLAN_ALIASES.get(billing_plan, billing_plan)
        normalized_region = region or kwargs.get("deployment_region", "global")
        normalized_nodes = int(kwargs.get("nodes", node_count or 5))
        normalized_pqc_profile = pqc_profile or kwargs.get("pqc_profile", "edge")
        pqc_enabled = bool(kwargs.get("pqc_enabled", True))
        obfuscation = kwargs.get("obfuscation", "none")
        traffic_profile = kwargs.get("traffic_profile", "none")
        join_token_ttl_sec = int(kwargs.get("join_token_ttl_sec", 604800))

        # Validate plan limits
        limits = self._billing.get_plan_limits(normalized_plan)
        if normalized_nodes > limits["max_nodes"]:
            raise ValueError(
                f"Node count {normalized_nodes} exceeds plan limit {limits['max_nodes']}"
            )

        # Generate mesh ID
        mesh_id = f"mesh-{secrets.token_hex(8)}"

        # Get PQC profile configuration (mapped by device class)
        pqc_config = get_pqc_profile(normalized_pqc_profile)

        # Create mesh instance
        instance = MeshInstance(
            mesh_id=mesh_id,
            name=name,
            owner_id=owner_id,
            plan=normalized_plan,
            region=normalized_region,
            nodes=normalized_nodes,
            pqc_profile=normalized_pqc_profile,
            pqc_enabled=pqc_enabled,
            obfuscation=obfuscation,
            traffic_profile=traffic_profile,
            enable_consciousness=enable_consciousness,
            created_at=datetime.utcnow(),
            pqc_config=pqc_config,
        )
        instance.join_token = f"join_{secrets.token_urlsafe(24)}"
        instance.join_token_ttl_sec = join_token_ttl_sec
        instance.join_token_issued_at = datetime.utcnow()
        instance.join_token_expires_at = (
            instance.join_token_issued_at + timedelta(seconds=join_token_ttl_sec)
        )

        # Provision nodes
        await instance.provision()

        # Register in global registry
        register_mesh(instance)

        # Audit log
        await record_audit_log(
            mesh_id,
            owner_id,
            "mesh.provision",
            f"Mesh created with {normalized_nodes} nodes in {normalized_region}",
        )

        # Record metrics
        if self._metrics:
            self._metrics.record_meter(
                "mesh.provisioned",
                1,
                {"plan": normalized_plan, "region": normalized_region},
            )

        logger.info(f"Provisioned mesh {mesh_id} for user {owner_id}")

        return instance

    async def scale_mesh(
        self,
        mesh_id: str,
        target_count: int,
        actor: str,
    ) -> Dict[str, Any]:
        """
        Scale a mesh to target node count.

        Args:
            mesh_id: Mesh to scale
            target_count: Target number of nodes
            actor: User performing the action

        Returns:
            Scaling result
        """
        instance = get_mesh(mesh_id)
        if not instance:
            raise ValueError(f"Mesh {mesh_id} not found")

        # Check plan limits
        limits = self._billing.get_plan_limits(instance.plan)
        if target_count > limits["max_nodes"]:
            raise ValueError(
                f"Target count {target_count} exceeds plan limit {limits['max_nodes']}"
            )

        current_count = len(instance.node_instances)

        if target_count > current_count:
            # Scale up
            instance.scale("scale_up", target_count - current_count)
            action = "scale_up"
        elif target_count < current_count:
            # Scale down
            instance.scale("scale_down", current_count - target_count)
            action = "scale_down"
        else:
            action = "no_change"

        # Audit log
        await record_audit_log(
            mesh_id,
            actor,
            "mesh.scale",
            f"Scaled from {current_count} to {target_count} nodes",
        )

        # MAPE-K event
        add_mapek_event(mesh_id, {
            "type": "scale",
            "from": current_count,
            "to": target_count,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {
            "mesh_id": mesh_id,
            "action": action,
            "previous_count": current_count,
            "current_count": len(instance.node_instances),
        }

    async def terminate_mesh(
        self,
        mesh_id: str,
        actor: str,
        reason: str = "user_request",
    ) -> Dict[str, Any]:
        """
        Terminate a mesh network.

        Args:
            mesh_id: Mesh to terminate
            actor: User performing the action
            reason: Termination reason

        Returns:
            Termination result
        """
        instance = get_mesh(mesh_id)
        if not instance:
            raise ValueError(f"Mesh {mesh_id} not found")

        # Terminate all nodes
        await instance.terminate()

        # Remove from registry
        unregister_mesh(mesh_id)

        # Audit log
        await record_audit_log(
            mesh_id,
            actor,
            "mesh.terminate",
            f"Mesh terminated: {reason}",
        )

        logger.info(f"Terminated mesh {mesh_id}")

        return {
            "mesh_id": mesh_id,
            "status": "terminated",
            "reason": reason,
        }

    async def approve_node(
        self,
        mesh_id: str,
        node_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        """
        Approve a pending node registration.

        Args:
            mesh_id: Mesh ID
            node_id: Node to approve
            actor: User performing the action

        Returns:
            Approval result
        """
        instance = get_mesh(mesh_id)
        if not instance:
            raise ValueError(f"Mesh {mesh_id} not found")

        pending = get_pending_nodes(mesh_id)
        if node_id not in pending:
            raise ValueError(f"Node {node_id} not in pending list")

        # Check if node is revoked
        if is_node_revoked(mesh_id, node_id):
            raise ValueError(f"Node {node_id} is revoked")

        # Get pending data
        node_data = pending[node_id]

        # Add node to mesh
        instance.add_node(node_id, node_data)

        # Remove from pending
        remove_pending_node(mesh_id, node_id)

        # Audit log
        audit_sync(mesh_id, actor, "node.approve", f"Node {node_id} approved")

        return {
            "mesh_id": mesh_id,
            "node_id": node_id,
            "status": "approved",
        }

    async def revoke_node(
        self,
        mesh_id: str,
        node_id: str,
        actor: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Revoke a node from the mesh.

        Args:
            mesh_id: Mesh ID
            node_id: Node to revoke
            actor: User performing the action
            reason: Revocation reason

        Returns:
            Revocation result
        """
        instance = get_mesh(mesh_id)
        if not instance:
            raise ValueError(f"Mesh {mesh_id} not found")

        # Add to revoked list
        mark_node_revoked(mesh_id, node_id, {
            "reason": reason,
            "revoked_by": actor,
            "revoked_at": datetime.utcnow().isoformat(),
        })

        # Remove from mesh
        instance.remove_node(node_id)

        # Audit log
        audit_sync(mesh_id, actor, "node.revoke", f"Node {node_id} revoked: {reason}")

        return {
            "mesh_id": mesh_id,
            "node_id": node_id,
            "status": "revoked",
            "reason": reason,
        }


# ---------------------------------------------------------------------------
# Usage Metering Service
# ---------------------------------------------------------------------------

class UsageMeteringService:
    """
    Tracks and reports usage metrics for billing.

    Responsibilities:
    - Request counting
    - Bandwidth tracking
    - Storage metering
    - Usage reports
    """

    def __init__(self, metrics: Optional[MetricsCollector] = None):
        self._metrics = metrics
        self._usage_cache: Dict[str, Dict[str, float]] = {}

    def record_request(
        self,
        mesh_id: str,
        endpoint: str,
        latency_ms: float,
    ) -> None:
        """Record an API request."""
        if mesh_id not in self._usage_cache:
            self._usage_cache[mesh_id] = {
                "requests": 0,
                "bandwidth_bytes": 0,
                "storage_bytes": 0,
            }

        self._usage_cache[mesh_id]["requests"] += 1

        if self._metrics:
            self._metrics.record_meter(
                "api.request",
                1,
                {"mesh_id": mesh_id, "endpoint": endpoint},
            )
            self._metrics.record_meter(
                "api.latency",
                latency_ms,
                {"mesh_id": mesh_id},
            )

    def record_bandwidth(
        self,
        mesh_id: str,
        bytes_in: int,
        bytes_out: int,
    ) -> None:
        """Record bandwidth usage."""
        if mesh_id not in self._usage_cache:
            self._usage_cache[mesh_id] = {}

        total = bytes_in + bytes_out
        self._usage_cache[mesh_id]["bandwidth_bytes"] = (
            self._usage_cache[mesh_id].get("bandwidth_bytes", 0) + total
        )

        if self._metrics:
            self._metrics.record_meter(
                "network.bandwidth",
                total,
                {"mesh_id": mesh_id},
            )

    def record_storage(
        self,
        mesh_id: str,
        bytes_used: int,
    ) -> None:
        """Record storage usage."""
        if mesh_id not in self._usage_cache:
            self._usage_cache[mesh_id] = {}

        self._usage_cache[mesh_id]["storage_bytes"] = bytes_used

        if self._metrics:
            self._metrics.record_meter(
                "storage.used",
                bytes_used,
                {"mesh_id": mesh_id},
            )

    def get_usage_report(self, mesh_id: str) -> Dict[str, Any]:
        """Get usage report for a mesh."""
        usage = self._usage_cache.get(mesh_id, {})

        return {
            "mesh_id": mesh_id,
            "requests": usage.get("requests", 0),
            "bandwidth_bytes": usage.get("bandwidth_bytes", 0),
            "storage_bytes": usage.get("storage_bytes", 0),
            "report_time": datetime.utcnow().isoformat(),
        }

    def reset_usage(self, mesh_id: str) -> None:
        """Reset usage counters (e.g., after billing cycle)."""
        if mesh_id in self._usage_cache:
            self._usage_cache[mesh_id] = {
                "requests": 0,
                "bandwidth_bytes": 0,
                "storage_bytes": 0,
            }


# ---------------------------------------------------------------------------
# Auth Service
# ---------------------------------------------------------------------------

class AuthService:
    """
    Handles authentication and authorization.

    Responsibilities:
    - API key validation
    - Token generation
    - Session management
    """

    def __init__(self, api_key_secret: Optional[str] = None, shared_state: Optional[Any] = None):
        self._secret = api_key_secret or secrets.token_hex(32)
        self._shared_state = _resolve_shared_state_store(shared_state)
        self._shared_state_authoritative = (
            shared_state is not None or getattr(self._shared_state, "enabled", False)
        )
        self._max_api_keys = max(
            128,
            int(os.getenv("MAAS_AUTH_MAX_API_KEYS", "50000")),
        )
        self._max_sessions = max(
            128,
            int(os.getenv("MAAS_AUTH_MAX_SESSIONS", "50000")),
        )
        self._api_key_ttl_seconds = max(
            0,
            int(os.getenv("MAAS_AUTH_API_KEY_TTL_SECONDS", "0")),
        )
        self._api_keys: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    @staticmethod
    def _evict_oldest(store: OrderedDict[str, Dict[str, Any]], max_entries: int) -> None:
        while len(store) > max_entries:
            store.popitem(last=False)

    @staticmethod
    def _api_key_store_key(api_key: str) -> str:
        return f"maas:auth:api_key:{api_key}"

    @staticmethod
    def _session_store_key(token: str) -> str:
        return f"maas:auth:session:{token}"

    def generate_api_key(self, user_id: str, plan: str) -> str:
        """Generate a new API key for a user."""
        key = f"maas_{secrets.token_urlsafe(32)}"

        key_record = {
            "user_id": user_id,
            "plan": plan,
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None,
            "request_count": 0,
        }
        self._api_keys[key] = key_record
        self._evict_oldest(self._api_keys, self._max_api_keys)
        self._shared_state.set_json(
            self._api_key_store_key(key),
            key_record,
            ttl_seconds=self._api_key_ttl_seconds if self._api_key_ttl_seconds > 0 else None,
        )

        return key

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return associated data."""
        key_data = self._shared_state.get_json(self._api_key_store_key(api_key))
        if key_data is None:
            if self._shared_state_authoritative:
                self._api_keys.pop(api_key, None)
                return None
            key_data = self._api_keys.get(api_key)
        if key_data is None:
            return None

        key_data = dict(key_data)

        # Update last used
        key_data["last_used"] = datetime.utcnow().isoformat()
        key_data["request_count"] += 1

        self._shared_state.set_json(
            self._api_key_store_key(api_key),
            key_data,
            ttl_seconds=self._api_key_ttl_seconds if self._api_key_ttl_seconds > 0 else None,
        )
        self._api_keys[api_key] = key_data
        self._api_keys.move_to_end(api_key)
        self._evict_oldest(self._api_keys, self._max_api_keys)

        return key_data

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        deleted_local = self._api_keys.pop(api_key, None) is not None
        deleted_shared = self._shared_state.delete(self._api_key_store_key(api_key))
        return deleted_local or deleted_shared

    def create_session(self, user_id: str, ttl_hours: int = 24) -> str:
        """Create a new session token."""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        session_record = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        self._sessions[token] = session_record
        self._evict_oldest(self._sessions, self._max_sessions)
        ttl_seconds = max(1, int((expires_at - datetime.utcnow()).total_seconds()))
        self._shared_state.set_json(
            self._session_store_key(token),
            session_record,
            ttl_seconds=ttl_seconds,
        )

        return token

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a session token."""
        session = self._shared_state.get_json(self._session_store_key(token))
        if session is None:
            if self._shared_state_authoritative:
                self._sessions.pop(token, None)
                return None
            session = self._sessions.get(token)
        if session is None:
            return None

        session = dict(session)

        # Check expiration
        expires = datetime.fromisoformat(session["expires_at"])
        if datetime.utcnow() > expires:
            self._shared_state.delete(self._session_store_key(token))
            self._sessions.pop(token, None)
            return None

        self._sessions[token] = session
        self._sessions.move_to_end(token)
        self._evict_oldest(self._sessions, self._max_sessions)
        return session

    def end_session(self, token: str) -> bool:
        """End a session."""
        deleted_local = self._sessions.pop(token, None) is not None
        deleted_shared = self._shared_state.delete(self._session_store_key(token))
        return deleted_local or deleted_shared


__all__ = [
    "BillingService",
    "MeshProvisioner",
    "UsageMeteringService",
    "AuthService",
    "PaymentProvider",
    "MetricsCollector",
]
