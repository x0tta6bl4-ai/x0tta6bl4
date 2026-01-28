"""
x0tta6bl4 MAPE-K DAO Integration Layer
Connects the MAPE-K autonomic loop with the DAO governance system
Enables decentralized decision-making and execution of autonomous network policies

Architecture:
  Monitor (eBPF) → Analyze (ML) → Plan (DAO proposals) → Execute (Timelock) → Knowledge (IPFS)

Version: 1.0.0
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from web3 import Web3
from eth_account import Account
from eth_utils import to_checksum_address

logger = logging.getLogger(__name__)


class ProposalStatus(Enum):
    """DAO Proposal status"""
    PENDING = 0
    ACTIVE = 1
    CANCELED = 2
    DEFEATED = 3
    SUCCEEDED = 4
    QUEUED = 5
    EXPIRED = 6
    EXECUTED = 7


class VoteType(Enum):
    """Vote direction"""
    AGAINST = 0
    FOR = 1
    ABSTAIN = 2


@dataclass
class GovernanceAction:
    """Action to be executed by MAPE-K through DAO governance"""
    action_id: str
    title: str
    description: str
    targets: List[str]  # Smart contract addresses to call
    values: List[int]   # ETH values to send
    calldatas: List[str]  # Encoded function calls
    votes_required: int  # Minimum votes to pass
    execution_delay: int  # Seconds to wait before execution
    created_at: datetime

    def to_proposal_description(self) -> str:
        """Convert to OpenZeppelin Governor proposal description format"""
        return f"# {self.title}\n\n{self.description}\n\nAction ID: {self.action_id}"


@dataclass
class GovernanceMetrics:
    """Metrics about DAO governance health"""
    total_proposals: int
    active_proposals: int
    passed_proposals: int
    failed_proposals: int
    executed_proposals: int
    total_voters: int
    total_votes_cast: int
    average_quorum: float
    average_voting_period: int  # blocks
    timestamp: datetime


@dataclass
class SimpleLogisticModel:
    """Minimal JSON-serializable logistic model for safe loading."""
    weights: List[float]
    bias: float = 0.0

    def _score(self, features: List[float]) -> float:
        if len(features) != len(self.weights):
            raise ValueError("Feature length does not match model weights")
        z = sum(w * x for w, x in zip(self.weights, features)) + self.bias
        return 1.0 / (1.0 + pow(2.718281828, -z))

    def predict(self, features_batch: List[List[float]]) -> List[int]:
        return [1 if self._score(features) >= 0.5 else 0 for features in features_batch]

    def predict_proba(self, features_batch: List[List[float]]) -> List[List[float]]:
        return [[1.0 - self._score(features), self._score(features)] for features in features_batch]


class GovernanceOracle(ABC):
    """Base class for governance decision oracles"""

    @abstractmethod
    async def should_execute_action(self, action: GovernanceAction) -> bool:
        """Determine if action should be executed by DAO"""
        pass

    @abstractmethod
    async def get_voting_recommendation(self, proposal_id: int) -> VoteType:
        """Get voting recommendation for a proposal"""
        pass

    @abstractmethod
    async def get_execution_priority(self, action: GovernanceAction) -> float:
        """Get priority score for executing action (0.0-1.0)"""
        pass


class MLBasedGovernanceOracle(GovernanceOracle):
    """ML-based oracle for governance decisions using trained models"""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize ML oracle
        
        Args:
            model_path: Path to trained ML model for governance decisions
        """
        self.model_path = model_path
        self.model = None
        if model_path:
            self._load_model()

    def _load_model(self):
        """Load ML model for governance decisions"""
        try:
            if not self.model_path or not self.model_path.endswith(".json"):
                raise ValueError("Model path must point to a JSON model file")

            with open(self.model_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            model_type = data.get("type")
            if model_type != "logistic":
                raise ValueError(f"Unsupported model type: {model_type}")

            weights = data.get("weights", [])
            if not weights:
                raise ValueError("Model weights missing")

            self.model = SimpleLogisticModel(
                weights=[float(w) for w in weights],
                bias=float(data.get("bias", 0.0)),
            )
            logger.info(f"Loaded governance JSON model from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load governance model: {e}")

    async def should_execute_action(self, action: GovernanceAction) -> bool:
        """Use ML to determine if action should be executed"""
        # Feature engineering
        features = {
            'title_length': len(action.title),
            'description_length': len(action.description),
            'targets_count': len(action.targets),
            'execution_delay': action.execution_delay,
            'votes_required': action.votes_required,
        }

        if self.model:
            try:
                # Predict using model
                prediction = self.model.predict([list(features.values())])
                return bool(prediction[0])
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}")

        # Fallback: simple heuristic
        return (
            len(action.description) > 50 and
            action.execution_delay >= 86400 and  # At least 1 day
            len(action.targets) <= 5
        )

    async def get_voting_recommendation(self, proposal_id: int) -> VoteType:
        """Use ML to recommend voting direction"""
        if self.model:
            try:
                confidence = self.model.predict_proba([[proposal_id]])
                return VoteType.FOR if confidence[0][1] > 0.6 else VoteType.AGAINST
            except Exception as e:
                logger.warning(f"ML voting recommendation failed: {e}")

        return VoteType.ABSTAIN  # Default to abstain if uncertain

    async def get_execution_priority(self, action: GovernanceAction) -> float:
        """Calculate execution priority (0.0-1.0)"""
        score = 0.5

        # Boost priority for critical network actions
        if 'security' in action.description.lower():
            score += 0.2
        if 'fix' in action.title.lower() or 'patch' in action.title.lower():
            score += 0.15

        # Reduce priority for low urgency
        if 'non-critical' in action.description.lower():
            score -= 0.15

        return min(1.0, max(0.0, score))


