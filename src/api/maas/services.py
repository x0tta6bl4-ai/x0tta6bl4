"""
MaaS Services - Business logic services.

Contains service classes for billing, mesh provisioning, usage metering, and auth.
"""

import hashlib
import hmac
import logging
import secrets
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Protocol

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
    ):
        self._provider = payment_provider
        self._webhook_secret = webhook_secret or secrets.token_hex(32)
        self._idempotency_cache: Dict[str, Dict] = {}
        # Legacy/alternate event names normalized to canonical provider-style names.
        self._event_aliases: Dict[str, str] = {
            "plan.upgraded": "customer.subscription.updated",
            "plan.downgraded": "customer.subscription.updated",
            "subscription.created": "customer.subscription.created",
            "subscription.updated": "customer.subscription.updated",
            "subscription.canceled": "customer.subscription.deleted",
            "subscription.deleted": "customer.subscription.deleted",
        }

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
        if timestamp:
            # Replay protection: reject if timestamp is too old
            try:
                ts = int(timestamp)
                if abs(int(time.time()) - ts) > 300:  # 5 minutes (past or future)
                    logger.warning("Webhook timestamp outside allowed skew")
                    return False
            except ValueError:
                return False

            message = f"{timestamp}.".encode("utf-8") + payload
        else:
            message = payload

        expected = hmac.new(
            self._webhook_secret.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()

        signature = signature.strip()
        if signature.startswith("sha256="):
            return hmac.compare_digest(f"sha256={expected}", signature)
        return hmac.compare_digest(expected, signature)

    def _normalize_event_type(self, event_type: str) -> str:
        """Normalize webhook event type to canonical provider-style name."""
        normalized = (event_type or "").strip().lower()
        return self._event_aliases.get(normalized, normalized)

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
        if event_id in self._idempotency_cache:
            logger.info(f"Webhook event {event_id} already processed")
            return self._idempotency_cache[event_id]

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
        self._idempotency_cache[event_id] = result

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

    def __init__(self, api_key_secret: Optional[str] = None):
        self._secret = api_key_secret or secrets.token_hex(32)
        self._api_keys: Dict[str, Dict[str, Any]] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def generate_api_key(self, user_id: str, plan: str) -> str:
        """Generate a new API key for a user."""
        key = f"maas_{secrets.token_urlsafe(32)}"

        self._api_keys[key] = {
            "user_id": user_id,
            "plan": plan,
            "created_at": datetime.utcnow().isoformat(),
            "last_used": None,
            "request_count": 0,
        }

        return key

    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return associated data."""
        if api_key not in self._api_keys:
            return None

        key_data = self._api_keys[api_key]

        # Update last used
        key_data["last_used"] = datetime.utcnow().isoformat()
        key_data["request_count"] += 1

        return key_data

    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key."""
        if api_key in self._api_keys:
            del self._api_keys[api_key]
            return True
        return False

    def create_session(self, user_id: str, ttl_hours: int = 24) -> str:
        """Create a new session token."""
        token = secrets.token_urlsafe(32)

        self._sessions[token] = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(hours=ttl_hours)
            ).isoformat(),
        }

        return token

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a session token."""
        if token not in self._sessions:
            return None

        session = self._sessions[token]

        # Check expiration
        expires = datetime.fromisoformat(session["expires_at"])
        if datetime.utcnow() > expires:
            del self._sessions[token]
            return None

        return session

    def end_session(self, token: str) -> bool:
        """End a session."""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False


__all__ = [
    "BillingService",
    "MeshProvisioner",
    "UsageMeteringService",
    "AuthService",
    "PaymentProvider",
    "MetricsCollector",
]
