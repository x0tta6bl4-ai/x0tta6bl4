"""
X0T Token Bridge: Off-chain (MeshToken) ↔ On-chain (X0TToken/X0TBridge.sol)

Responsibilities:
1. Listen to on-chain events (Staked, Unstaked, Transfer, RelayPaid, BridgeDeposit)
2. Sync state to local MeshToken
3. Push local rewards/payments to on-chain contract

Architecture:
    ┌─────────────────┐         ┌─────────────────┐
    │   MeshToken     │◄───────►│   X0TToken.sol  │
    │   (Python)      │  Bridge │   (Blockchain)  │
    │   Off-chain     │         │   On-chain      │
    └─────────────────┘         └─────────────────┘
         ▲                              ▲
         │                              │
    Local mesh ops              Exchange/Wallet
    (fast, free)                (permanent, tradeable)
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import AsyncSafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.reward_events import publish_reward_settlement_event
from src.services.service_event_identity import service_event_identity

# Optional web3 import
try:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"websockets\.legacy is deprecated.*",
            category=DeprecationWarning,
            append=False,
        )
        from web3 import Web3

    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None

# Type imports
if TYPE_CHECKING:
    from src.dao.token import MeshToken

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "token-bridge"

TOKEN_BRIDGE_CLAIM_BOUNDARY = (
    "TokenBridge chain-write event only. It records local policy, actuator, "
    "and settlement submission state for X0T bridge operations; it is not "
    "proof of final live external settlement without a verified receipt and "
    "live RPC evidence."
)


class BridgeDirection(Enum):
    """Direction of token bridge operation."""

    TO_CHAIN = "to_chain"  # Python → Blockchain
    FROM_CHAIN = "from_chain"  # Blockchain → Python


@dataclass
class BridgeTransaction:
    """Record of a bridge transaction."""

    tx_id: str
    direction: BridgeDirection
    from_address: str
    to_address: str
    amount: float
    event_type: str
    timestamp: float
    block_number: Optional[int] = None
    tx_hash: Optional[str] = None
    status: str = "pending"  # pending, confirmed, failed


@dataclass
class BridgeConfig:
    """Configuration for token bridge."""

    rpc_urls: List[str] = field(default_factory=list) # P0 Q2: Multiple RPC support
    rpc_url: str = "" # Keep for backward compatibility
    contract_address: str = ""
    private_key: str = ""
    chain_id: int = 84532  # Base Sepolia (testnet default)
    poll_interval: int = 12  # seconds (1 block on Base)
    confirmations: int = 2
    gas_limit: int = 200000
    max_gas_price_gwei: float = 50.0
    allow_simulated_chain_writes: bool = False


class TokenBridge:
    """
    Bridge between off-chain MeshToken and on-chain X0TToken/X0TBridge.

    Usage:
        from src.dao.token import MeshToken
        from src.dao.token_bridge import TokenBridge, BridgeConfig

        token = MeshToken()
        config = BridgeConfig(
            rpc_url="https://sepolia.base.org",
            contract_address="0x...",
            private_key="..."
        )
        bridge = TokenBridge(token, config)

        # Start listening to on-chain events
        await bridge.start()

        # Push local rewards to chain
        await bridge.push_rewards_to_chain({"node1": 100.0, "node2": 50.0})
    """

    POLLED_EVENT_TYPES = (
        "Staked",
        "Unstaked",
        "Transfer",
        "RelayPaid",
        "BridgeDeposit",
        "BridgeRelease",
    )

    # X0TToken/X0TBridge ABI (minimal, only what we need)
    CONTRACT_ABI = [
        # Events
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "user", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"},
                {"indexed": False, "name": "totalStaked", "type": "uint256"},
            ],
            "name": "Staked",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "user", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"},
                {"indexed": False, "name": "totalStaked", "type": "uint256"},
            ],
            "name": "Unstaked",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "from", "type": "address"},
                {"indexed": True, "name": "to", "type": "address"},
                {"indexed": False, "name": "value", "type": "uint256"},
            ],
            "name": "Transfer",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "payer", "type": "address"},
                {"indexed": True, "name": "relayer", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"},
                {"indexed": False, "name": "feeBurned", "type": "uint256"},
            ],
            "name": "RelayPaid",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "epoch", "type": "uint256"},
                {"indexed": False, "name": "totalRewards", "type": "uint256"},
                {"indexed": False, "name": "recipientCount", "type": "uint256"},
            ],
            "name": "EpochRewardsDistributed",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "escrowId", "type": "bytes32"},
                {"indexed": True, "name": "payer", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"},
            ],
            "name": "EscrowCreated",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "escrowId", "type": "bytes32"},
                {"indexed": True, "name": "recipient", "type": "address"},
            ],
            "name": "EscrowReleased",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "depositId", "type": "bytes32"},
                {"indexed": True, "name": "depositor", "type": "address"},
                {"indexed": True, "name": "recipient", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"},
                {"indexed": False, "name": "nodeIdHash", "type": "bytes32"},
                {"indexed": False, "name": "meshNodeId", "type": "string"},
            ],
            "name": "BridgeDeposit",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "releaseId", "type": "bytes32"},
                {"indexed": True, "name": "recipient", "type": "address"},
                {"indexed": False, "name": "amount", "type": "uint256"},
            ],
            "name": "BridgeRelease",
            "type": "event",
        },
        # Read functions
        {
            "inputs": [{"name": "account", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [{"name": "user", "type": "address"}],
            "name": "votingPower",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "totalStaked",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "currentEpoch",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "inputs": [],
            "name": "canDistributeRewards",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "view",
            "type": "function",
        },
        # Write functions
        {
            "inputs": [
                {"name": "recipients", "type": "address[]"},
                {"name": "uptimes", "type": "uint256[]"},
            ],
            "name": "distributeEpochRewards",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"name": "relayer", "type": "address"},
                {"name": "authorized", "type": "bool"},
            ],
            "name": "setRelayerAuthorized",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"name": "recipient", "type": "address"},
                {"name": "meshNodeId", "type": "string"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "depositFor",
            "outputs": [{"name": "depositId", "type": "bytes32"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "inputs": [
                {"name": "releaseId", "type": "bytes32"},
                {"name": "recipient", "type": "address"},
                {"name": "amount", "type": "uint256"},
            ],
            "name": "releaseToChain",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]

    def __init__(
        self,
        mesh_token: "MeshToken",
        config: BridgeConfig,
        *,
        node_id: str = "token-bridge",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[AsyncSafeActuator] = None,
    ):
        """
        Initialize token bridge with resilience patterns.

        Args:
            mesh_token: Local MeshToken instance
            config: Bridge configuration
        """
        self.mesh_token = mesh_token
        self.config = config
        self.node_id = node_id
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_TOKEN_BRIDGE_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="token-bridge")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id if spiffe_id is not None else service_identity["spiffe_id"],
            "did": did if did is not None else service_identity["did"],
            "wallet_address": (
                wallet_address
                if wallet_address is not None
                else service_identity["wallet_address"]
            ),
        }
        self.safe_actuator = safe_actuator or AsyncSafeActuator(
            self._execute_chain_write_through_actuator
        )
        self._last_chain_write_result: Any = None
        self.web3 = None
        self.contract = None
        self.account = None

        self._running = False
        self._last_block = 0
        self._tx_history: List[BridgeTransaction] = []
        self._address_mapping: Dict[str, str] = {}  # node_id → eth_address

        # Resilience: Circuit Breaker for RPC calls
        from src.resilience.advanced_patterns import CircuitBreaker, CircuitBreakerConfig
        self.rpc_breaker = CircuitBreaker(
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout_seconds=60
            ),
            name="blockchain_rpc_breaker"
        )

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "Staked": [],
            "Unstaked": [],
            "Transfer": [],
            "RelayPaid": [],
            "EpochRewardsDistributed": [],
            "BridgeDeposit": [],
            "BridgeRelease": [],
        }

        self._initialized = False

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except Exception as exc:
            logger.error("Failed to initialize TokenBridge EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize TokenBridge policy engine: %s", exc)
            return None

    @staticmethod
    def _policy_allowed(decision: Any) -> bool:
        return normalize_policy_allowed(decision)

    @staticmethod
    def _policy_reason(decision: Any) -> str:
        return normalize_policy_reason(decision)

    @staticmethod
    def _policy_rules(decision: Any) -> list[str]:
        return normalize_policy_rules(decision)

    @classmethod
    def _safe_value(cls, key: str, value: Any, depth: int = 0) -> Any:
        blocked_fragments = ("secret", "password", "token", "key", "private")
        if any(fragment in str(key).lower() for fragment in blocked_fragments):
            return "<redacted>"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict) and depth < 3:
            return {
                str(child_key): cls._safe_value(str(child_key), child_value, depth + 1)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list) and depth < 3:
            return [cls._safe_value(key, item, depth + 1) for item in value]
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    @staticmethod
    def _chain_resource_name(operation: str) -> str:
        operation_lower = str(operation or "unknown_operation").lower().strip()
        slug = "".join(
            char if char.isalnum() else "_"
            for char in operation_lower
        ).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "unknown_operation"

    def _publish_chain_write_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        operation: str,
        context: Dict[str, Any],
        reason: str = "",
        policy_decision: Any = None,
        success: Optional[bool] = None,
        transaction_hash: Optional[str] = None,
        simulated: Optional[bool] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        operation_resource = self._chain_resource_name(operation)
        payload = {
            "component": "dao.token_bridge",
            "stage": stage,
            "operation": operation,
            "operation_resource": operation_resource,
            "resource": f"dao:token_bridge:{operation_resource}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "success": success,
            "transaction_hash": transaction_hash,
            "simulated": simulated,
            "submitted_transaction": bool(transaction_hash and not simulated),
            "reason": reason,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": self._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "safe_actuator": True,
            "claim_boundary": TOKEN_BRIDGE_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=8)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish TokenBridge chain-write event: %s", exc)
            return None

    def _evaluate_chain_write_policy(self, operation: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "TokenBridge policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "TokenBridge SPIFFE identity is required for policy evaluation"
        operation_resource = self._chain_resource_name(operation)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"dao:token_bridge:{operation_resource}",
                workload_type="token-bridge",
            )
        except Exception as exc:
            return False, None, f"TokenBridge policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "TokenBridge policy denied chain write"
        return True, decision, self._policy_reason(decision)

    @staticmethod
    def _chain_write_succeeded(operation: str, raw: Any) -> bool:
        if operation in {"release_escrow_on_chain", "refund_escrow_on_chain"}:
            return raw is True
        return raw is not None

    @staticmethod
    def _chain_write_tx_hash(raw: Any) -> Optional[str]:
        if isinstance(raw, str):
            return raw
        return None

    @staticmethod
    def _chain_write_simulated(operation: str, raw: Any) -> bool:
        if operation == "lock_escrow_on_chain" and isinstance(raw, str) and raw.startswith("sim_tx_"):
            return True
        if operation in {"release_escrow_on_chain", "refund_escrow_on_chain"} and raw is True:
            return True
        return False

    def _publish_reward_lifecycle(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        success: bool,
        simulated: bool,
        transaction_hash: Optional[str],
        reason: str,
    ) -> None:
        if operation != "push_rewards_to_chain":
            return
        rewards = context.get("rewards") if isinstance(context.get("rewards"), dict) else {}
        amount = sum(float(value) for value in rewards.values()) if rewards else None
        publish_reward_settlement_event(
            transition="recorded" if success and not simulated else "blocked",
            source_agent=self.source_agent,
            node_address=self.identity.get("wallet_address") or self.identity.get("node_id"),
            packets=None,
            amount=amount,
            status="submitted" if success and not simulated else "blocked",
            submitted_transaction=bool(transaction_hash and not simulated),
            simulated=simulated,
            settlement_recorded=bool(success and not simulated and transaction_hash),
            local_accounting_recorded=False,
            transaction_hash=transaction_hash if not simulated else None,
            reason=reason,
            event_bus=self.event_bus,
            project_root=self.event_project_root,
            **self.identity,
        )

    def _publish_marketplace_lifecycle(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        success: bool,
        simulated: bool,
        reason: str,
    ) -> None:
        transitions = {
            "lock_escrow_on_chain": "held",
            "release_escrow_on_chain": "released",
            "refund_escrow_on_chain": "refunded",
        }
        if operation not in transitions:
            return
        publish_marketplace_escrow_event(
            transition=transitions[operation] if success and not simulated else "blocked",
            source_agent=self.source_agent,
            escrow_id=context.get("escrow_id"),
            listing_id=context.get("listing_id"),
            renter_id=context.get("renter_id"),
            actor_id=self.identity.get("node_id"),
            currency="X0T",
            status=transitions[operation] if success and not simulated else "blocked",
            node_id=context.get("target_node_id") or self.identity.get("node_id"),
            mesh_id=context.get("mesh_id"),
            amount_token=context.get("amount_xot"),
            reason=reason,
            event_bus=self.event_bus,
            project_root=self.event_project_root,
            spiffe_id=self.identity.get("spiffe_id"),
            did=self.identity.get("did"),
            wallet_address=self.identity.get("wallet_address"),
        )

    async def _execute_chain_write_through_actuator(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        self._last_chain_write_result = None
        if operation == "lock_escrow_on_chain":
            raw = await self._lock_escrow_on_chain_internal(
                str(context.get("escrow_id", "")),
                str(context.get("target_node_id", "")),
                float(context.get("amount_xot") or 0.0),
            )
        elif operation == "release_escrow_on_chain":
            raw = await self._release_escrow_on_chain_internal(str(context.get("escrow_id", "")))
        elif operation == "refund_escrow_on_chain":
            raw = await self._refund_escrow_on_chain_internal(str(context.get("escrow_id", "")))
        elif operation == "push_rewards_to_chain":
            rewards = context.get("rewards")
            uptimes = context.get("uptimes")
            raw = await self._push_rewards_to_chain_internal(
                rewards if isinstance(rewards, dict) else {},
                uptimes if isinstance(uptimes, dict) or uptimes is None else None,
            )
        elif operation == "authorize_relayer":
            raw = await self._authorize_relayer_internal(
                str(context.get("target_node_id", "")),
                bool(context.get("authorized", True)),
            )
        else:
            return SafeActuatorResult(False, f"unknown TokenBridge operation: {operation}")

        self._last_chain_write_result = raw
        success = self._chain_write_succeeded(operation, raw)
        simulated = self.config.allow_simulated_chain_writes and self._chain_write_simulated(operation, raw)
        if simulated:
            return SafeActuatorResult(success, "simulated chain write is not production settlement", True)
        return SafeActuatorResult(success, "" if success else f"{operation} returned no settlement result")

    async def _run_chain_write(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        failure_value: Any = None,
    ) -> Any:
        self._last_chain_write_result = None
        self._publish_chain_write_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            operation=operation,
            context=context,
        )
        policy_allowed, policy_decision, policy_reason = self._evaluate_chain_write_policy(operation)
        if not policy_allowed:
            self._publish_chain_write_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                operation=operation,
                context=context,
                reason=policy_reason,
                policy_decision=policy_decision,
                success=False,
                simulated=False,
            )
            self._publish_reward_lifecycle(
                operation=operation,
                context=context,
                success=False,
                simulated=False,
                transaction_hash=None,
                reason=policy_reason,
            )
            self._publish_marketplace_lifecycle(
                operation=operation,
                context=context,
                success=False,
                simulated=False,
                reason=policy_reason,
            )
            return failure_value

        self._publish_chain_write_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )
        actuator_result = await self.safe_actuator.execute(operation, context)
        raw = self._last_chain_write_result
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        transaction_hash = self._chain_write_tx_hash(raw)
        reason = actuator_result.reason or policy_reason
        event_type = EventType.PIPELINE_STAGE_END if success and not simulated else EventType.TASK_FAILED
        stage = (
            "actuator_completed"
            if success and not simulated
            else "actuator_simulated"
            if simulated
            else "actuator_failed"
        )
        self._publish_chain_write_event(
            event_type,
            stage=stage,
            operation=operation,
            context=context,
            reason=reason,
            policy_decision=policy_decision,
            success=success and not simulated,
            transaction_hash=transaction_hash if not simulated else None,
            simulated=simulated,
        )
        self._publish_reward_lifecycle(
            operation=operation,
            context=context,
            success=success,
            simulated=simulated,
            transaction_hash=transaction_hash,
            reason=reason,
        )
        self._publish_marketplace_lifecycle(
            operation=operation,
            context=context,
            success=success,
            simulated=simulated,
            reason=reason,
        )
        if raw is not None and simulated and operation in {
            "lock_escrow_on_chain",
            "release_escrow_on_chain",
            "refund_escrow_on_chain",
        }:
            return raw
        return raw if success and not simulated else failure_value

    def _init_web3(self):
        """Initialize Web3 with failover support across multiple RPC providers."""
        if self._initialized and self.web3 and self.web3.is_connected():
            return True

        try:
            from eth_account import Account
            from web3 import Web3
        except (ImportError, Exception) as e:
            logger.error(f"web3/eth_account not available: {e}")
            return False

        # Combine single rpc_url and list of rpc_urls
        all_urls = self.config.rpc_urls.copy()
        if self.config.rpc_url and self.config.rpc_url not in all_urls:
            all_urls.insert(0, self.config.rpc_url)

        if not all_urls:
            logger.error("No RPC URLs configured for TokenBridge")
            return False

        for url in all_urls:
            try:
                logger.info(f"Connecting to RPC: {url}")
                instance = Web3(Web3.HTTPProvider(url))
                if instance.is_connected():
                    self.web3 = instance
                    
                    if self.config.private_key:
                        self.account = Account.from_key(self.config.private_key)
                        logger.info(f"Bridge account: {self.account.address}")

                    if self.config.contract_address:
                        self.contract = self.web3.eth.contract(
                            address=Web3.to_checksum_address(self.config.contract_address),
                            abi=self.CONTRACT_ABI,
                        )
                        logger.info(f"Contract loaded: {self.config.contract_address}")

                    self._initialized = True
                    logger.info(f"✅ TokenBridge connected to {url}")
                    return True
            except Exception as e:
                logger.warning(f"⚠️ Failed to connect to {url}: {e}")

        logger.error("❌ All RPC providers failed")
        return False

    # ─────────────────────────────────────────────────────────────
    # Address Mapping (node_id ↔ eth_address)
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_address(eth_address: Any) -> str:
        """Normalize addresses for stable matching in both real and mocked Web3."""
        address = str(eth_address).strip()
        if not address.startswith(("0x", "0X")):
            address = f"0x{address}"
        return address.lower()

    @staticmethod
    def _checksum_address_or_none(eth_address: str) -> Optional[str]:
        """Return checksum address only when Web3 conversion returns a valid string."""
        if not WEB3_AVAILABLE:
            return None
        try:
            converted = Web3.to_checksum_address(eth_address)
        except Exception:
            return None
        if isinstance(converted, str) and converted.startswith("0x"):
            return converted
        return None

    def register_address(self, node_id: str, eth_address: str):
        """
        Register mapping between mesh node_id and Ethereum address.

        Args:
            node_id: Mesh network node identifier
            eth_address: Ethereum address (0x...)
        """
        normalized = str(eth_address).strip()
        if not normalized.startswith(("0x", "0X")):
            normalized = f"0x{normalized}"
        self._address_mapping[node_id] = (
            self._checksum_address_or_none(normalized) or normalized
        )
        logger.info(f"Registered: {node_id} → {self._address_mapping[node_id]}")

    def get_eth_address(self, node_id: str) -> Optional[str]:
        """Get Ethereum address for node_id."""
        return self._address_mapping.get(node_id)

    def get_node_id(self, eth_address: str) -> Optional[str]:
        """Get node_id for Ethereum address."""
        eth_address_lower = self._normalize_address(eth_address)
        for node_id, addr in self._address_mapping.items():
            if self._normalize_address(addr) == eth_address_lower:
                return node_id
        return None

    # ─────────────────────────────────────────────────────────────
    # Event Listening (Chain → Python)
    # ─────────────────────────────────────────────────────────────

    def on_event(self, event_name: str, handler: Callable):
        """Register handler for on-chain event."""
        if event_name in self._event_handlers:
            self._event_handlers[event_name].append(handler)

    @staticmethod
    def _event_arg(args: Any, key: str, default: Any = None) -> Any:
        if hasattr(args, "get"):
            return args.get(key, default)
        try:
            return getattr(args, key)
        except AttributeError:
            return default

    async def start(self):
        """Start listening to on-chain events."""
        if not self._init_web3():
            logger.error("Cannot start bridge: Web3 not initialized")
            return

        self._running = True
        self._last_block = self.web3.eth.block_number
        logger.info(f"Bridge started at block {self._last_block}")

        while self._running:
            try:
                await self._poll_events()
            except Exception as e:
                logger.error(f"Event polling error: {e}")

            await asyncio.sleep(self.config.poll_interval)

    def stop(self):
        """Stop event listening."""
        self._running = False
        logger.info("Bridge stopped")

    async def _poll_events(self):
        """Poll for new events since last block."""
        current_block = self.web3.eth.block_number

        confirmations = max(int(self.config.confirmations or 0), 0)
        confirmed_to_block = current_block - confirmations
        if confirmed_to_block <= self._last_block:
            return

        # Get events from last_block to current
        from_block = self._last_block + 1
        to_block = confirmed_to_block

        for event_name in self.POLLED_EVENT_TYPES:
            await self._process_event_type(event_name, from_block, to_block)

        self._last_block = confirmed_to_block

    async def _process_event_type(
        self, event_name: str, from_block: int, to_block: int
    ):
        """Process events of a specific type."""
        if not self.contract:
            return

        try:
            event_filter = getattr(self.contract.events, event_name)
            events = event_filter.get_logs(fromBlock=from_block, toBlock=to_block)

            for event in events:
                await self._handle_event(event_name, event)

        except Exception as e:
            logger.error(f"Error processing {event_name} events: {e}")

    async def _handle_event(self, event_name: str, event: Any):
        """Handle a single on-chain event."""
        args = event.args
        block = event.blockNumber
        tx_hash = event.transactionHash.hex()
        bridge_deposit_recorded = False

        logger.info(f"Event {event_name} at block {block}: {dict(args)}")

        # Sync to local MeshToken
        if event_name == "Staked":
            await self._sync_stake(args.user, args.amount, is_stake=True)
        elif event_name == "Unstaked":
            await self._sync_stake(args.user, args.amount, is_stake=False)
        elif event_name == "Transfer":
            await self._sync_transfer(args["from"], args.to, args.value)
        elif event_name == "RelayPaid":
            await self._sync_relay_payment(args.payer, args.relayer, args.amount)
        elif event_name == "BridgeDeposit":
            bridge_deposit_recorded = True
            await self.mint_from_bridge_event(
                tx_hash=tx_hash,
                recipient_address=str(self._event_arg(args, "recipient", "")),
                amount_wei=int(self._event_arg(args, "amount", 0) or 0),
                block_number=block,
            )

        # Call registered handlers
        for handler in self._event_handlers.get(event_name, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        if bridge_deposit_recorded:
            return

        if event_name == "BridgeRelease":
            from_address = "bridge"
            to_address = str(self._event_arg(args, "recipient", ""))
        else:
            from_address = str(
                self._event_arg(
                    args,
                    "from",
                    self._event_arg(args, "user", self._event_arg(args, "payer", "")),
                )
            )
            to_address = str(
                self._event_arg(
                    args,
                    "to",
                    self._event_arg(args, "relayer", self._event_arg(args, "recipient", "")),
                )
            )

        # Record transaction
        self._tx_history.append(
            BridgeTransaction(
                tx_id=f"{event_name}_{tx_hash[:8]}",
                direction=BridgeDirection.FROM_CHAIN,
                from_address=from_address,
                to_address=to_address,
                amount=(
                    float(self._event_arg(args, "amount", self._event_arg(args, "value", 0)))
                    / 1e18
                ),
                event_type=event_name,
                timestamp=time.time(),
                block_number=block,
                tx_hash=tx_hash,
                status="confirmed",
            )
        )

    async def _sync_stake(self, eth_address: str, amount_wei: int, is_stake: bool):
        """Sync stake event to local MeshToken."""
        node_id = self.get_node_id(eth_address)
        if not node_id:
            logger.warning(f"Unknown address {eth_address}, skipping stake sync")
            return

        amount = float(amount_wei) / 1e18

        if is_stake:
            # Ensure node has balance, then stake
            current_balance = self.mesh_token.balance_of(node_id)
            if current_balance < amount:
                self.mesh_token.mint(node_id, amount - current_balance, "bridge_sync")
            self.mesh_token.stake(node_id, amount)
            logger.info(f"Synced stake: {node_id} staked {amount} X0T")
        else:
            # Unstake locally
            # Note: lock period is handled on-chain, local unstake is immediate
            self.mesh_token.stakes.pop(node_id, None)
            logger.info(f"Synced unstake: {node_id} unstaked {amount} X0T")

    async def _sync_transfer(self, from_addr: str, to_addr: str, amount_wei: int):
        """Sync transfer event to local MeshToken."""
        from_node = self.get_node_id(from_addr)
        to_node = self.get_node_id(to_addr)
        amount = float(amount_wei) / 1e18

        if from_node and to_node:
            # Both addresses known, sync transfer
            self.mesh_token.transfer(from_node, to_node, amount)
            logger.info(f"Synced transfer: {from_node} → {to_node}: {amount} X0T")
        elif to_node:
            # Incoming from unknown (e.g., exchange deposit)
            self.mesh_token.mint(to_node, amount, "bridge_deposit")
            logger.info(f"Synced deposit: {to_node} received {amount} X0T")

    async def _sync_relay_payment(self, payer: str, relayer: str, amount_wei: int):
        """Sync relay payment to local MeshToken."""
        payer_node = self.get_node_id(payer)
        relayer_node = self.get_node_id(relayer)
        amount = float(amount_wei) / 1e18

        if payer_node and relayer_node:
            logger.info(
                f"Synced relay payment: {payer_node} → {relayer_node}: {amount} X0T"
            )
            # Local state already updated via relay_packet(), just log

    # ─────────────────────────────────────────────────────────────
    # Push to Chain (Python → Chain)
    # ─────────────────────────────────────────────────────────────

    async def lock_escrow_on_chain(
        self, escrow_id: str, node_id: str, amount_xot: float
    ) -> Optional[str]:
        context = {
            "escrow_id": escrow_id,
            "target_node_id": node_id,
            "amount_xot": amount_xot,
        }
        result = await self._run_chain_write(
            operation="lock_escrow_on_chain",
            context=context,
            failure_value=None,
        )
        return result if isinstance(result, str) else None

    async def _lock_escrow_on_chain_internal(
        self, escrow_id: str, node_id: str, amount_xot: float
    ) -> Optional[str]:
        """
        Lock tokens in a decentralized escrow on-chain.
        """
        if not self._init_web3() or not self.contract or not self.account:
            if not self.config.allow_simulated_chain_writes:
                logger.error(
                    "Decentralized escrow %s refused: Web3, bridge contract, or "
                    "operator account is unavailable",
                    escrow_id,
                )
                return None
            logger.warning(
                "Decentralized escrow %s simulated because explicit "
                "allow_simulated_chain_writes=True is set",
                escrow_id,
            )
            return f"sim_tx_{uuid.uuid4().hex[:8]}"

        eth_addr = self.get_eth_address(node_id)
        if not eth_addr:
            logger.error(f"No Ethereum address for {node_id}")
            return None

        logger.error(
            "Decentralized escrow %s refused: real X0TBridge deposit submission "
            "is not implemented for node %s amount %s",
            escrow_id,
            node_id,
            amount_xot,
        )
        return None

    async def release_escrow_on_chain(self, escrow_id: str) -> bool:
        result = await self._run_chain_write(
            operation="release_escrow_on_chain",
            context={"escrow_id": escrow_id},
            failure_value=False,
        )
        return bool(result)

    async def _release_escrow_on_chain_internal(self, escrow_id: str) -> bool:
        """
        Release on-chain escrow to the node operator.
        """
        if not self._init_web3() or not self.contract or not self.account:
            if self.config.allow_simulated_chain_writes:
                logger.warning(
                    "Release for on-chain escrow %s simulated because explicit "
                    "allow_simulated_chain_writes=True is set",
                    escrow_id,
                )
                return True
            logger.error(
                "Release for on-chain escrow %s refused: Web3, bridge contract, "
                "or operator account is unavailable",
                escrow_id,
            )
            return False

        logger.error(
            "Release for on-chain escrow %s refused: real X0TBridge release "
            "submission is not implemented",
            escrow_id,
        )
        return False

    async def refund_escrow_on_chain(self, escrow_id: str) -> bool:
        result = await self._run_chain_write(
            operation="refund_escrow_on_chain",
            context={"escrow_id": escrow_id},
            failure_value=False,
        )
        return bool(result)

    async def _refund_escrow_on_chain_internal(self, escrow_id: str) -> bool:
        """
        Refund on-chain escrow to the renter.
        """
        if not self._init_web3() or not self.contract or not self.account:
            if self.config.allow_simulated_chain_writes:
                logger.warning(
                    "Refund for on-chain escrow %s simulated because explicit "
                    "allow_simulated_chain_writes=True is set",
                    escrow_id,
                )
                return True
            logger.error(
                "Refund for on-chain escrow %s refused: Web3, bridge contract, "
                "or operator account is unavailable",
                escrow_id,
            )
            return False

        logger.error(
            "Refund for on-chain escrow %s refused: real X0TBridge refund "
            "submission is not implemented",
            escrow_id,
        )
        return False

    async def push_rewards_to_chain(
        self, rewards: Dict[str, float], uptimes: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        result = await self._run_chain_write(
            operation="push_rewards_to_chain",
            context={"rewards": dict(rewards), "uptimes": dict(uptimes) if uptimes else None},
            failure_value=None,
        )
        return result if isinstance(result, str) else None

    async def _push_rewards_to_chain_internal(
        self, rewards: Dict[str, float], uptimes: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Push epoch rewards to on-chain contract.

        Args:
            rewards: Dict of node_id → reward amount (for reference)
            uptimes: Dict of node_id → uptime percent (0-100)

        Returns:
            Transaction hash if successful
        """
        if not self._init_web3():
            logger.error("Cannot push rewards: Web3 not initialized")
            return None

        if not self.contract or not self.account:
            logger.error("Contract or account not configured")
            return None

        # Check if epoch is ready
        can_distribute = self.contract.functions.canDistributeRewards().call()
        if not can_distribute:
            logger.warning("Epoch not complete, cannot distribute rewards yet")
            return None

        # Convert node_ids to addresses
        recipients = []
        uptime_values = []

        for node_id in rewards.keys():
            eth_addr = self.get_eth_address(node_id)
            if eth_addr:
                recipients.append(eth_addr)
                uptime_values.append(uptimes.get(node_id, 100) if uptimes else 100)

        if not recipients:
            logger.warning("No valid recipients for rewards")
            return None

        try:
            # P0 Q2: Dynamic Gas Estimation (EIP-1559) for Mainnet
            latest_block = self.web3.eth.get_block("latest")
            base_fee = latest_block.get("baseFeePerGas", self.web3.to_wei(1, "gwei"))
            
            # Use maxPriorityFeePerGas from provider or default to 1 gwei
            try:
                priority_fee = self.web3.eth.max_priority_fee
            except Exception:
                priority_fee = self.web3.to_wei(1, "gwei")
                
            max_fee = (base_fee * 2) + priority_fee

            # Build transaction
            tx = self.contract.functions.distributeEpochRewards(
                recipients, uptime_values
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.web3.eth.get_transaction_count(self.account.address),
                    "gas": self.config.gas_limit,
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": priority_fee,
                    "chainId": self.config.chain_id,
                }
            )

            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)

            logger.info(f"Rewards tx sent: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                logger.info(f"Rewards distributed in block {receipt.blockNumber}")

                # Record transaction
                self._tx_history.append(
                    BridgeTransaction(
                        tx_id=f"rewards_{tx_hash.hex()[:8]}",
                        direction=BridgeDirection.TO_CHAIN,
                        from_address="bridge",
                        to_address="contract",
                        amount=sum(rewards.values()),
                        event_type="EpochRewardsDistributed",
                        timestamp=time.time(),
                        block_number=receipt.blockNumber,
                        tx_hash=tx_hash.hex(),
                        status="confirmed",
                    )
                )

                return tx_hash.hex()
            else:
                logger.error("Rewards transaction failed")
                return None

        except Exception as e:
            logger.error(f"Failed to push rewards: {e}")
            return None

    async def authorize_relayer(
        self, node_id: str, authorized: bool = True
    ) -> Optional[str]:
        result = await self._run_chain_write(
            operation="authorize_relayer",
            context={"target_node_id": node_id, "authorized": authorized},
            failure_value=None,
        )
        return result if isinstance(result, str) else None

    async def _authorize_relayer_internal(
        self, node_id: str, authorized: bool = True
    ) -> Optional[str]:
        """
        Authorize/deauthorize a relay node on-chain.

        Args:
            node_id: Mesh node identifier
            authorized: True to authorize, False to revoke

        Returns:
            Transaction hash if successful
        """
        if not self._init_web3():
            return None

        eth_addr = self.get_eth_address(node_id)
        if not eth_addr:
            logger.error(f"No Ethereum address for {node_id}")
            return None

        try:
            tx = self.contract.functions.setRelayerAuthorized(
                eth_addr, authorized
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.web3.eth.get_transaction_count(self.account.address),
                    "gas": 100000,
                    "gasPrice": self.web3.to_wei(
                        self.config.max_gas_price_gwei, "gwei"
                    ),
                    "chainId": self.config.chain_id,
                }
            )

            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)

            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            if receipt.status == 1:
                status = "authorized" if authorized else "revoked"
                logger.info(f"Relayer {node_id} {status}: {tx_hash.hex()}")
                return tx_hash.hex()

            return None

        except Exception as e:
            logger.error(f"Failed to authorize relayer: {e}")
            return None

    # ─────────────────────────────────────────────────────────────
    # State Sync
    # ─────────────────────────────────────────────────────────────

    def _execute_rpc(self, func: Callable, *args, **kwargs) -> Any:
        """Execute RPC call wrapped in Circuit Breaker."""
        try:
            return self.rpc_breaker.call(func, *args, **kwargs)
        except Exception as e:
            if "Circuit breaker is OPEN" in str(e):
                logger.warning("Blockchain RPC Breaker is OPEN. Skipping external call.")
                raise ConnectionError("Blockchain RPC currently unavailable (Circuit Breaker OPEN)")
            # Other exceptions are handled and recorded by Circuit Breaker inside .call()
            raise

    async def sync_balance(self, node_id: str) -> Optional[float]:
        """
        Sync balance from chain to local MeshToken.

        Args:
            node_id: Mesh node identifier

        Returns:
            On-chain balance
        """
        if not self._init_web3():
            return None

        eth_addr = self.get_eth_address(node_id)
        if not eth_addr:
            return None

        try:
            # Wrap contract call in Circuit Breaker
            balance_wei = self._execute_rpc(self.contract.functions.balanceOf(eth_addr).call)
            balance = float(balance_wei) / 1e18

            # Update local balance
            current = self.mesh_token.balance_of(node_id)
            if balance > current:
                self.mesh_token.mint(node_id, balance - current, "chain_sync")
            elif balance < current:
                self.mesh_token.burn(node_id, current - balance, "chain_sync")

            logger.info(f"Synced balance for {node_id}: {balance} X0T")
            return balance

        except Exception as e:
            logger.error(f"Failed to sync balance: {e}")
            return None

    async def sync_all_balances(self):
        """Sync all registered addresses from chain."""
        for node_id in self._address_mapping.keys():
            await self.sync_balance(node_id)

    def get_chain_stats(self) -> Dict:
        """Get on-chain token statistics."""
        if not self._init_web3() or not self.contract:
            return {}

        try:
            return {
                "total_staked": float(self.contract.functions.totalStaked().call())
                / 1e18,
                "current_epoch": self.contract.functions.currentEpoch().call(),
                "can_distribute": self.contract.functions.canDistributeRewards().call(),
                "chain_id": self.config.chain_id,
                "contract": self.config.contract_address,
            }
        except Exception as e:
            logger.error(f"Failed to get chain stats: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────
    # Transaction History
    # ─────────────────────────────────────────────────────────────

    def get_tx_history(self, limit: int = 100) -> List[BridgeTransaction]:
        """Get recent bridge transactions."""
        return self._tx_history[-limit:]

    def get_pending_txs(self) -> List[BridgeTransaction]:
        """Get pending transactions."""
        return [tx for tx in self._tx_history if tx.status == "pending"]

    # ─────────────────────────────────────────────────────────────
    # Operator-triggered Mint (Base Sepolia bridge deposit)
    # ─────────────────────────────────────────────────────────────

    async def mint_from_bridge_event(
        self,
        tx_hash: str,
        recipient_address: str,
        amount_wei: int,
        block_number: int,
        confirmations: Optional[int] = None,
    ) -> Optional[BridgeTransaction]:
        """
        Mint local MeshToken after a confirmed on-chain bridge deposit.

        Called by the x0tta-mesh-operator after receiving a Deposit event
        on the Base Sepolia bridge contract and waiting for the required
        number of block confirmations (default: spec.dao.bridge.confirmations).

        Args:
            tx_hash: On-chain transaction hash of the deposit.
            recipient_address: Ethereum address of the depositor.
            amount_wei: Token amount in wei (will be converted to X0T).
            block_number: Block number where the deposit was mined.
            confirmations: Override for required confirmations; falls back to
                           BridgeConfig.confirmations (default 2).

        Returns:
            BridgeTransaction record if mint succeeded, None on failure.
        """
        required = confirmations if confirmations is not None else self.config.confirmations

        # Confirm enough blocks have passed (live check when Web3 is available)
        if self._init_web3() and self.web3:
            try:
                current_block = self.web3.eth.block_number
                actual_confs = current_block - block_number
                if actual_confs < required:
                    logger.warning(
                        f"mint_from_bridge_event: only {actual_confs}/{required} "
                        f"confirmations for tx {tx_hash}"
                    )
                    return None
            except Exception as e:
                logger.warning(f"Could not verify confirmations for {tx_hash}: {e}")

        # Idempotency: skip if already processed
        already = next(
            (t for t in self._tx_history if t.tx_hash == tx_hash and t.status == "confirmed"),
            None,
        )
        if already:
            logger.info(f"mint_from_bridge_event: tx {tx_hash} already minted, skipping")
            return already

        # Resolve node_id from Ethereum address
        node_id = self.get_node_id(recipient_address)
        amount_xot = float(amount_wei) / 1e18

        if node_id:
            self.mesh_token.mint(node_id, amount_xot, "bridge_deposit_sepolia")
            logger.info(
                f"✅ Minted {amount_xot:.4f} X0T for {node_id} "
                f"(tx={tx_hash}, block={block_number})"
            )
        else:
            # Unregistered address — record for reconciliation but still create
            # a pending BridgeTransaction so the operator can resolve later.
            logger.warning(
                f"mint_from_bridge_event: no node_id for {recipient_address}, "
                f"recording as unresolved (tx={tx_hash})"
            )

        record = BridgeTransaction(
            tx_id=f"mint_{tx_hash[:12]}",
            direction=BridgeDirection.FROM_CHAIN,
            from_address=recipient_address,
            to_address=node_id or recipient_address,
            amount=amount_xot,
            event_type="BridgeDeposit",
            timestamp=time.time(),
            block_number=block_number,
            tx_hash=tx_hash,
            status="confirmed" if node_id else "unresolved",
        )
        self._tx_history.append(record)
        return record


# ─────────────────────────────────────────────────────────────────
# Epoch Reward Scheduler
# ─────────────────────────────────────────────────────────────────


class EpochRewardScheduler:
    """
    Automatic epoch reward distribution scheduler.

    Runs every hour, collects uptimes, pushes rewards to chain.
    """

    def __init__(
        self, bridge: TokenBridge, uptime_provider: Callable[[], Dict[str, float]]
    ):
        """
        Args:
            bridge: TokenBridge instance
            uptime_provider: Function that returns {node_id: uptime_percent}
        """
        self.bridge = bridge
        self.uptime_provider = uptime_provider
        self._running = False

    async def start(self):
        """Start automatic reward distribution."""
        self._running = True
        logger.info("Epoch reward scheduler started")

        while self._running:
            try:
                # Check if epoch ready
                stats = self.bridge.get_chain_stats()
                if stats.get("can_distribute"):
                    await self._distribute_epoch()

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Check every 5 minutes
            await asyncio.sleep(300)

    def stop(self):
        """Stop scheduler."""
        self._running = False

    async def _distribute_epoch(self):
        """Distribute rewards for current epoch."""
        # Get uptimes from provider
        uptimes = self.uptime_provider()

        if not uptimes:
            logger.warning("No uptime data, skipping epoch")
            return

        # Convert to int percentages
        uptime_ints = {k: int(v * 100) for k, v in uptimes.items()}

        # Push to chain
        tx_hash = await self.bridge.push_rewards_to_chain(
            rewards={}, uptimes=uptime_ints  # Actual amounts calculated on-chain
        )

        if tx_hash:
            logger.info(f"Epoch rewards distributed: {tx_hash}")
        else:
            logger.error("Failed to distribute epoch rewards")

