"""
On-chain DAO Governance Integration for x0tta6bl4.

Provides Python interface to MeshGovernance smart contract.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "governance-contract"

GOVERNANCE_CONTRACT_CLAIM_BOUNDARY = (
    "GovernanceContract chain-write event only. It records local identity, "
    "policy, and safe actuator state for governance proposal transactions; "
    "it is not proof of final live external settlement without a verified "
    "receipt and live RPC evidence."
)

# Try to import Web3
try:
    from web3 import Web3

    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("Web3 not installed. Governance contract features unavailable.")


class ProposalState(Enum):
    """Proposal states matching smart contract."""

    PENDING = 0
    ACTIVE = 1
    PASSED = 2
    REJECTED = 3
    EXECUTED = 4


@dataclass
class ProposalInfo:
    """Proposal information from smart contract."""

    id: int
    title: str
    description: str
    proposer: str
    start_time: int
    end_time: int
    yes_votes: int
    no_votes: int
    abstain_votes: int
    total_voting_power: int
    executed: bool
    state: ProposalState


class GovernanceContract:
    """
    Python interface to MeshGovernance smart contract.

    Provides high-level methods for:
    - Creating proposals
    - Voting on proposals
    - Executing proposals
    - Querying proposal state
    """

    def __init__(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        *,
        node_id: str = "governance-contract",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[SafeActuator] = None,
    ):
        """
        Initialize governance contract interface.

        Args:
            contract_address: MeshGovernance contract address
            token_address: X0TToken contract address
            private_key: Private key for transactions (optional)
            rpc_url: RPC endpoint URL
        """
        if not WEB3_AVAILABLE:
            raise ImportError("web3.py required for governance contract")

        self.contract_address = contract_address
        self.token_address = token_address
        self.rpc_url = rpc_url or os.getenv("RPC_URL")
        if not self.rpc_url:
            raise ValueError("RPC_URL must be provided via environment or parameter")
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
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
            else self._env_bool("X0TTA6BL4_GOVERNANCE_CONTRACT_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="governance-contract")
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
        self.safe_actuator = safe_actuator or SafeActuator(
            self._execute_chain_write_through_actuator
        )
        self._last_chain_write_result: Any = None
        self._last_chain_write_exception: Optional[BaseException] = None

        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {self.rpc_url}")

        # Load contract ABI
        import json

        base_dir = os.path.dirname(__file__)
        # Try multiple possible artifact locations
        possible_paths = [
            os.path.join(base_dir, "contracts/artifacts/contracts/MeshGovernance.sol/MeshGovernance.json"),
            os.path.join(base_dir, "artifacts/contracts/MeshGovernance.sol/MeshGovernance.json"),
        ]
        
        abi_path = None
        for path in possible_paths:
            if os.path.exists(path):
                abi_path = path
                break
        
        if abi_path is None:
            # Try Governor artifact if available (new contract name)
            governor_path = os.path.join(base_dir, "contracts/artifacts/contracts/Governor.sol/X0TTA6BL4Governor.json")
            if os.path.exists(governor_path):
                abi_path = governor_path
            else:
                logger.warning("Governance ABI not found in any location, using minimal ABI")
                abi = self._get_minimal_abi()
                self.contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(contract_address), abi=abi
                )
                return
        
        # Load ABI from found path
        with open(abi_path) as f:
            abi = json.load(f)["abi"]

        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(contract_address), abi=abi
        )

        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(
                f"Governance contract initialized with account: {self.account.address}"
            )
        else:
            logger.warning("No private key provided - read-only mode")

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
            logger.error("Failed to initialize GovernanceContract EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize GovernanceContract policy engine: %s", exc)
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
    def _operation_resource_name(operation: str) -> str:
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
        operation_resource = self._operation_resource_name(operation)
        payload = {
            "component": "dao.governance_contract",
            "stage": stage,
            "operation": operation,
            "operation_resource": operation_resource,
            "resource": f"dao:governance_contract:{operation_resource}",
            "contract_address": self.contract_address,
            "token_address": self.token_address,
            "chain_rpc_configured": bool(self.rpc_url),
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
            "claim_boundary": GOVERNANCE_CONTRACT_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=8)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish GovernanceContract chain-write event: %s", exc)
            return None

    def _evaluate_chain_write_policy(self, operation: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "GovernanceContract policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "GovernanceContract SPIFFE identity is required for policy evaluation"
        operation_resource = self._operation_resource_name(operation)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"dao:governance_contract:{operation_resource}",
                workload_type="governance-contract",
            )
        except Exception as exc:
            return False, None, f"GovernanceContract policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, (
                self._policy_reason(decision) or "GovernanceContract policy denied chain write"
            )
        return True, decision, self._policy_reason(decision)

    @staticmethod
    def _chain_write_transaction_hash(raw: Any) -> Optional[str]:
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            tx_hash = raw.get("tx_hash")
            return str(tx_hash) if tx_hash else None
        return None

    @staticmethod
    def _chain_write_success(raw: Any) -> bool:
        if isinstance(raw, dict):
            return bool(raw.get("success", raw.get("ok", raw.get("tx_hash") is not None)))
        return raw is not None

    def _execute_chain_write_through_actuator(
        self,
        operation: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        self._last_chain_write_result = None
        self._last_chain_write_exception = None
        try:
            if operation == "create_proposal":
                raw = self._create_proposal_internal(
                    str(context.get("title", "")),
                    str(context.get("description", "")),
                    int(context.get("duration_seconds", 0)),
                )
            elif operation == "cast_vote":
                raw = self._cast_vote_internal(
                    int(context.get("proposal_id", 0)),
                    int(context.get("support", -1)),
                )
            elif operation == "execute_proposal":
                raw = self._execute_proposal_internal(int(context.get("proposal_id", 0)))
            else:
                return SafeActuatorResult(False, f"unknown GovernanceContract operation: {operation}")
        except BaseException as exc:
            self._last_chain_write_exception = exc
            return SafeActuatorResult(False, str(exc))

        self._last_chain_write_result = raw
        return SafeActuatorResult(
            self._chain_write_success(raw),
            "" if self._chain_write_success(raw) else f"{operation} returned no transaction result",
        )

    def _run_chain_write(self, operation: str, context: Dict[str, Any]) -> Any:
        self._last_chain_write_result = None
        self._last_chain_write_exception = None
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
            raise PermissionError(policy_reason)

        self._publish_chain_write_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            operation=operation,
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )
        actuator_result = self.safe_actuator.execute(operation, context)
        raw = self._last_chain_write_result
        transaction_hash = self._chain_write_transaction_hash(raw)
        if self._last_chain_write_exception is not None:
            self._publish_chain_write_event(
                EventType.TASK_FAILED,
                stage="actuator_failed",
                operation=operation,
                context=context,
                reason=str(self._last_chain_write_exception),
                policy_decision=policy_decision,
                success=False,
                transaction_hash=None,
                simulated=False,
            )
            raise self._last_chain_write_exception

        if actuator_result.simulated:
            self._publish_chain_write_event(
                EventType.TASK_FAILED,
                stage="actuator_simulated",
                operation=operation,
                context=context,
                reason=actuator_result.reason or "safe actuator returned simulated result",
                policy_decision=policy_decision,
                success=False,
                transaction_hash=None,
                simulated=True,
            )
            raise RuntimeError(actuator_result.reason or "safe actuator returned simulated result")

        if not actuator_result.success:
            self._publish_chain_write_event(
                EventType.TASK_FAILED,
                stage="actuator_failed",
                operation=operation,
                context=context,
                reason=actuator_result.reason,
                policy_decision=policy_decision,
                success=False,
                transaction_hash=None,
                simulated=False,
            )
            raise RuntimeError(actuator_result.reason or f"{operation} failed")

        self._publish_chain_write_event(
            EventType.PIPELINE_STAGE_END,
            stage="actuator_completed",
            operation=operation,
            context=context,
            reason=actuator_result.reason or policy_reason,
            policy_decision=policy_decision,
            success=True,
            transaction_hash=transaction_hash,
            simulated=False,
        )
        return raw

    def _get_minimal_abi(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [
                    {"name": "title", "type": "string"},
                    {"name": "description", "type": "string"},
                    {"name": "duration", "type": "uint256"},
                ],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function",
            },
            {
                "inputs": [
                    {"name": "proposalId", "type": "uint256"},
                    {"name": "support", "type": "uint8"},
                ],
                "name": "castVote",
                "outputs": [],
                "type": "function",
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}],
                "name": "getProposal",
                "outputs": [
                    {"name": "id", "type": "uint256"},
                    {"name": "title", "type": "string"},
                    {"name": "description", "type": "string"},
                    {"name": "proposer", "type": "address"},
                    {"name": "startTime", "type": "uint256"},
                    {"name": "endTime", "type": "uint256"},
                    {"name": "yesVotes", "type": "uint256"},
                    {"name": "noVotes", "type": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"},
                ],
                "type": "function",
                "stateMutability": "view",
            },
        ]

    def create_proposal(
        self,
        title: str,
        description: str,
        duration_seconds: int = 259200,  # 3 days default
    ) -> int:
        """
        Create a new governance proposal on-chain.

        Args:
            title: Proposal title
            description: Proposal description
            duration_seconds: Voting duration in seconds

        Returns:
            Proposal ID
        """
        raw = self._run_chain_write(
            "create_proposal",
            {
                "title": title,
                "description": description,
                "duration_seconds": duration_seconds,
            },
        )
        return int(raw["proposal_id"] if isinstance(raw, dict) else raw)

    def _create_proposal_internal(
        self,
        title: str,
        description: str,
        duration_seconds: int,
    ) -> Dict[str, Any]:
        if not self.account:
            raise ValueError("Private key required for creating proposals")

        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price

            tx = self.contract.functions.createProposal(
                title, description, duration_seconds
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 500000,
                    "gasPrice": gas_price,
                }
            )

            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            self.web3.eth.wait_for_transaction_receipt(tx_hash)

            # Get proposal ID from event or contract state
            proposal_count = self.contract.functions.proposalCount().call()
            proposal_id = proposal_count

            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return {"proposal_id": proposal_id, "tx_hash": tx_hash.hex()}

        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise

    def cast_vote(self, proposal_id: int, support: int) -> str:
        """
        Cast a vote on a proposal.

        Args:
            proposal_id: Proposal ID
            support: 0 = against, 1 = for, 2 = abstain

        Returns:
            Transaction hash
        """
        raw = self._run_chain_write(
            "cast_vote",
            {
                "proposal_id": proposal_id,
                "support": support,
            },
        )
        return str(raw)

    def _cast_vote_internal(self, proposal_id: int, support: int) -> str:
        if not self.account:
            raise ValueError("Private key required for voting")

        if support not in [0, 1, 2]:
            raise ValueError("Support must be 0 (against), 1 (for), or 2 (abstain)")

        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price

            tx = self.contract.functions.castVote(
                proposal_id, support
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 200000,
                    "gasPrice": gas_price,
                }
            )

            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            self.web3.eth.wait_for_transaction_receipt(tx_hash)

            logger.info(
                f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})"
            )
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise

    def get_proposal(self, proposal_id: int) -> ProposalInfo:
        """
        Get proposal information from contract.

        Args:
            proposal_id: Proposal ID

        Returns:
            ProposalInfo object
        """
        try:
            result = self.contract.functions.getProposal(proposal_id).call()

            return ProposalInfo(
                id=result[0],
                title=result[1],
                description=result[2],
                proposer=result[3],
                start_time=result[4],
                end_time=result[5],
                yes_votes=result[6],
                no_votes=result[7],
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11]),
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise

    def get_voting_power(self, address: str) -> int:
        """
        Get voting power of an address.

        Args:
            address: Ethereum address

        Returns:
            Voting power (based on staked tokens)
        """
        try:
            power = self.contract.functions.getVotingPower(address).call()
            return power
        except Exception as e:
            logger.error(f"Failed to get voting power: {e}")
            return 0

    def can_execute(self, proposal_id: int) -> bool:
        """
        Check if proposal can be executed.

        Args:
            proposal_id: Proposal ID

        Returns:
            True if proposal can be executed
        """
        try:
            return self.contract.functions.canExecute(proposal_id).call()
        except Exception as e:
            logger.error(f"Failed to check execution status: {e}")
            return False

    def execute_proposal(self, proposal_id: int) -> str:
        """
        Execute a passed proposal.

        Args:
            proposal_id: Proposal ID

        Returns:
            Transaction hash
        """
        raw = self._run_chain_write(
            "execute_proposal",
            {
                "proposal_id": proposal_id,
            },
        )
        return str(raw)

    def _execute_proposal_internal(self, proposal_id: int) -> str:
        if not self.account:
            raise ValueError("Private key required for executing proposals")

        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price

            tx = self.contract.functions.executeProposal(proposal_id).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": nonce,
                    "gas": 300000,
                    "gasPrice": gas_price,
                }
            )

            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            self.web3.eth.wait_for_transaction_receipt(tx_hash)

            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise

    def get_proposal_count(self) -> int:
        """Get total number of proposals."""
        try:
            return self.contract.functions.proposalCount().call()
        except Exception as e:
            logger.error(f"Failed to get proposal count: {e}")
            return 0
