"""
X0T Token Bridge Core - syncing off-chain and on-chain state.

The bridge is intentionally conservative: a local transaction submission is
recorded as pending chain-write evidence, not as settlement finality.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import time
import uuid
import warnings
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import (
    AsyncSafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.marketplace_events import publish_marketplace_escrow_event
from src.services.reward_events import publish_reward_settlement_event
from src.services.service_event_identity import service_event_identity

from .abi import CONTRACT_ABI
from .policy import evaluate_bridge_policy
from .types import (
    BridgeConfig,
    BridgeDirection,
    BridgeTransaction,
    TOKEN_BRIDGE_CHAIN_READ_CLAIM_BOUNDARY,
    TOKEN_BRIDGE_CLAIM_BOUNDARY,
)

try:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"websockets\\.legacy is deprecated.*",
            category=DeprecationWarning,
            append=False,
        )
        from web3 import Web3

    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None

if TYPE_CHECKING:
    from src.dao.token import MeshToken

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "token-bridge"
_WEI_PER_XOT = 10**18
_EVENT_ID_LIMIT = 10

TOKEN_BRIDGE_SAFE_ACTUATOR_CLAIM_BOUNDARY = (
    "TokenBridge SafeActuator metadata proves only a local policy-gated "
    "chain-write attempt. It is not proof of external settlement finality, "
    "payment provider settlement, bank settlement, traffic delivery, customer "
    "delivery, revenue recognition, or production readiness."
)

_TOKEN_BRIDGE_STRONG_CLAIM_IDS = (
    "external_settlement_finality_claim_allowed",
    "payment_provider_settlement_claim_allowed",
    "bank_settlement_claim_allowed",
    "live_token_settlement_finality_claim_allowed",
    "dataplane_delivery_claim_allowed",
    "traffic_delivery_claim_allowed",
    "customer_traffic_claim_allowed",
    "revenue_recognition_claim_allowed",
    "production_readiness_claim_allowed",
)


def _hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _hash_prefix(value: Any) -> Optional[str]:
    digest = _hash(value)
    return digest[:16] if digest else None


def _legacy_token_bridge_override(name: str, default: Any) -> Any:
    legacy_module = sys.modules.get("src.dao.token_bridge")
    if legacy_module is None:
        return default
    legacy_value = getattr(legacy_module, name, default)
    return legacy_value if legacy_value is not default else default


def _resolved_web3_available() -> bool:
    return bool(_legacy_token_bridge_override("WEB3_AVAILABLE", WEB3_AVAILABLE))


def _resolved_web3_class() -> Any:
    return _legacy_token_bridge_override("Web3", Web3)


def _xot_from_wei(value: Any) -> float:
    try:
        return float(value) / _WEI_PER_XOT
    except (TypeError, ValueError):
        return 0.0


def _tx_hash_hex(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "hex"):
        try:
            return str(value.hex())
        except Exception:
            return None
    normalized = str(value).strip()
    return normalized or None


class TokenBridge:
    """Bridge between off-chain MeshToken and on-chain X0TToken/X0TBridge."""

    POLLED_EVENT_TYPES = (
        "Staked",
        "Unstaked",
        "Transfer",
        "RelayPaid",
        "BridgeDeposit",
        "BridgeRelease",
    )

    CONTRACT_ABI = CONTRACT_ABI

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
        self.mesh_token = mesh_token
        self.config = config
        self.node_id = node_id
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus
            if event_bus is not None
            else self._default_event_bus(event_project_root)
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

        service_identity = service_event_identity(service_name=_SERVICE_AGENT)
        self.identity = {
            "node_id": node_id,
            "spiffe_id": (
                spiffe_id if spiffe_id is not None else service_identity["spiffe_id"]
            ),
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
        self._last_chain_write_result: Dict[str, Any] = {}
        self._last_chain_write_event_ids: List[str] = []
        self._minted_bridge_txs: Dict[str, BridgeTransaction] = {}
        self.web3 = None
        self.contract = None
        self.account = None

        self._running = False
        self._last_block = 0
        self._tx_history: List[BridgeTransaction] = []
        self._address_mapping: Dict[str, str] = {}

        from src.resilience.advanced_patterns import (
            CircuitBreaker,
            CircuitBreakerConfig,
        )

        self.rpc_breaker = CircuitBreaker(
            config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout_seconds=60,
            ),
            name="blockchain_rpc_breaker",
        )
        self._event_handlers: Dict[str, List[Callable]] = {
            event_type: [] for event_type in self.POLLED_EVENT_TYPES
        }
        self._event_handlers["EpochRewardsDistributed"] = []
        self._initialized = False

    @property
    def last_chain_write_event_ids(self) -> List[str]:
        return list(self._last_chain_write_event_ids)

    @last_chain_write_event_ids.setter
    def last_chain_write_event_ids(self, value: Any) -> None:
        try:
            self._last_chain_write_event_ids = [str(item) for item in value]
        except TypeError:
            self._last_chain_write_event_ids = []

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
    def _hash_value(value: Any) -> Optional[str]:
        return _hash(value)

    @staticmethod
    def _policy_allowed(decision: Any) -> bool:
        return normalize_policy_allowed(decision)

    @staticmethod
    def _policy_reason(decision: Any) -> str:
        return normalize_policy_reason(decision)

    @staticmethod
    def _policy_rules(decision: Any) -> List[str]:
        return normalize_policy_rules(decision)

    def _init_web3(self) -> bool:
        if self._initialized and self.web3 and self.web3.is_connected():
            return True
        try:
            patched_web3 = _resolved_web3_class()
            if patched_web3 is None:
                return False
            from eth_account import Account
            if patched_web3 is Web3:
                from web3 import Web3 as Web3Impl
            else:
                Web3Impl = patched_web3
        except (ImportError, Exception) as exc:
            logger.error("web3/eth_account not available: %s", exc)
            return False

        all_urls = list(self.config.rpc_urls)
        if self.config.rpc_url and self.config.rpc_url not in all_urls:
            all_urls.insert(0, self.config.rpc_url)
        if not all_urls:
            return False

        for url in all_urls:
            try:
                instance = Web3Impl(Web3Impl.HTTPProvider(url))
                if not instance.is_connected():
                    continue
                self.web3 = instance
                if self.config.private_key:
                    self.account = Account.from_key(self.config.private_key)
                if self.config.contract_address:
                    self.contract = self.web3.eth.contract(
                        address=Web3Impl.to_checksum_address(
                            self.config.contract_address
                        ),
                        abi=self.CONTRACT_ABI,
                    )
                self._initialized = True
                return True
            except Exception as exc:
                logger.warning("Failed to connect to %s: %s", url, exc)
        return False

    def register_address(self, node_id: str, eth_address: str) -> None:
        normalized = str(eth_address).strip()
        if not normalized.startswith(("0x", "0X")):
            normalized = f"0x{normalized}"
        web3_impl = _resolved_web3_class()
        if _resolved_web3_available() and web3_impl is not None:
            try:
                normalized = web3_impl.to_checksum_address(normalized)
            except Exception:
                pass
        self._address_mapping[node_id] = normalized

    def get_eth_address(self, node_id: str) -> Optional[str]:
        return self._address_mapping.get(node_id)

    def get_node_id(self, eth_address: str) -> Optional[str]:
        normalized = str(eth_address).strip()
        if not normalized.startswith(("0x", "0X")):
            normalized = f"0x{normalized}"
        web3_impl = _resolved_web3_class()
        if _resolved_web3_available() and web3_impl is not None:
            try:
                normalized = web3_impl.to_checksum_address(normalized)
            except Exception:
                pass
        addr_lower = normalized.lower()
        for node_id, address in self._address_mapping.items():
            if address.lower() == addr_lower:
                return node_id
        return None

    @staticmethod
    def _mapping_summary(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {
                "entries_total": 0,
                "entries_limit": 16,
                "entries_truncated": False,
                "key_hashes": [],
                "numeric_values_total": 0.0,
                "numeric_values_count": 0,
                "raw_keys_redacted": True,
                "raw_values_redacted": True,
            }
        items = list(value.items())
        shown = items[:16]
        numeric_values = []
        for _key, item in items:
            try:
                numeric_values.append(float(item))
            except (TypeError, ValueError):
                pass
        return {
            "entries_total": len(items),
            "entries_limit": 16,
            "entries_truncated": len(items) > 16,
            "key_hashes": [_hash_prefix(key) for key, _item in shown],
            "numeric_values_total": sum(numeric_values),
            "numeric_values_count": len(numeric_values),
            "raw_keys_redacted": True,
            "raw_values_redacted": True,
        }

    @classmethod
    def _safe_context_value(cls, key: str, value: Any) -> Any:
        key_lower = key.lower()
        if key_lower in {"rewards", "uptimes"}:
            return cls._mapping_summary(value)
        if key_lower in {
            "escrow_id",
            "target_node_id",
            "node_id",
            "listing_id",
            "renter_id",
            "actor_id",
        }:
            digest = _hash_prefix(value)
            return f"sha256:{digest}" if digest else None
        if key_lower in {"amount_xot", "amount", "chain_id", "confirmations"}:
            return value
        if any(
            fragment in key_lower
            for fragment in (
                "address",
                "wallet",
                "spiffe",
                "did",
                "contract",
                "private",
                "secret",
                "token",
                "key",
            )
        ):
            digest = _hash_prefix(value)
            return f"sha256:{digest}" if digest else None
        if isinstance(value, dict):
            return {
                str(child_key): cls._safe_context_value(str(child_key), child_value)
                for child_key, child_value in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._safe_context_value(key, item) for item in list(value)[:16]]
        return value

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_context_value(str(key), value)
            for key, value in context.items()
        }

    def _identity_hashes(self) -> Dict[str, Optional[str]]:
        return {f"{key}_hash": _hash_prefix(value) for key, value in self.identity.items()}

    def _identity_fields_present(self) -> Dict[str, bool]:
        return {key: value is not None for key, value in self.identity.items()}

    @staticmethod
    def _result_summary(
        result: SafeActuatorResult,
        *,
        submitted_transaction: bool,
        transaction_hash: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "success": bool(result.success),
            "simulated": bool(result.simulated),
            "submitted_transaction": bool(submitted_transaction),
            "transaction_hash_present": bool(transaction_hash),
            "transaction_hash_hash": _hash_prefix(transaction_hash),
            "raw_result_redacted": True,
        }

    def _chain_write_claim_gate(
        self,
        *,
        operation: str,
        success: bool,
        simulated: bool,
        submitted_transaction: bool,
        policy_decision: Any = None,
    ) -> Dict[str, Any]:
        claim_gate = {
            "schema": "x0tta6bl4.token_bridge.safe_actuator_claim_gate.v1",
            "operation": operation,
            "local_chain_write_attempt_succeeded": success and not simulated,
            "pending_chain_submission_claim_allowed": bool(submitted_transaction),
            "safe_actuator_result_recorded": True,
            "safe_actuator_simulated": simulated,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "claim_boundary": TOKEN_BRIDGE_SAFE_ACTUATOR_CLAIM_BOUNDARY,
            "redacted": True,
        }
        claim_gate.update(
            {claim_id: False for claim_id in _TOKEN_BRIDGE_STRONG_CLAIM_IDS}
        )
        return claim_gate

    @staticmethod
    def _chain_write_cross_plane_claim_gate() -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.token_bridge.safe_actuator_cross_plane_claim_gate.v1",
            "economy_plane_evidence_type": "local_token_bridge_chain_write_attempt",
            "control_plane_evidence_type": "policy_gated_safe_actuator_attempt",
            "requires_external_finality_evidence_for_settlement_claim": True,
            "requires_dataplane_evidence_for_delivery_claim": True,
            "requires_customer_traffic_proof_for_customer_claim": True,
            "requires_revenue_recognition_review_for_revenue_claim": True,
            "allowed": False,
            "redacted": True,
        }

    def _chain_write_evidence_metadata(
        self,
        *,
        operation: str,
        context: Dict[str, Any],
        result: SafeActuatorResult,
        submitted_transaction: bool,
        transaction_hash: Optional[str],
        policy_decision: Any = None,
        event_ids: Optional[List[str]] = None,
    ) -> SafeActuatorEvidenceMetadata:
        upstream = result.evidence_metadata
        evidence_event_ids = list(upstream.event_ids or event_ids or [])
        evidence = {
            **dict(upstream.evidence),
            "source_agents": list(upstream.source_agents or [self.source_agent]),
            "event_ids": evidence_event_ids,
            "operation": operation,
            "resource": f"dao:token_bridge:{operation}",
            "context_keys": sorted(str(key) for key in context),
            "submitted_transaction": bool(submitted_transaction),
            "transaction_hash_present": bool(transaction_hash),
            "transaction_hash_hash": _hash_prefix(transaction_hash),
            "safe_actuator_simulated": bool(result.simulated),
            "raw_context_values_redacted": True,
            "raw_result_values_redacted": True,
        }
        return SafeActuatorEvidenceMetadata.from_value(
            {
                "claim_gate": self._chain_write_claim_gate(
                    operation=operation,
                    success=bool(result.success),
                    simulated=bool(result.simulated),
                    submitted_transaction=submitted_transaction,
                    policy_decision=policy_decision,
                ),
                "cross_plane_claim_gate": self._chain_write_cross_plane_claim_gate(),
                "evidence": evidence,
                "source_agents": list(upstream.source_agents or [self.source_agent]),
                "event_ids": evidence_event_ids,
                "claim_boundary": TOKEN_BRIDGE_SAFE_ACTUATOR_CLAIM_BOUNDARY,
                "redacted": True,
            }
        )

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
        simulated: Optional[bool] = None,
        submitted_transaction: bool = False,
        transaction_hash: Optional[str] = None,
        source_quality: str = "",
        duration_ms: Optional[float] = None,
        result: Optional[SafeActuatorResult] = None,
        safe_actuator_used: bool = True,
        metadata: Optional[SafeActuatorEvidenceMetadata] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        result = result or SafeActuatorResult(False, reason, simulated=bool(simulated))
        payload = {
            "component": "dao.token_bridge",
            "stage": stage,
            "operation": operation,
            "resource": f"dao:token_bridge:{operation}",
            "service_name": self.source_agent,
            "source_alias": self.source_agent,
            "layer": "dao_chain_bridge",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "identity_hashes": self._identity_hashes(),
            "identity_fields_present": self._identity_fields_present(),
            "context": self._safe_context(context),
            "context_values_redacted": True,
            "context_payloads_redacted": True,
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
            "safe_actuator_used": safe_actuator_used,
            "safe_actuator_evidence_metadata": (
                metadata.to_dict()
                if metadata is not None
                else SafeActuatorEvidenceMetadata().to_dict()
            ),
            "submitted_transaction": bool(submitted_transaction),
            "transaction_hash": transaction_hash,
            "transaction_hash_hash": _hash_prefix(transaction_hash),
            "source_quality": source_quality,
            "duration_ms": round(float(duration_ms or 0.0), 3),
            "success": success,
            "simulated": simulated,
            "reason": reason,
            "result_summary": self._result_summary(
                result,
                submitted_transaction=submitted_transaction,
                transaction_hash=transaction_hash,
            ),
            "result_payload_redacted": True,
            "claim_boundary": TOKEN_BRIDGE_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish TokenBridge chain-write event: %s", exc)
            return None

    def _evaluate_chain_write_policy(self, operation: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "TokenBridge policy engine is required but unavailable"
            return True, None, ""
        return evaluate_bridge_policy(
            self.policy_engine,
            self.identity.get("spiffe_id") or "",
            operation,
        )

    async def _run_chain_write(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        self._last_chain_write_result = {}
        self._last_chain_write_event_ids = []
        started = time.monotonic()
        event_ids: List[str] = []
        received_id = self._publish_chain_write_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            operation=operation,
            context=context,
            source_quality="request_received",
            safe_actuator_used=False,
            duration_ms=0,
        )
        if received_id:
            event_ids.append(received_id)

        policy_allowed, policy_decision, policy_reason = self._evaluate_chain_write_policy(
            operation
        )
        if not policy_allowed:
            result = SafeActuatorResult(False, policy_reason)
            metadata = self._chain_write_evidence_metadata(
                operation=operation,
                context=context,
                result=result,
                submitted_transaction=False,
                transaction_hash=None,
                policy_decision=policy_decision,
                event_ids=event_ids,
            )
            blocked_id = self._publish_chain_write_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                operation=operation,
                context=context,
                reason=policy_reason,
                policy_decision=policy_decision,
                success=False,
                simulated=False,
                submitted_transaction=False,
                source_quality="policy_denied_before_actuator",
                duration_ms=(time.monotonic() - started) * 1000,
                result=result,
                safe_actuator_used=False,
                metadata=metadata,
            )
            if blocked_id:
                event_ids.append(blocked_id)
            self._last_chain_write_event_ids = event_ids[-_EVENT_ID_LIMIT:]
            return SafeActuatorResult(
                False,
                policy_reason,
                evidence_metadata=metadata,
            )

        start_id = self._publish_chain_write_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
            source_quality="safe_actuator_start",
            duration_ms=(time.monotonic() - started) * 1000,
        )
        if start_id:
            event_ids.append(start_id)

        actuator_result = await self.safe_actuator.execute(operation, context)
        transaction_hash = self._last_chain_write_result.get("transaction_hash")
        submitted_transaction = bool(
            self._last_chain_write_result.get("submitted_transaction")
        )
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        if simulated:
            source_quality = "safe_actuator_simulated_no_settlement"
        elif success and submitted_transaction:
            source_quality = "safe_actuator_submitted_transaction"
        else:
            source_quality = "safe_actuator_blocked_or_failed"

        metadata = self._chain_write_evidence_metadata(
            operation=operation,
            context=context,
            result=actuator_result,
            submitted_transaction=submitted_transaction,
            transaction_hash=transaction_hash,
            policy_decision=policy_decision,
            event_ids=event_ids,
        )
        result = SafeActuatorResult(
            success=success,
            reason=actuator_result.reason,
            simulated=simulated,
            evidence_metadata=metadata,
        )
        terminal_id = self._publish_chain_write_event(
            EventType.PIPELINE_STAGE_END if success and not simulated else EventType.TASK_FAILED,
            stage=(
                "actuator_completed"
                if success and not simulated
                else "actuator_simulated"
                if simulated
                else "actuator_failed"
            ),
            operation=operation,
            context=context,
            reason=result.reason,
            policy_decision=policy_decision,
            success=success and not simulated,
            simulated=simulated,
            submitted_transaction=submitted_transaction and not simulated,
            transaction_hash=transaction_hash if not simulated else None,
            source_quality=source_quality,
            duration_ms=(time.monotonic() - started) * 1000,
            result=result,
            metadata=metadata,
        )
        if terminal_id:
            event_ids.append(terminal_id)
        self._last_chain_write_event_ids = event_ids[-_EVENT_ID_LIMIT:]
        return result

    def _build_transaction(self, fn: Any) -> Dict[str, Any]:
        builder = getattr(fn, "build_transaction", None)
        if callable(builder):
            return builder(
                {
                    "from": getattr(self.account, "address", None),
                    "gas": self.config.gas_limit,
                    "chainId": self.config.chain_id,
                }
            )
        return {}

    def _send_contract_transaction(self, fn: Any) -> tuple[Optional[str], Any]:
        tx = self._build_transaction(fn)
        signed = self.account.sign_transaction(tx) if self.account is not None else tx
        raw_tx = getattr(signed, "rawTransaction", None)
        if raw_tx is None:
            raw_tx = getattr(signed, "raw_transaction", signed)
        tx_hash_raw = self.web3.eth.send_raw_transaction(raw_tx)
        tx_hash = _tx_hash_hex(tx_hash_raw)
        receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash_raw)
        return tx_hash, receipt

    async def _execute_chain_write_through_actuator(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        handlers = {
            "push_rewards_to_chain": self._submit_rewards_transaction,
            "lock_escrow_on_chain": self._submit_escrow_transaction,
            "release_escrow_on_chain": self._submit_escrow_transaction,
            "refund_escrow_on_chain": self._submit_escrow_transaction,
            "authorize_relayer": self._submit_authorize_relayer,
        }
        handler = handlers.get(operation)
        if handler is None:
            return SafeActuatorResult(False, f"unsupported TokenBridge operation: {operation}")
        try:
            return handler(operation, context)
        except Exception as exc:
            logger.exception("TokenBridge chain write failed")
            self._last_chain_write_result = {
                "submitted_transaction": False,
                "error": str(exc),
            }
            return SafeActuatorResult(False, f"TokenBridge chain write failed: {exc}")

    def _submit_rewards_transaction(
        self,
        _operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if not self._init_web3():
            return SafeActuatorResult(False, "TokenBridge Web3 is unavailable")
        if self.contract is None:
            return SafeActuatorResult(False, "TokenBridge contract is unavailable")
        if self.account is None:
            return SafeActuatorResult(False, "TokenBridge account is unavailable")
        if not self.contract.functions.canDistributeRewards().call():
            return SafeActuatorResult(False, "TokenBridge rewards cannot be distributed now")

        rewards = context.get("rewards") if isinstance(context.get("rewards"), dict) else {}
        uptimes = context.get("uptimes") if isinstance(context.get("uptimes"), dict) else {}
        recipients: List[str] = []
        uptime_values: List[int] = []
        reward_values_wei: List[int] = []
        for node_id, amount in rewards.items():
            address = self.get_eth_address(str(node_id))
            if not address:
                continue
            recipients.append(address)
            uptime_values.append(int(uptimes.get(node_id, 100)))
            reward_values_wei.append(int(float(amount) * _WEI_PER_XOT))
        if not recipients:
            return SafeActuatorResult(False, "TokenBridge has no valid reward recipients")

        fn = self.contract.functions.distributeEpochRewards(
            recipients,
            uptime_values,
            reward_values_wei,
        )
        tx_hash, receipt = self._send_contract_transaction(fn)
        if not tx_hash or getattr(receipt, "status", 0) != 1:
            return SafeActuatorResult(False, "TokenBridge reward transaction failed")

        total_amount = sum(float(value) for value in rewards.values())
        self._tx_history.append(
            BridgeTransaction(
                tx_id=str(uuid.uuid4()),
                direction=BridgeDirection.TO_CHAIN,
                from_address=getattr(self.account, "address", ""),
                to_address=self.config.contract_address,
                amount=total_amount,
                event_type="EpochRewardsDistributed",
                timestamp=time.time(),
                block_number=getattr(receipt, "blockNumber", None),
                tx_hash=tx_hash,
                status="confirmed",
            )
        )
        self._last_chain_write_result = {
            "submitted_transaction": True,
            "transaction_hash": tx_hash,
            "block_number": getattr(receipt, "blockNumber", None),
        }
        return SafeActuatorResult(True, "TokenBridge reward transaction submitted")

    def _submit_escrow_transaction(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if not self._init_web3():
            if self.config.allow_simulated_chain_writes:
                simulated_tx = f"sim_tx_{uuid.uuid4().hex[:8]}"
                self._last_chain_write_result = {
                    "submitted_transaction": False,
                    "simulated_tx_id": simulated_tx,
                }
                return SafeActuatorResult(
                    True,
                    "TokenBridge escrow simulation recorded locally",
                    simulated=True,
                )
            return SafeActuatorResult(False, "TokenBridge Web3 is unavailable")

        return SafeActuatorResult(
            False,
            f"TokenBridge {operation} has no real submission implementation yet",
        )

    def _submit_authorize_relayer(
        self,
        _operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if not self._init_web3():
            return SafeActuatorResult(False, "TokenBridge Web3 is unavailable")
        if self.contract is None or self.account is None:
            return SafeActuatorResult(False, "TokenBridge contract/account unavailable")
        node_id = str(context.get("node_id") or "")
        address = self.get_eth_address(node_id)
        if not address:
            return SafeActuatorResult(False, "TokenBridge relayer address is unknown")
        authorized = bool(context.get("authorized", True))
        fn = self.contract.functions.setRelayerAuthorized(address, authorized)
        tx_hash, receipt = self._send_contract_transaction(fn)
        if not tx_hash or getattr(receipt, "status", 0) != 1:
            return SafeActuatorResult(False, "TokenBridge relayer authorization failed")
        self._last_chain_write_result = {
            "submitted_transaction": True,
            "transaction_hash": tx_hash,
        }
        return SafeActuatorResult(True, "TokenBridge relayer authorization submitted")

    async def push_rewards_to_chain(
        self,
        rewards: Dict[str, float],
        uptimes: Optional[Dict[str, int]] = None,
    ) -> Optional[str]:
        context = {"rewards": dict(rewards), "uptimes": dict(uptimes or {})}
        result = await self._run_chain_write("push_rewards_to_chain", context)
        tx_hash = self._last_chain_write_result.get("transaction_hash")
        submitted = bool(result.success) and not bool(result.simulated) and bool(tx_hash)
        reward_event_id = publish_reward_settlement_event(
            transition="recorded" if submitted else "blocked",
            source_agent=self.source_agent,
            node_address=self.identity["wallet_address"],
            node_id=self.identity["node_id"],
            spiffe_id=self.identity["spiffe_id"],
            did=self.identity["did"],
            wallet_address=self.identity["wallet_address"],
            packets=0,
            amount=sum(float(value) for value in rewards.values()),
            status="submitted" if submitted else "blocked",
            submitted_transaction=submitted,
            simulated=bool(result.simulated),
            settlement_recorded=submitted,
            local_accounting_recorded=False,
            transaction_hash=tx_hash,
            upstream_event_ids=self._last_chain_write_event_ids,
            upstream_source_agents=[self.source_agent],
            upstream_claim_gate=result.evidence_metadata.claim_gate,
            upstream_cross_plane_claim_gate=result.evidence_metadata.cross_plane_claim_gate,
            evidence_metadata=result.evidence_metadata.to_dict(),
            reason=result.reason,
            event_bus=self.event_bus,
            project_root=self.event_project_root,
        )
        if reward_event_id:
            self._last_chain_write_event_ids.append(reward_event_id)
        return tx_hash if submitted else None

    async def lock_escrow_on_chain(
        self,
        escrow_id: str,
        target_node_id: str,
        amount_xot: float,
    ) -> Optional[str]:
        context = {
            "escrow_id": escrow_id,
            "target_node_id": target_node_id,
            "amount_xot": amount_xot,
        }
        result = await self._run_chain_write("lock_escrow_on_chain", context)
        tx_hash = self._last_chain_write_result.get("transaction_hash")
        simulated_tx = self._last_chain_write_result.get("simulated_tx_id")
        if result.simulated:
            event_id = publish_marketplace_escrow_event(
                transition="blocked",
                source_agent=self.source_agent,
                escrow_id=escrow_id,
                listing_id=escrow_id,
                node_id=target_node_id,
                spiffe_id=self.identity["spiffe_id"],
                did=self.identity["did"],
                wallet_address=self.identity["wallet_address"],
                amount_token=amount_xot,
                status="blocked",
                upstream_event_ids=self._last_chain_write_event_ids,
                upstream_source_agents=[self.source_agent],
                settlement_evidence={
                    "decision_basis": "token_bridge_simulated",
                    "source_quality": "safe_actuator_simulated_no_settlement",
                    "settlement_action": "lock_escrow_on_chain",
                    "claim_gate": result.evidence_metadata.claim_gate,
                },
                reason="token_bridge_simulated_no_settlement",
                event_bus=self.event_bus,
                project_root=self.event_project_root,
            )
            if event_id:
                self._last_chain_write_event_ids.append(event_id)
            return str(simulated_tx) if simulated_tx else None
        if result.success and tx_hash:
            event_id = publish_marketplace_escrow_event(
                transition="held",
                source_agent=self.source_agent,
                escrow_id=escrow_id,
                listing_id=escrow_id,
                node_id=target_node_id,
                spiffe_id=self.identity["spiffe_id"],
                did=self.identity["did"],
                wallet_address=self.identity["wallet_address"],
                amount_token=amount_xot,
                status="held",
                upstream_event_ids=self._last_chain_write_event_ids,
                upstream_source_agents=[self.source_agent],
                event_bus=self.event_bus,
                project_root=self.event_project_root,
            )
            if event_id:
                self._last_chain_write_event_ids.append(event_id)
            return tx_hash
        event_id = publish_marketplace_escrow_event(
            transition="blocked",
            source_agent=self.source_agent,
            escrow_id=escrow_id,
            listing_id=escrow_id,
            node_id=target_node_id,
            spiffe_id=self.identity["spiffe_id"],
            did=self.identity["did"],
            wallet_address=self.identity["wallet_address"],
            amount_token=amount_xot,
            status="blocked",
            upstream_event_ids=self._last_chain_write_event_ids,
            upstream_source_agents=[self.source_agent],
            reason=result.reason,
            event_bus=self.event_bus,
            project_root=self.event_project_root,
        )
        if event_id:
            self._last_chain_write_event_ids.append(event_id)
        return None

    async def release_escrow_on_chain(self, escrow_id: str) -> bool:
        result = await self._run_chain_write(
            "release_escrow_on_chain",
            {"escrow_id": escrow_id},
        )
        return bool(result.success) and (
            bool(result.simulated)
            or bool(self._last_chain_write_result.get("transaction_hash"))
        )

    async def refund_escrow_on_chain(self, escrow_id: str) -> bool:
        result = await self._run_chain_write(
            "refund_escrow_on_chain",
            {"escrow_id": escrow_id},
        )
        return bool(result.success) and (
            bool(result.simulated)
            or bool(self._last_chain_write_result.get("transaction_hash"))
        )

    async def authorize_relayer(
        self,
        node_id: str,
        authorized: bool = True,
    ) -> Optional[str]:
        result = await self._run_chain_write(
            "authorize_relayer",
            {"node_id": node_id, "authorized": authorized},
        )
        tx_hash = self._last_chain_write_result.get("transaction_hash")
        return tx_hash if result.success and tx_hash else None

    async def start(self) -> None:
        if not self._init_web3():
            return
        self._running = True
        self._last_block = self.web3.eth.block_number
        while self._running:
            try:
                await self._poll_events()
            except Exception as exc:
                logger.error("Polling error: %s", exc)
            await asyncio.sleep(self.config.poll_interval)

    def stop(self) -> None:
        self._running = False

    def on_event(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._event_handlers:
            return
        self._event_handlers[event_type].append(handler)

    async def _poll_events(self) -> None:
        curr = self.web3.eth.block_number
        confirmed = curr - max(int(self.config.confirmations or 0), 0)
        if confirmed <= self._last_block:
            return
        from_block, to_block = self._last_block + 1, confirmed
        for event_name in self.POLLED_EVENT_TYPES:
            await self._process_event_type(event_name, from_block, to_block)
        self._last_block = confirmed

    async def _process_event_type(
        self,
        event_name: str,
        from_block: int,
        to_block: int,
    ) -> None:
        if self.contract is None:
            return
        try:
            event_filter = getattr(self.contract.events, event_name)
            logs = event_filter.get_logs(fromBlock=from_block, toBlock=to_block)
            for log in logs:
                await self._handle_event(event_name, log)
        except Exception as exc:
            logger.error("Error polling %s: %s", event_name, exc)

    async def _notify_event_handlers(self, event_name: str, event: Any) -> None:
        for handler in self._event_handlers.get(event_name, []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.error("TokenBridge event handler failed for %s: %s", event_name, exc)

    def _publish_chain_read_event(
        self,
        *,
        event_name: str,
        chain_arg_keys: List[str],
        sync_result: Dict[str, Any],
        transaction_hash: Optional[str] = None,
        block_number: Optional[int] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        payload = {
            "component": "dao.token_bridge",
            "stage": "chain_event_observed",
            "operation": "chain_read",
            "resource": f"dao:token_bridge:from_chain:{event_name.lower()}",
            "service_name": self.source_agent,
            "source_alias": self.source_agent,
            "layer": "dao_chain_bridge",
            "event_name": event_name,
            "block_number": block_number,
            "transaction_hash": transaction_hash,
            "transaction_hash_hash": _hash_prefix(transaction_hash),
            "chain_arg_keys": chain_arg_keys,
            "chain_arg_values_redacted": True,
            "safe_observation": True,
            "identity": dict(self.identity),
            "identity_hashes": self._identity_hashes(),
            "sync_result": sync_result,
            "claim_boundary": TOKEN_BRIDGE_CHAIN_READ_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.source_agent,
                payload,
                priority=5,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish TokenBridge chain-read event: %s", exc)
            return None

    async def _handle_event(self, event_name: str, event: Any) -> None:
        args = getattr(event, "args", {})
        tx_hash = _tx_hash_hex(getattr(event, "transactionHash", None))
        block_number = getattr(event, "blockNumber", None)
        if event_name == "Staked":
            user = args.get("user") if hasattr(args, "get") else None
            amount_wei = args.get("amount") if hasattr(args, "get") else 0
            amount_xot = _xot_from_wei(amount_wei)
            node_id = self.get_node_id(user)
            await self._sync_stake(user, amount_wei, is_stake=True)
            self._tx_history.append(
                BridgeTransaction(
                    tx_id=str(uuid.uuid4()),
                    direction=BridgeDirection.FROM_CHAIN,
                    from_address=user or "",
                    to_address="mesh_token",
                    amount=amount_xot,
                    event_type="Staked",
                    timestamp=time.time(),
                    block_number=block_number,
                    tx_hash=tx_hash,
                    status="confirmed",
                )
            )
            sync_result = {
                "local_update": "stake_synced",
                "amount_xot": amount_xot,
                "address_hash": _hash(user),
                "node_known": node_id is not None,
            }
            self._publish_chain_read_event(
                event_name="Staked",
                chain_arg_keys=["user", "amount"],
                sync_result=sync_result,
                transaction_hash=tx_hash,
                block_number=block_number,
            )
        elif event_name == "Unstaked":
            user = args.get("user") if hasattr(args, "get") else None
            amount_wei = args.get("amount") if hasattr(args, "get") else 0
            amount_xot = _xot_from_wei(amount_wei)
            await self._sync_stake(user, amount_wei, is_stake=False)
            self._tx_history.append(
                BridgeTransaction(
                    tx_id=str(uuid.uuid4()),
                    direction=BridgeDirection.FROM_CHAIN,
                    from_address=user or "",
                    to_address="mesh_token",
                    amount=amount_xot,
                    event_type="Unstaked",
                    timestamp=time.time(),
                    block_number=block_number,
                    tx_hash=tx_hash,
                    status="confirmed",
                )
            )
            self._publish_chain_read_event(
                event_name="Unstaked",
                chain_arg_keys=["user", "amount"],
                sync_result={
                    "local_update": "unstake_synced",
                    "amount_xot": amount_xot,
                    "address_hash": _hash(user),
                },
                transaction_hash=tx_hash,
                block_number=block_number,
            )
        elif event_name == "Transfer":
            from_address = args.get("from") if hasattr(args, "get") else None
            to_address = args.get("to") if hasattr(args, "get") else None
            amount_wei = args.get("value") if hasattr(args, "get") else 0
            amount_xot = _xot_from_wei(amount_wei)
            await self._sync_transfer(from_address, to_address, amount_wei)
            self._tx_history.append(
                BridgeTransaction(
                    tx_id=str(uuid.uuid4()),
                    direction=BridgeDirection.FROM_CHAIN,
                    from_address=from_address or "",
                    to_address=to_address or "",
                    amount=amount_xot,
                    event_type="Transfer",
                    timestamp=time.time(),
                    block_number=block_number,
                    tx_hash=tx_hash,
                    status="confirmed",
                )
            )
            self._publish_chain_read_event(
                event_name="Transfer",
                chain_arg_keys=["from", "to", "value"],
                sync_result={
                    "local_update": "transfer_synced",
                    "amount_xot": amount_xot,
                    "from_hash": _hash(from_address),
                    "to_hash": _hash(to_address),
                },
                transaction_hash=tx_hash,
                block_number=block_number,
            )
        elif event_name == "RelayPaid":
            payer = args.get("payer") if hasattr(args, "get") else None
            relayer = args.get("relayer") if hasattr(args, "get") else None
            amount_wei = args.get("amount") if hasattr(args, "get") else 0
            amount_xot = _xot_from_wei(amount_wei)
            await self._sync_relay_payment(payer, relayer, amount_wei)
            self._tx_history.append(
                BridgeTransaction(
                    tx_id=str(uuid.uuid4()),
                    direction=BridgeDirection.FROM_CHAIN,
                    from_address=payer or "",
                    to_address=relayer or "",
                    amount=amount_xot,
                    event_type="RelayPaid",
                    timestamp=time.time(),
                    block_number=block_number,
                    tx_hash=tx_hash,
                    status="confirmed",
                )
            )
            self._publish_chain_read_event(
                event_name="RelayPaid",
                chain_arg_keys=["payer", "relayer", "amount"],
                sync_result={
                    "local_update": "relay_payment_observed",
                    "amount_xot": amount_xot,
                    "payer_hash": _hash(payer),
                    "relayer_hash": _hash(relayer),
                },
                transaction_hash=tx_hash,
                block_number=block_number,
            )
        elif event_name == "BridgeDeposit":
            recipient = args.get("recipient") if hasattr(args, "get") else None
            amount_wei = args.get("amount") if hasattr(args, "get") else 0
            amount_xot = _xot_from_wei(amount_wei)
            tx_record = await self.mint_from_bridge_event(
                tx_hash=tx_hash or "",
                recipient_address=recipient or "",
                amount_wei=amount_wei,
                block_number=int(block_number or 0),
            )
            sync_result = {
                "local_update": "bridge_deposit_minted"
                if tx_record is not None and tx_record.status == "confirmed"
                else "unresolved",
                "transaction_status": tx_record.status if tx_record is not None else "pending",
                "amount_xot": amount_xot,
                "recipient_hash": _hash(recipient),
            }
            self._publish_chain_read_event(
                event_name="BridgeDeposit",
                chain_arg_keys=["recipient", "amount"],
                sync_result=sync_result,
                transaction_hash=tx_hash,
                block_number=block_number,
            )
        elif event_name == "BridgeRelease":
            recipient = args.get("recipient") if hasattr(args, "get") else None
            amount_wei = args.get("amount") if hasattr(args, "get") else 0
            amount_xot = _xot_from_wei(amount_wei)
            self._tx_history.append(
                BridgeTransaction(
                    tx_id=str(uuid.uuid4()),
                    direction=BridgeDirection.FROM_CHAIN,
                    from_address="bridge",
                    to_address=recipient or "",
                    amount=amount_xot,
                    event_type="BridgeRelease",
                    timestamp=time.time(),
                    block_number=block_number,
                    tx_hash=tx_hash,
                    status="confirmed",
                )
            )
            self._publish_chain_read_event(
                event_name="BridgeRelease",
                chain_arg_keys=["recipient", "amount"],
                sync_result={
                    "local_update": "bridge_release_observed",
                    "amount_xot": amount_xot,
                    "recipient_hash": _hash(recipient),
                },
                transaction_hash=tx_hash,
                block_number=block_number,
            )
        else:
            self._tx_history.append(
                BridgeTransaction(
                    tx_id=str(uuid.uuid4()),
                    direction=BridgeDirection.FROM_CHAIN,
                    from_address="<redacted>",
                    to_address="<redacted>",
                    amount=0.0,
                    event_type=event_name,
                    timestamp=time.time(),
                    block_number=block_number,
                    tx_hash=tx_hash,
                    status="confirmed",
                )
            )
        await self._notify_event_handlers(event_name, event)

    async def _sync_stake(
        self,
        user_address: str,
        amount_wei: int,
        *,
        is_stake: bool,
    ) -> None:
        node_id = self.get_node_id(user_address)
        if node_id is None:
            return
        amount_xot = _xot_from_wei(amount_wei)
        if is_stake:
            current_balance = float(self.mesh_token.balance_of(node_id))
            if current_balance < amount_xot:
                self.mesh_token.mint(node_id, amount_xot - current_balance, "bridge_sync")
            self.mesh_token.stake(node_id, amount_xot)
            return
        if node_id in getattr(self.mesh_token, "stakes", {}):
            del self.mesh_token.stakes[node_id]

    async def _sync_transfer(
        self,
        from_address: str,
        to_address: str,
        amount_wei: int,
    ) -> None:
        from_node = self.get_node_id(from_address)
        to_node = self.get_node_id(to_address)
        amount_xot = _xot_from_wei(amount_wei)
        if from_node and to_node:
            self.mesh_token.transfer(from_node, to_node, amount_xot)
        elif to_node:
            self.mesh_token.mint(to_node, amount_xot, "bridge_deposit")

    async def sync_balance(self, node_id: str) -> Optional[float]:
        if not self._init_web3():
            return None
        address = self.get_eth_address(node_id)
        if not address or self.contract is None:
            return None
        try:
            raw_balance = self.contract.functions.balanceOf(address).call()
            chain_balance = _xot_from_wei(raw_balance)
            local_balance = float(self.mesh_token.balance_of(node_id))
            delta = round(chain_balance - local_balance, 12)
            if delta > 0:
                self.mesh_token.mint(node_id, delta, "chain_sync")
                update_action = "minted"
            elif delta < 0:
                self.mesh_token.burn(node_id, abs(delta), "chain_sync")
                update_action = "burned"
            else:
                update_action = "unchanged"
            self._publish_chain_read_event(
                event_name="balanceOf",
                chain_arg_keys=["account"],
                sync_result={
                    "local_update": "balance_synced",
                    "update_action": update_action,
                    "balance_xot": chain_balance,
                    "delta_xot": abs(delta),
                    "address_hash": _hash(address),
                },
            )
            return chain_balance
        except Exception as exc:
            logger.error("TokenBridge balance sync failed: %s", exc)
            return None

    async def sync_all_balances(self) -> None:
        for node_id in list(self._address_mapping):
            await self.sync_balance(node_id)

    def get_chain_stats(self) -> Dict[str, Any]:
        if not self._init_web3() or self.contract is None:
            return {}
        try:
            total_staked = _xot_from_wei(
                self.contract.functions.totalStaked().call()
            )
            current_epoch = int(self.contract.functions.currentEpoch().call())
            can_distribute = bool(
                self.contract.functions.canDistributeRewards().call()
            )
            stats = {
                "total_staked": total_staked,
                "current_epoch": current_epoch,
                "can_distribute": can_distribute,
                "chain_id": self.config.chain_id,
                "contract": self.config.contract_address,
            }
            self._publish_chain_read_event(
                event_name="chainStats",
                chain_arg_keys=["contract"],
                sync_result={
                    "local_update": "chain_stats_read",
                    "total_staked": total_staked,
                    "current_epoch": current_epoch,
                    "can_distribute": can_distribute,
                    "contract_address_hash": _hash(self.config.contract_address),
                },
            )
            return stats
        except Exception as exc:
            logger.error("TokenBridge stats read failed: %s", exc)
            return {}

    async def _sync_relay_payment(
        self,
        payer_address: str,
        relayer_address: str,
        amount_wei: int,
    ) -> None:
        logger.info(
            "Observed relay payment payer=%s relayer=%s amount_xot=%s",
            _hash_prefix(payer_address),
            _hash_prefix(relayer_address),
            _xot_from_wei(amount_wei),
        )

    async def mint_from_bridge_event(
        self,
        *,
        tx_hash: str,
        recipient_address: str,
        amount_wei: int,
        block_number: int,
        confirmations: Optional[int] = None,
    ) -> Optional[BridgeTransaction]:
        if tx_hash in self._minted_bridge_txs:
            return self._minted_bridge_txs[tx_hash]
        required_confirmations = (
            self.config.confirmations if confirmations is None else confirmations
        )
        if self._init_web3() and self.web3 is not None:
            current_block = getattr(self.web3.eth, "block_number", block_number)
            if current_block - block_number < required_confirmations:
                return None
        amount_xot = _xot_from_wei(amount_wei)
        node_id = self.get_node_id(recipient_address)
        status = "confirmed" if node_id else "unresolved"
        if node_id:
            self.mesh_token.mint(node_id, amount_xot, "bridge_deposit_sepolia")
        record = BridgeTransaction(
            tx_id=str(uuid.uuid4()),
            direction=BridgeDirection.FROM_CHAIN,
            from_address="<redacted>",
            to_address="<redacted>",
            amount=amount_xot,
            event_type="BridgeDeposit",
            timestamp=time.time(),
            block_number=block_number,
            tx_hash=tx_hash,
            status=status,
        )
        self._minted_bridge_txs[tx_hash] = record
        self._tx_history.append(record)
        return record

    def get_tx_history(self, limit: int = 100) -> List[BridgeTransaction]:
        return list(self._tx_history[-limit:])

    def get_pending_txs(self) -> List[BridgeTransaction]:
        return [tx for tx in self._tx_history if tx.status == "pending"]


class EpochRewardScheduler:
    def __init__(
        self,
        bridge: TokenBridge,
        uptime_provider: Callable[[], Dict[str, float]],
    ):
        self.bridge = bridge
        self.uptime_provider = uptime_provider
        self._running = False

    async def start(self) -> None:
        self._running = True
        while self._running:
            try:
                stats = self.bridge.get_chain_stats()
                if stats.get("can_distribute"):
                    await self._distribute_epoch(stats=stats)
            except Exception as exc:
                logger.error("Epoch reward scheduler error: %s", exc)
            await asyncio.sleep(300)

    def stop(self) -> None:
        self._running = False

    @staticmethod
    def _uptime_summary(uptimes: Dict[str, float]) -> Dict[str, Any]:
        return {
            "nodes_total": len(uptimes),
            "node_id_hashes": [_hash(node_id) for node_id in list(uptimes)[:16]],
            "raw_node_ids_redacted": True,
        }

    @staticmethod
    def _stats_summary(stats: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "current_epoch": stats.get("current_epoch"),
            "total_staked": stats.get("total_staked"),
            "can_distribute": bool(stats.get("can_distribute")),
            "chain_id": stats.get("chain_id"),
            "contract_address_hash": _hash(stats.get("contract")),
            "raw_contract_address_redacted": True,
        }

    async def _distribute_epoch(
        self,
        stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        stats = stats if stats is not None else self.bridge.get_chain_stats()
        uptimes_raw = self.uptime_provider() or {}
        if not uptimes_raw:
            return
        uptimes = {node_id: int(value * 100) for node_id, value in uptimes_raw.items()}
        tx_hash = await self.bridge.push_rewards_to_chain(rewards={}, uptimes=uptimes)
        event_bus = getattr(self.bridge, "event_bus", None)
        if event_bus is not None:
            payload = {
                "component": "dao.token_bridge.epoch_reward_scheduler",
                "stage": (
                    "reward_distribution_submitted"
                    if tx_hash
                    else "reward_distribution_blocked"
                ),
                "submitted_transaction": bool(tx_hash),
                "transaction_hash": tx_hash,
                "transaction_hash_hash": _hash_prefix(tx_hash),
                "stats_summary": self._stats_summary(stats),
                "uptime_summary": self._uptime_summary(uptimes_raw),
                "downstream_evidence": {
                    "event_ids": self.bridge.last_chain_write_event_ids,
                    "source_agents": [self.bridge.source_agent],
                    "payloads_redacted": True,
                },
                "chain_write_evidence": {
                    "payloads_redacted": True,
                    "settlement_finality_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                },
                "identity": dict(self.bridge.identity),
                "claim_boundary": TOKEN_BRIDGE_CLAIM_BOUNDARY,
            }
            event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.bridge.source_agent,
                payload,
                priority=5,
            )