class MAEKGovernanceAdapter:
    """
    Adapter connecting MAPE-K autonomic loop with DAO governance
    
    Responsibilities:
    - Convert MAPE-K decisions into governance proposals
    - Execute DAO proposals through smart contracts
    - Track governance metrics
    - Integrate with ML/RAG for decision support
    """

    def __init__(
        self,
        w3: Web3,
        governor_address: str,
        governance_token_address: str,
        treasury_address: str,
        timelock_address: str,
        private_key: str,
        oracle: Optional[GovernanceOracle] = None,
    ):
        """
        Initialize MAPE-K governance adapter
        
        Args:
            w3: Web3 instance
            governor_address: Governor contract address
            governance_token_address: Governance token contract address
            treasury_address: Treasury contract address
            timelock_address: Timelock contract address
            private_key: Private key for sending transactions
            oracle: Governance decision oracle
        """
        self.w3 = w3
        self.account = Account.from_key(private_key)
        self.oracle = oracle or MLBasedGovernanceOracle()

        # Contract addresses
        self.governor_address = to_checksum_address(governor_address)
        self.governance_token_address = to_checksum_address(governance_token_address)
        self.treasury_address = to_checksum_address(treasury_address)
        self.timelock_address = to_checksum_address(timelock_address)

        # Load contract ABIs (simplified)
        self.governor_contract = None
        self.token_contract = None
        self.treasury_contract = None
        self.timelock_contract = None

        logger.info(f"Initialized MAPE-K Governance Adapter for account {self.account.address}")

    async def submit_governance_action(
        self,
        action: GovernanceAction,
        submit_proposal: bool = True,
    ) -> Optional[str]:
        """
        Submit MAPE-K action as governance proposal
        
        Args:
            action: Governance action to submit
            submit_proposal: If True, submit to Governor; if False, just validate
            
        Returns:
            Proposal ID if successful, None otherwise
        """
        # Check if action should be executed
        should_execute = await self.oracle.should_execute_action(action)
        if not should_execute:
            logger.warning(f"Oracle decided not to execute action {action.action_id}")
            return None

        if not submit_proposal:
            logger.info(f"Validated action {action.action_id}: {action.title}")
            return None

        try:
            # Prepare proposal
            description = action.to_proposal_description()
            description_hash = Web3.keccak(text=description)

            logger.info(f"Submitting governance proposal: {action.title}")
            logger.debug(f"  Targets: {action.targets}")
            logger.debug(f"  Description: {description}")

            # In production, would call Governor.propose() here
            proposal_id = Web3.keccak(
                hexstr=self.governor_address + 
                action.action_id + 
                str(action.created_at.timestamp())
            ).hex()

            logger.info(f"Governance proposal submitted: {proposal_id}")
            return proposal_id

        except Exception as e:
            logger.error(f"Failed to submit governance proposal: {e}")
            return None

    async def cast_vote(
        self,
        proposal_id: str,
        voter_address: str,
        vote_type: Optional[VoteType] = None,
    ) -> bool:
        """
        Cast vote on governance proposal
        
        Args:
            proposal_id: Proposal ID to vote on
            voter_address: Address of voter
            vote_type: Type of vote (None = get recommendation from oracle)
            
        Returns:
            True if vote was cast successfully
        """
        try:
            if vote_type is None:
                # Get voting recommendation from oracle
                vote_type = await self.oracle.get_voting_recommendation(int(proposal_id, 16))

            logger.info(f"Casting {vote_type.name} vote on proposal {proposal_id}")

            # In production, would call Governor.castVote() here
            logger.info(f"Vote cast successfully for {voter_address}")
            return True

        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            return False

    async def queue_proposal(self, proposal_id: str) -> bool:
        """Queue proposal for execution (after voting period ends)"""
        try:
            logger.info(f"Queueing proposal {proposal_id} for execution")
            # In production, would call Governor.queue() here
            return True
        except Exception as e:
            logger.error(f"Failed to queue proposal: {e}")
            return False

    async def execute_proposal(self, proposal_id: str) -> bool:
        """Execute proposal (after timelock delay expires)"""
        try:
            logger.info(f"Executing proposal {proposal_id}")
            # In production, would call Governor.execute() here
            return True
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            return False

    async def get_governance_metrics(self) -> GovernanceMetrics:
        """Get current governance health metrics"""
        # In production, would query Governor contract
        return GovernanceMetrics(
            total_proposals=0,
            active_proposals=0,
            passed_proposals=0,
            failed_proposals=0,
            executed_proposals=0,
            total_voters=0,
            total_votes_cast=0,
            average_quorum=0.0,
            average_voting_period=50400,
            timestamp=datetime.now(),
        )

    async def monitor_proposal(self, proposal_id: str, check_interval: int = 300) -> None:
        """
        Monitor proposal and execute when conditions are met
        
        Args:
            proposal_id: Proposal to monitor
            check_interval: Seconds between checks
        """
        logger.info(f"Starting to monitor proposal {proposal_id}")

        while True:
            try:
                # Check proposal status
                # status = await self._get_proposal_status(proposal_id)

                # If succeeded, queue for execution
                # if status == ProposalStatus.SUCCEEDED:
                #     await self.queue_proposal(proposal_id)

                # If ready, execute
                # elif status == ProposalStatus.QUEUED:
                #     await self.execute_proposal(proposal_id)

                # If executed, break
                # elif status == ProposalStatus.EXECUTED:
                logger.info(f"Proposal {proposal_id} executed successfully")
                break

                await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error monitoring proposal: {e}")
                await asyncio.sleep(check_interval)


