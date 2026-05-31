"""
x0tta6bl4 Token Rewards System.
Handles distributing X0T tokens for relay traffic and uptime.
Supports both local simulation and real Base Sepolia transactions.
"""

import hashlib
import logging
import os
import warnings
from decimal import Decimal
from typing import Any, Optional

from src.services.reward_events import publish_reward_settlement_event

logger = logging.getLogger(__name__)

Web3: Any = None
WEB3_AVAILABLE: Optional[bool] = None


def _get_web3_class() -> Any:
    global Web3, WEB3_AVAILABLE
    if WEB3_AVAILABLE is False:
        return None
    if Web3 is not None:
        return Web3
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"websockets\.legacy is deprecated.*",
                category=DeprecationWarning,
            )
            from web3 import Web3 as imported_web3
    except ImportError:
        WEB3_AVAILABLE = False
        logger.info("Web3 not installed. Using local accounting mode.")
        return None

    Web3 = imported_web3
    WEB3_AVAILABLE = True
    return Web3

# Base Sepolia RPC - should be configured via environment
BASE_SEPOLIA_RPC = os.getenv("RPC_URL", "")

# Minimal ERC20 ABI for transfer
ERC20_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]
_UNSET = object()
REWARD_RATE_XOT_PER_PACKET = Decimal("0.0001")


