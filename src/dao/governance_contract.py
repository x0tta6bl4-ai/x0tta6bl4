"""
On-chain DAO Governance Integration for x0tta6bl4.

Provides Python interface to MeshGovernance smart contract.
"""
import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

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
        rpc_url: Optional[str] = None
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
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(__file__),
            "contracts/artifacts/contracts/MeshGovernance.sol/MeshGovernance.json"
        )
        
        if not os.path.exists(abi_path):
            # Try alternative path
            abi_path = os.path.join(
                os.path.dirname(__file__),
                "../dao/contracts/artifacts/contracts/MeshGovernance.sol/MeshGovernance.json"
            )
        
        if os.path.exists(abi_path):
            with open(abi_path) as f:
                abi = json.load(f)["abi"]
        else:
            logger.warning("Governance ABI not found, using minimal ABI")
            abi = self._get_minimal_abi()
        
        self.contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=abi
        )
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def _get_minimal_abi(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "type": "uint8"}],
                "name": "castVote",
                "outputs": [],
                "type": "function"
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
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def create_proposal(
        self,
        title: str,
        description: str,
        duration_seconds: int = 259200  # 3 days default
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
        if not self.account:
            raise ValueError("Private key required for creating proposals")
        
        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price
            
            tx = self.contract.functions.createProposal(
                title,
                description,
                duration_seconds
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get proposal ID from event or contract state
            proposal_count = self.contract.functions.proposalCount().call()
            proposal_id = proposal_count
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
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
        if not self.account:
            raise ValueError("Private key required for voting")
        
        if support not in [0, 1, 2]:
            raise ValueError("Support must be 0 (against), 1 (for), or 2 (abstain)")
        
        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price
            
            tx = self.contract.functions.castVote(proposal_id, support).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
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
                state=ProposalState(result[11])
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
        if not self.account:
            raise ValueError("Private key required for executing proposals")
        
        try:
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            gas_price = self.web3.eth.gas_price
            
            tx = self.contract.functions.executeProposal(proposal_id).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 300000,
                'gasPrice': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
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