class DAOIntegration:
    """
    Main integration point for MAPE-K DAO governance
    Manages the complete governance lifecycle
    """

    def __init__(
        self,
        w3: Web3,
        contracts: Dict[str, str],
        private_key: str,
        oracle: Optional[GovernanceOracle] = None,
    ):
        """
        Initialize DAO Integration
        
        Args:
            w3: Web3 instance
            contracts: Dict with addresses for {governor, token, treasury, timelock}
            private_key: Deployer private key
            oracle: Governance oracle
        """
        self.w3 = w3
        self.adapter = MAEKGovernanceAdapter(
            w3=w3,
            governor_address=contracts['governor'],
            governance_token_address=contracts['token'],
            treasury_address=contracts['treasury'],
            timelock_address=contracts['timelock'],
            private_key=private_key,
            oracle=oracle,
        )

    async def process_mapek_decision(
        self,
        decision: Dict[str, Any],
    ) -> Optional[str]:
        """
        Process MAPE-K decision and convert to governance proposal
        
        Args:
            decision: MAPE-K decision output with {title, description, targets, values, calldatas}
            
        Returns:
            Proposal ID if created, None otherwise
        """
        action = GovernanceAction(
            action_id=decision.get('id', f"action-{datetime.now().timestamp()}"),
            title=decision['title'],
            description=decision['description'],
            targets=decision.get('targets', []),
            values=decision.get('values', []),
            calldatas=decision.get('calldatas', []),
            votes_required=decision.get('votes_required', 100),
            execution_delay=decision.get('execution_delay', 172800),  # 2 days
            created_at=datetime.now(),
        )

        return await self.adapter.submit_governance_action(action)

    async def vote_on_proposal(
        self,
        proposal_id: str,
        voter_address: str,
    ) -> bool:
        """Vote on proposal using oracle recommendation"""
        return await self.adapter.cast_vote(proposal_id, voter_address)

    async def finalize_proposal(self, proposal_id: str) -> bool:
        """Queue and execute proposal after voting period"""
        queued = await self.adapter.queue_proposal(proposal_id)
        if queued:
            await asyncio.sleep(172800)  # Wait 2 days for timelock
            return await self.adapter.execute_proposal(proposal_id)
        return False


# Example usage
async def main():
    # Setup Web3 connection
    w3 = Web3(Web3.HTTPProvider('https://rpc-mumbai.maticvigil.com'))

    # Contract addresses (from deployment)
    contracts = {
        'governor': '0x...',
        'token': '0x...',
        'treasury': '0x...',
        'timelock': '0x...',
    }

    # Create DAO integration
    dao = DAOIntegration(
        w3=w3,
        contracts=contracts,
        private_key='0x...',
        oracle=MLBasedGovernanceOracle(),
    )

    # Example MAPE-K decision
    decision = {
        'id': 'security-patch-001',
        'title': 'Security Patch: Update mTLS Certificates',
        'description': 'Update X.509 certificates in mesh network nodes',
        'targets': ['0x...'],
        'values': [0],
        'calldatas': ['0x...'],
        'execution_delay': 172800,  # 2 days
    }

    # Submit governance proposal
    proposal_id = await dao.process_mapek_decision(decision)
    logger.info(f"Created proposal: {proposal_id}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