class TokenRewards:
    """Rewards manager for Mesh Nodes. Supports real blockchain transactions."""

    def __init__(
        self,
        contract_address: str,
        private_key: Optional[str] | object = _UNSET,
        rpc_url: Optional[str] = None,
        event_bus: Any = None,
        event_project_root: str = ".",
        source_agent: str = "token-rewards",
        node_id: Optional[str] = None,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ):
        self.contract_address = contract_address
        if private_key is _UNSET:
            use_env_key = (
                os.getenv("TOKEN_REWARDS_USE_ENV_KEY", "false").strip().lower()
                == "true"
            )
            self.private_key = os.getenv("OPERATOR_PRIVATE_KEY") if use_env_key else None
        else:
            self.private_key = private_key
        self.rpc_url = rpc_url or os.getenv("RPC_URL", BASE_SEPOLIA_RPC)
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = source_agent
        self.node_id = node_id
        self.spiffe_id = spiffe_id
        self.did = did
        self.wallet_address = wallet_address

        self.total_distributed = Decimal("0.0")
        self.pending_rewards = Decimal("0.0")
        self.tx_history = []

        # Local state (always maintained)
        self.balance = Decimal("1000.0")
        self.daily_earnings = Decimal("0.0")

        # Initialize Web3 if available and configured
        self.web3 = None
        self.contract = None
        self.account = None

        web3_class = _get_web3_class() if self.private_key else None
        if web3_class is not None and self.private_key:
            try:
                self.web3 = web3_class(web3_class.HTTPProvider(self.rpc_url))
                self.contract = self.web3.eth.contract(
                    address=web3_class.to_checksum_address(contract_address),
                    abi=ERC20_ABI,
                )
                self.account = self.web3.eth.account.from_key(self.private_key)
                logger.info(f"🔗 Blockchain connected: {self.rpc_url}")
                logger.info(f"   Wallet: {self.account.address}")
            except Exception as e:
                logger.error(f"Failed to initialize Web3: {e}")
                self.web3 = None

    @staticmethod
    def _hash_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _reward_evidence_metadata(
        self,
        *,
        result: dict,
        node_address: str,
        packets: Optional[int],
        calculation_metadata: Any = None,
    ) -> dict:
        metadata = dict(calculation_metadata or {}) if isinstance(calculation_metadata, dict) else {}
        metadata.update(
            {
                "component": "dao.token_rewards",
                "calculator": metadata.get("calculator") or "TokenRewards.reward_relay",
                "settlement_status": result.get("status"),
                "settlement_recorded": result.get("settlement_recorded"),
                "local_accounting_recorded": result.get("local_accounting_recorded"),
                "submitted_transaction": result.get("submitted_transaction"),
                "simulated": result.get("simulated"),
                "packets": packets,
                "amount_xot": result.get("amount"),
                "reward_rate_xot_per_packet": str(REWARD_RATE_XOT_PER_PACKET),
                "node_address_hash": self._hash_value(node_address),
                "contract_address_hash": self._hash_value(self.contract_address),
                "blockchain_configured": bool(self.web3 and self.contract and self.account),
                "pending_after_xot": str(self.pending_rewards),
                "balance_after_xot": str(self.balance),
                "total_distributed_after_xot": str(self.total_distributed),
            }
        )
        return metadata

    def reward_relay(
        self,
        node_address: str,
        packets: int,
        *,
        upstream_event_ids: Any = None,
        upstream_source_agents: Any = None,
        upstream_claim_gate: Any = None,
        upstream_cross_plane_claim_gate: Any = None,
    ):
        """Calculate and queue reward for relayed packets."""
        return self.reward_relay_with_evidence(
            node_address,
            packets,
            upstream_event_ids=upstream_event_ids,
            upstream_source_agents=upstream_source_agents,
            upstream_claim_gate=upstream_claim_gate,
            upstream_cross_plane_claim_gate=upstream_cross_plane_claim_gate,
        )

    def reward_relay_with_evidence(
        self,
        node_address: str,
        packets: int,
        *,
        upstream_event_ids: Any = None,
        upstream_source_agents: Any = None,
        upstream_claim_gate: Any = None,
        upstream_cross_plane_claim_gate: Any = None,
    ):
        """Calculate and queue reward for relayed packets with upstream trace IDs."""
        # Rate: 0.0001 X0T per packet
        reward = Decimal(packets) * REWARD_RATE_XOT_PER_PACKET
        self.pending_rewards += reward
        self.daily_earnings += reward

        logger.info(f"💰 Reward queued: {reward:.4f} X0T for {packets} packets")

        calculation_metadata = {
            "calculator": "TokenRewards.reward_relay",
            "packets": packets,
            "calculated_reward_xot": str(reward),
            "reward_rate_xot_per_packet": str(REWARD_RATE_XOT_PER_PACKET),
            "pending_queued_before_settlement_xot": str(self.pending_rewards),
        }
        # Settle rewards (local + blockchain if configured)
        return self._settle_rewards(
            node_address,
            packets=packets,
            upstream_event_ids=upstream_event_ids,
            upstream_source_agents=upstream_source_agents,
            upstream_claim_gate=upstream_claim_gate,
            upstream_cross_plane_claim_gate=upstream_cross_plane_claim_gate,
            calculation_metadata=calculation_metadata,
        )

    def _publish_settlement_event(
        self,
        result: dict,
        node_address: str,
        packets: Optional[int] = None,
        upstream_event_ids: Any = None,
        upstream_source_agents: Any = None,
        calculation_metadata: Any = None,
        upstream_claim_gate: Any = None,
        upstream_cross_plane_claim_gate: Any = None,
    ) -> dict:
        if self.event_bus is None:
            return result
        evidence_metadata = self._reward_evidence_metadata(
            result=result,
            node_address=node_address,
            packets=packets,
            calculation_metadata=calculation_metadata,
        )
        transition = "recorded" if result.get("ok") is True else "blocked"
        event_id = publish_reward_settlement_event(
            transition=transition,
            source_agent=self.source_agent,
            node_address=node_address,
            node_id=self.node_id,
            spiffe_id=self.spiffe_id,
            did=self.did,
            wallet_address=self.wallet_address,
            packets=packets,
            amount=result.get("amount"),
            status=result.get("status"),
            submitted_transaction=result.get("submitted_transaction"),
            simulated=result.get("simulated"),
            settlement_recorded=result.get("settlement_recorded"),
            local_accounting_recorded=result.get("local_accounting_recorded"),
            transaction_hash=result.get("transaction_hash"),
            upstream_event_ids=upstream_event_ids,
            upstream_source_agents=upstream_source_agents,
            upstream_claim_gate=upstream_claim_gate,
            upstream_cross_plane_claim_gate=upstream_cross_plane_claim_gate,
            evidence_metadata=evidence_metadata,
            reason=str(result.get("error") or result.get("status") or ""),
            event_bus=self.event_bus,
            project_root=self.event_project_root,
        )
        if event_id:
            result["event_id"] = event_id
        return result

    def _settle_rewards(
        self,
        node_address: str,
        packets: Optional[int] = None,
        *,
        upstream_event_ids: Any = None,
        upstream_source_agents: Any = None,
        calculation_metadata: Any = None,
        upstream_claim_gate: Any = None,
        upstream_cross_plane_claim_gate: Any = None,
    ):
        """Execute transfer - local always, blockchain if configured."""
        publish_kwargs = {
            "upstream_claim_gate": upstream_claim_gate,
            "upstream_cross_plane_claim_gate": upstream_cross_plane_claim_gate,
        }
        if self.pending_rewards <= 0:
            return self._publish_settlement_event({
                "ok": True,
                "status": "noop",
                "settlement_recorded": False,
                "local_accounting_recorded": False,
                "submitted_transaction": False,
                "simulated": self.web3 is None or self.contract is None or self.account is None,
                "amount": "0.0",
                "to": node_address,
                "transaction_hash": "",
            }, node_address, packets, upstream_event_ids, upstream_source_agents, calculation_metadata, **publish_kwargs)

        amount = self.pending_rewards
        self.balance += amount
        self.total_distributed += amount
        blockchain_configured = bool(self.web3 and self.contract and self.account)

        if not blockchain_configured:
            self.pending_rewards = Decimal("0.0")
            return self._publish_settlement_event({
                "ok": True,
                "status": "local_accounting_only",
                "settlement_recorded": True,
                "local_accounting_recorded": True,
                "submitted_transaction": False,
                "simulated": True,
                "amount": str(amount),
                "to": node_address,
                "transaction_hash": "",
            }, node_address, packets, upstream_event_ids, upstream_source_agents, calculation_metadata, **publish_kwargs)

        try:
            tx_hash = self._send_blockchain_reward(node_address, amount)
            if tx_hash:
                self.tx_history.append(
                    {
                        "hash": tx_hash,
                        "amount": str(amount),
                        "to": node_address,
                        "timestamp": __import__("time").time(),
                    }
                )
                logger.info(f"⛓️  Blockchain TX: {tx_hash}")
                self.pending_rewards = Decimal("0.0")
                return self._publish_settlement_event({
                    "ok": True,
                    "status": "blockchain_submitted",
                    "settlement_recorded": True,
                    "local_accounting_recorded": True,
                    "submitted_transaction": True,
                    "simulated": False,
                    "amount": str(amount),
                    "to": node_address,
                    "transaction_hash": tx_hash,
                }, node_address, packets, upstream_event_ids, upstream_source_agents, calculation_metadata, **publish_kwargs)
            self.pending_rewards = Decimal("0.0")
            return self._publish_settlement_event({
                "ok": False,
                "status": "blockchain_submission_failed",
                "settlement_recorded": False,
                "local_accounting_recorded": True,
                "submitted_transaction": False,
                "simulated": False,
                "amount": str(amount),
                "to": node_address,
                "transaction_hash": "",
                "error": "blockchain transaction hash was not returned",
            }, node_address, packets, upstream_event_ids, upstream_source_agents, calculation_metadata, **publish_kwargs)
        except Exception as e:
            logger.error(f"Blockchain TX failed: {e}")
            self.pending_rewards = Decimal("0.0")
            return self._publish_settlement_event({
                "ok": False,
                "status": "blockchain_submission_failed",
                "settlement_recorded": False,
                "local_accounting_recorded": True,
                "submitted_transaction": False,
                "simulated": False,
                "amount": str(amount),
                "to": node_address,
                "transaction_hash": "",
                "error": str(e),
            }, node_address, packets, upstream_event_ids, upstream_source_agents, calculation_metadata, **publish_kwargs)

    def _send_blockchain_reward(self, to_address: str, amount: Decimal) -> Optional[str]:
        """Send actual ERC20 transfer on Base Sepolia."""
        if not self.web3:
            return None
        web3_class = _get_web3_class()
        if web3_class is None:
            return None

        try:
            # Convert to wei (18 decimals)
            amount_wei = int(amount * Decimal("1e18"))

            # Build transaction
            nonce = self.web3.eth.get_transaction_count(self.account.address)

            tx = self.contract.functions.transfer(
                web3_class.to_checksum_address(to_address), amount_wei
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 100000,
                    "gasPrice": self.web3.eth.gas_price,
                    "chainId": 84532,  # Base Sepolia chain ID
                }
            )

            # Sign and send
            signed = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed.raw_transaction)

            return tx_hash.hex()
        except Exception as e:
            logger.error(f"Blockchain transfer error: {e}")
            return None

    def get_blockchain_balance(self) -> str:
        """Get real token balance from blockchain."""
        if self.web3 and self.contract and self.account:
            try:
                balance_wei = self.contract.functions.balanceOf(
                    self.account.address
                ).call()
                balance = Decimal(balance_wei) / Decimal("1e18")
                return f"{balance:.4f}"
            except Exception:
                pass
        return f"{self.balance:.4f}"

    def get_daily_earnings(self, node_address: str) -> str:
        return f"{self.daily_earnings:.4f}"

    def get_monthly_projection(self, node_address: str) -> str:
        # Simple projection: daily * 30
        return f"{self.daily_earnings * 30:.2f}"

    def get_balance(self, node_address: str) -> str:
        return f"{self.balance:.4f}"
