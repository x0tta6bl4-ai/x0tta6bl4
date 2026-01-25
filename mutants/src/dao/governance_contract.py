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
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


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
    
    def xǁGovernanceContractǁ__init____mutmut_orig(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_1(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "XXhttp://localhost:8545XX"
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
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_2(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "HTTP://LOCALHOST:8545"
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
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_3(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
    ):
        """
        Initialize governance contract interface.
        
        Args:
            contract_address: MeshGovernance contract address
            token_address: X0TToken contract address
            private_key: Private key for transactions (optional)
            rpc_url: RPC endpoint URL
        """
        if WEB3_AVAILABLE:
            raise ImportError("web3.py required for governance contract")
        
        self.contract_address = contract_address
        self.token_address = token_address
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_4(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
            raise ImportError(None)
        
        self.contract_address = contract_address
        self.token_address = token_address
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_5(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
            raise ImportError("XXweb3.py required for governance contractXX")
        
        self.contract_address = contract_address
        self.token_address = token_address
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_6(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
            raise ImportError("WEB3.PY REQUIRED FOR GOVERNANCE CONTRACT")
        
        self.contract_address = contract_address
        self.token_address = token_address
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_7(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        
        self.contract_address = None
        self.token_address = token_address
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_8(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.token_address = None
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_9(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = None
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
    
    def xǁGovernanceContractǁ__init____mutmut_10(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = None
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_11(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key and os.getenv("OPERATOR_PRIVATE_KEY")
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_12(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv(None)
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_13(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("XXOPERATOR_PRIVATE_KEYXX")
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_14(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("operator_private_key")
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_15(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = None
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
    
    def xǁGovernanceContractǁ__init____mutmut_16(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(None)
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
    
    def xǁGovernanceContractǁ__init____mutmut_17(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(None))
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
    
    def xǁGovernanceContractǁ__init____mutmut_18(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if self.web3.is_connected():
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
    
    def xǁGovernanceContractǁ__init____mutmut_19(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(None)
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_20(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = None
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_21(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            None,
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
    
    def xǁGovernanceContractǁ__init____mutmut_22(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(__file__),
            None
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
    
    def xǁGovernanceContractǁ__init____mutmut_23(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
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
    
    def xǁGovernanceContractǁ__init____mutmut_24(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(__file__),
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
    
    def xǁGovernanceContractǁ__init____mutmut_25(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(None),
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
    
    def xǁGovernanceContractǁ__init____mutmut_26(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(__file__),
            "XXcontracts/artifacts/contracts/MeshGovernance.sol/MeshGovernance.jsonXX"
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
    
    def xǁGovernanceContractǁ__init____mutmut_27(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(__file__),
            "contracts/artifacts/contracts/meshgovernance.sol/meshgovernance.json"
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
    
    def xǁGovernanceContractǁ__init____mutmut_28(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        
        # Initialize Web3
        self.web3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.web3.is_connected():
            raise ConnectionError(f"Could not connect to {rpc_url}")
        
        # Load contract ABI
        import json
        abi_path = os.path.join(
            os.path.dirname(__file__),
            "CONTRACTS/ARTIFACTS/CONTRACTS/MESHGOVERNANCE.SOL/MESHGOVERNANCE.JSON"
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
    
    def xǁGovernanceContractǁ__init____mutmut_29(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
        
        if os.path.exists(abi_path):
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
    
    def xǁGovernanceContractǁ__init____mutmut_30(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
        
        if not os.path.exists(None):
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
    
    def xǁGovernanceContractǁ__init____mutmut_31(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            abi_path = None
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_32(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                None,
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
    
    def xǁGovernanceContractǁ__init____mutmut_33(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                None
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
    
    def xǁGovernanceContractǁ__init____mutmut_34(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_35(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
    
    def xǁGovernanceContractǁ__init____mutmut_36(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                os.path.dirname(None),
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
    
    def xǁGovernanceContractǁ__init____mutmut_37(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                "XX../dao/contracts/artifacts/contracts/MeshGovernance.sol/MeshGovernance.jsonXX"
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
    
    def xǁGovernanceContractǁ__init____mutmut_38(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                "../dao/contracts/artifacts/contracts/meshgovernance.sol/meshgovernance.json"
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
    
    def xǁGovernanceContractǁ__init____mutmut_39(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                "../DAO/CONTRACTS/ARTIFACTS/CONTRACTS/MESHGOVERNANCE.SOL/MESHGOVERNANCE.JSON"
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
    
    def xǁGovernanceContractǁ__init____mutmut_40(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
        
        if os.path.exists(None):
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
    
    def xǁGovernanceContractǁ__init____mutmut_41(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            with open(None) as f:
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
    
    def xǁGovernanceContractǁ__init____mutmut_42(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                abi = None
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
    
    def xǁGovernanceContractǁ__init____mutmut_43(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                abi = json.load(None)["abi"]
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
    
    def xǁGovernanceContractǁ__init____mutmut_44(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                abi = json.load(f)["XXabiXX"]
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
    
    def xǁGovernanceContractǁ__init____mutmut_45(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
                abi = json.load(f)["ABI"]
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
    
    def xǁGovernanceContractǁ__init____mutmut_46(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning(None)
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
    
    def xǁGovernanceContractǁ__init____mutmut_47(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning("XXGovernance ABI not found, using minimal ABIXX")
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
    
    def xǁGovernanceContractǁ__init____mutmut_48(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning("governance abi not found, using minimal abi")
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
    
    def xǁGovernanceContractǁ__init____mutmut_49(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning("GOVERNANCE ABI NOT FOUND, USING MINIMAL ABI")
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
    
    def xǁGovernanceContractǁ__init____mutmut_50(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            abi = None
        
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
    
    def xǁGovernanceContractǁ__init____mutmut_51(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
        
        self.contract = None
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_52(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            address=None,
            abi=abi
        )
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_53(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            abi=None
        )
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_54(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            abi=abi
        )
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_55(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            )
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_56(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            address=Web3.to_checksum_address(None),
            abi=abi
        )
        
        # Set up account if private key provided
        self.account = None
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_57(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
        self.account = ""
        if self.private_key:
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_58(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            self.account = None
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_59(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            self.account = self.web3.eth.account.from_key(None)
            logger.info(f"Governance contract initialized with account: {self.account.address}")
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_60(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.info(None)
        else:
            logger.warning("No private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_61(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning(None)
    
    def xǁGovernanceContractǁ__init____mutmut_62(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning("XXNo private key provided - read-only modeXX")
    
    def xǁGovernanceContractǁ__init____mutmut_63(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning("no private key provided - read-only mode")
    
    def xǁGovernanceContractǁ__init____mutmut_64(
        self,
        contract_address: str,
        token_address: str,
        private_key: Optional[str] = None,
        rpc_url: str = "http://localhost:8545"
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
        self.rpc_url = rpc_url
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
            logger.warning("NO PRIVATE KEY PROVIDED - READ-ONLY MODE")
    
    xǁGovernanceContractǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁ__init____mutmut_1': xǁGovernanceContractǁ__init____mutmut_1, 
        'xǁGovernanceContractǁ__init____mutmut_2': xǁGovernanceContractǁ__init____mutmut_2, 
        'xǁGovernanceContractǁ__init____mutmut_3': xǁGovernanceContractǁ__init____mutmut_3, 
        'xǁGovernanceContractǁ__init____mutmut_4': xǁGovernanceContractǁ__init____mutmut_4, 
        'xǁGovernanceContractǁ__init____mutmut_5': xǁGovernanceContractǁ__init____mutmut_5, 
        'xǁGovernanceContractǁ__init____mutmut_6': xǁGovernanceContractǁ__init____mutmut_6, 
        'xǁGovernanceContractǁ__init____mutmut_7': xǁGovernanceContractǁ__init____mutmut_7, 
        'xǁGovernanceContractǁ__init____mutmut_8': xǁGovernanceContractǁ__init____mutmut_8, 
        'xǁGovernanceContractǁ__init____mutmut_9': xǁGovernanceContractǁ__init____mutmut_9, 
        'xǁGovernanceContractǁ__init____mutmut_10': xǁGovernanceContractǁ__init____mutmut_10, 
        'xǁGovernanceContractǁ__init____mutmut_11': xǁGovernanceContractǁ__init____mutmut_11, 
        'xǁGovernanceContractǁ__init____mutmut_12': xǁGovernanceContractǁ__init____mutmut_12, 
        'xǁGovernanceContractǁ__init____mutmut_13': xǁGovernanceContractǁ__init____mutmut_13, 
        'xǁGovernanceContractǁ__init____mutmut_14': xǁGovernanceContractǁ__init____mutmut_14, 
        'xǁGovernanceContractǁ__init____mutmut_15': xǁGovernanceContractǁ__init____mutmut_15, 
        'xǁGovernanceContractǁ__init____mutmut_16': xǁGovernanceContractǁ__init____mutmut_16, 
        'xǁGovernanceContractǁ__init____mutmut_17': xǁGovernanceContractǁ__init____mutmut_17, 
        'xǁGovernanceContractǁ__init____mutmut_18': xǁGovernanceContractǁ__init____mutmut_18, 
        'xǁGovernanceContractǁ__init____mutmut_19': xǁGovernanceContractǁ__init____mutmut_19, 
        'xǁGovernanceContractǁ__init____mutmut_20': xǁGovernanceContractǁ__init____mutmut_20, 
        'xǁGovernanceContractǁ__init____mutmut_21': xǁGovernanceContractǁ__init____mutmut_21, 
        'xǁGovernanceContractǁ__init____mutmut_22': xǁGovernanceContractǁ__init____mutmut_22, 
        'xǁGovernanceContractǁ__init____mutmut_23': xǁGovernanceContractǁ__init____mutmut_23, 
        'xǁGovernanceContractǁ__init____mutmut_24': xǁGovernanceContractǁ__init____mutmut_24, 
        'xǁGovernanceContractǁ__init____mutmut_25': xǁGovernanceContractǁ__init____mutmut_25, 
        'xǁGovernanceContractǁ__init____mutmut_26': xǁGovernanceContractǁ__init____mutmut_26, 
        'xǁGovernanceContractǁ__init____mutmut_27': xǁGovernanceContractǁ__init____mutmut_27, 
        'xǁGovernanceContractǁ__init____mutmut_28': xǁGovernanceContractǁ__init____mutmut_28, 
        'xǁGovernanceContractǁ__init____mutmut_29': xǁGovernanceContractǁ__init____mutmut_29, 
        'xǁGovernanceContractǁ__init____mutmut_30': xǁGovernanceContractǁ__init____mutmut_30, 
        'xǁGovernanceContractǁ__init____mutmut_31': xǁGovernanceContractǁ__init____mutmut_31, 
        'xǁGovernanceContractǁ__init____mutmut_32': xǁGovernanceContractǁ__init____mutmut_32, 
        'xǁGovernanceContractǁ__init____mutmut_33': xǁGovernanceContractǁ__init____mutmut_33, 
        'xǁGovernanceContractǁ__init____mutmut_34': xǁGovernanceContractǁ__init____mutmut_34, 
        'xǁGovernanceContractǁ__init____mutmut_35': xǁGovernanceContractǁ__init____mutmut_35, 
        'xǁGovernanceContractǁ__init____mutmut_36': xǁGovernanceContractǁ__init____mutmut_36, 
        'xǁGovernanceContractǁ__init____mutmut_37': xǁGovernanceContractǁ__init____mutmut_37, 
        'xǁGovernanceContractǁ__init____mutmut_38': xǁGovernanceContractǁ__init____mutmut_38, 
        'xǁGovernanceContractǁ__init____mutmut_39': xǁGovernanceContractǁ__init____mutmut_39, 
        'xǁGovernanceContractǁ__init____mutmut_40': xǁGovernanceContractǁ__init____mutmut_40, 
        'xǁGovernanceContractǁ__init____mutmut_41': xǁGovernanceContractǁ__init____mutmut_41, 
        'xǁGovernanceContractǁ__init____mutmut_42': xǁGovernanceContractǁ__init____mutmut_42, 
        'xǁGovernanceContractǁ__init____mutmut_43': xǁGovernanceContractǁ__init____mutmut_43, 
        'xǁGovernanceContractǁ__init____mutmut_44': xǁGovernanceContractǁ__init____mutmut_44, 
        'xǁGovernanceContractǁ__init____mutmut_45': xǁGovernanceContractǁ__init____mutmut_45, 
        'xǁGovernanceContractǁ__init____mutmut_46': xǁGovernanceContractǁ__init____mutmut_46, 
        'xǁGovernanceContractǁ__init____mutmut_47': xǁGovernanceContractǁ__init____mutmut_47, 
        'xǁGovernanceContractǁ__init____mutmut_48': xǁGovernanceContractǁ__init____mutmut_48, 
        'xǁGovernanceContractǁ__init____mutmut_49': xǁGovernanceContractǁ__init____mutmut_49, 
        'xǁGovernanceContractǁ__init____mutmut_50': xǁGovernanceContractǁ__init____mutmut_50, 
        'xǁGovernanceContractǁ__init____mutmut_51': xǁGovernanceContractǁ__init____mutmut_51, 
        'xǁGovernanceContractǁ__init____mutmut_52': xǁGovernanceContractǁ__init____mutmut_52, 
        'xǁGovernanceContractǁ__init____mutmut_53': xǁGovernanceContractǁ__init____mutmut_53, 
        'xǁGovernanceContractǁ__init____mutmut_54': xǁGovernanceContractǁ__init____mutmut_54, 
        'xǁGovernanceContractǁ__init____mutmut_55': xǁGovernanceContractǁ__init____mutmut_55, 
        'xǁGovernanceContractǁ__init____mutmut_56': xǁGovernanceContractǁ__init____mutmut_56, 
        'xǁGovernanceContractǁ__init____mutmut_57': xǁGovernanceContractǁ__init____mutmut_57, 
        'xǁGovernanceContractǁ__init____mutmut_58': xǁGovernanceContractǁ__init____mutmut_58, 
        'xǁGovernanceContractǁ__init____mutmut_59': xǁGovernanceContractǁ__init____mutmut_59, 
        'xǁGovernanceContractǁ__init____mutmut_60': xǁGovernanceContractǁ__init____mutmut_60, 
        'xǁGovernanceContractǁ__init____mutmut_61': xǁGovernanceContractǁ__init____mutmut_61, 
        'xǁGovernanceContractǁ__init____mutmut_62': xǁGovernanceContractǁ__init____mutmut_62, 
        'xǁGovernanceContractǁ__init____mutmut_63': xǁGovernanceContractǁ__init____mutmut_63, 
        'xǁGovernanceContractǁ__init____mutmut_64': xǁGovernanceContractǁ__init____mutmut_64
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁGovernanceContractǁ__init____mutmut_orig)
    xǁGovernanceContractǁ__init____mutmut_orig.__name__ = 'xǁGovernanceContractǁ__init__'
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_orig(self) -> List[Dict]:
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_1(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "XXinputsXX": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_2(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "INPUTS": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_3(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"XXnameXX": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_4(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"NAME": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_5(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "XXtitleXX", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_6(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "TITLE", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_7(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "XXtypeXX": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_8(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "TYPE": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_9(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "XXstringXX"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_10(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "STRING"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_11(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"XXnameXX": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_12(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"NAME": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_13(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "XXdescriptionXX", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_14(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "DESCRIPTION", "type": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_15(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "XXtypeXX": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_16(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "TYPE": "string"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_17(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "XXstringXX"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_18(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "STRING"}, {"name": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_19(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"XXnameXX": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_20(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"NAME": "duration", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_21(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "XXdurationXX", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_22(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "DURATION", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_23(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "XXtypeXX": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_24(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "TYPE": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_25(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "XXuint256XX"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_26(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "UINT256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_27(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "XXnameXX": "createProposal",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_28(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "NAME": "createProposal",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_29(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "XXcreateProposalXX",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_30(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createproposal",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_31(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "CREATEPROPOSAL",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_32(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "XXoutputsXX": [{"name": "", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_33(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "OUTPUTS": [{"name": "", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_34(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"XXnameXX": "", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_35(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"NAME": "", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_36(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "XXXX", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_37(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "XXtypeXX": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_38(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "TYPE": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_39(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "XXuint256XX"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_40(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "UINT256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_41(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "XXtypeXX": "function"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_42(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "TYPE": "function"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_43(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "XXfunctionXX"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_44(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "FUNCTION"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_45(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "XXinputsXX": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_46(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "INPUTS": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_47(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"XXnameXX": "proposalId", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_48(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"NAME": "proposalId", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_49(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "XXproposalIdXX", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_50(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalid", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_51(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "PROPOSALID", "type": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_52(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "XXtypeXX": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_53(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "TYPE": "uint256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_54(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "XXuint256XX"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_55(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "UINT256"}, {"name": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_56(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"XXnameXX": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_57(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"NAME": "support", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_58(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "XXsupportXX", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_59(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "SUPPORT", "type": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_60(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "XXtypeXX": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_61(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "TYPE": "uint8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_62(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "type": "XXuint8XX"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_63(self) -> List[Dict]:
        """Minimal ABI for governance contract."""
        return [
            {
                "inputs": [{"name": "title", "type": "string"}, {"name": "description", "type": "string"}, {"name": "duration", "type": "uint256"}],
                "name": "createProposal",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "proposalId", "type": "uint256"}, {"name": "support", "type": "UINT8"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_64(self) -> List[Dict]:
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
                "XXnameXX": "castVote",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_65(self) -> List[Dict]:
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
                "NAME": "castVote",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_66(self) -> List[Dict]:
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
                "name": "XXcastVoteXX",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_67(self) -> List[Dict]:
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
                "name": "castvote",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_68(self) -> List[Dict]:
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
                "name": "CASTVOTE",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_69(self) -> List[Dict]:
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
                "XXoutputsXX": [],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_70(self) -> List[Dict]:
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
                "OUTPUTS": [],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_71(self) -> List[Dict]:
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
                "XXtypeXX": "function"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_72(self) -> List[Dict]:
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
                "TYPE": "function"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_73(self) -> List[Dict]:
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
                "type": "XXfunctionXX"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_74(self) -> List[Dict]:
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
                "type": "FUNCTION"
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_75(self) -> List[Dict]:
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
                "XXinputsXX": [{"name": "proposalId", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_76(self) -> List[Dict]:
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
                "INPUTS": [{"name": "proposalId", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_77(self) -> List[Dict]:
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
                "inputs": [{"XXnameXX": "proposalId", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_78(self) -> List[Dict]:
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
                "inputs": [{"NAME": "proposalId", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_79(self) -> List[Dict]:
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
                "inputs": [{"name": "XXproposalIdXX", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_80(self) -> List[Dict]:
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
                "inputs": [{"name": "proposalid", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_81(self) -> List[Dict]:
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
                "inputs": [{"name": "PROPOSALID", "type": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_82(self) -> List[Dict]:
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
                "inputs": [{"name": "proposalId", "XXtypeXX": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_83(self) -> List[Dict]:
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
                "inputs": [{"name": "proposalId", "TYPE": "uint256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_84(self) -> List[Dict]:
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
                "inputs": [{"name": "proposalId", "type": "XXuint256XX"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_85(self) -> List[Dict]:
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
                "inputs": [{"name": "proposalId", "type": "UINT256"}],
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_86(self) -> List[Dict]:
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
                "XXnameXX": "getProposal",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_87(self) -> List[Dict]:
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
                "NAME": "getProposal",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_88(self) -> List[Dict]:
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
                "name": "XXgetProposalXX",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_89(self) -> List[Dict]:
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
                "name": "getproposal",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_90(self) -> List[Dict]:
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
                "name": "GETPROPOSAL",
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_91(self) -> List[Dict]:
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
                "XXoutputsXX": [
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_92(self) -> List[Dict]:
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
                "OUTPUTS": [
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_93(self) -> List[Dict]:
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
                    {"XXnameXX": "id", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_94(self) -> List[Dict]:
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
                    {"NAME": "id", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_95(self) -> List[Dict]:
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
                    {"name": "XXidXX", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_96(self) -> List[Dict]:
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
                    {"name": "ID", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_97(self) -> List[Dict]:
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
                    {"name": "id", "XXtypeXX": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_98(self) -> List[Dict]:
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
                    {"name": "id", "TYPE": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_99(self) -> List[Dict]:
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
                    {"name": "id", "type": "XXuint256XX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_100(self) -> List[Dict]:
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
                    {"name": "id", "type": "UINT256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_101(self) -> List[Dict]:
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
                    {"XXnameXX": "title", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_102(self) -> List[Dict]:
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
                    {"NAME": "title", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_103(self) -> List[Dict]:
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
                    {"name": "XXtitleXX", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_104(self) -> List[Dict]:
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
                    {"name": "TITLE", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_105(self) -> List[Dict]:
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
                    {"name": "title", "XXtypeXX": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_106(self) -> List[Dict]:
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
                    {"name": "title", "TYPE": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_107(self) -> List[Dict]:
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
                    {"name": "title", "type": "XXstringXX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_108(self) -> List[Dict]:
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
                    {"name": "title", "type": "STRING"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_109(self) -> List[Dict]:
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
                    {"XXnameXX": "description", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_110(self) -> List[Dict]:
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
                    {"NAME": "description", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_111(self) -> List[Dict]:
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
                    {"name": "XXdescriptionXX", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_112(self) -> List[Dict]:
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
                    {"name": "DESCRIPTION", "type": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_113(self) -> List[Dict]:
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
                    {"name": "description", "XXtypeXX": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_114(self) -> List[Dict]:
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
                    {"name": "description", "TYPE": "string"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_115(self) -> List[Dict]:
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
                    {"name": "description", "type": "XXstringXX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_116(self) -> List[Dict]:
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
                    {"name": "description", "type": "STRING"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_117(self) -> List[Dict]:
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
                    {"XXnameXX": "proposer", "type": "address"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_118(self) -> List[Dict]:
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
                    {"NAME": "proposer", "type": "address"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_119(self) -> List[Dict]:
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
                    {"name": "XXproposerXX", "type": "address"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_120(self) -> List[Dict]:
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
                    {"name": "PROPOSER", "type": "address"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_121(self) -> List[Dict]:
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
                    {"name": "proposer", "XXtypeXX": "address"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_122(self) -> List[Dict]:
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
                    {"name": "proposer", "TYPE": "address"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_123(self) -> List[Dict]:
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
                    {"name": "proposer", "type": "XXaddressXX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_124(self) -> List[Dict]:
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
                    {"name": "proposer", "type": "ADDRESS"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_125(self) -> List[Dict]:
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
                    {"XXnameXX": "startTime", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_126(self) -> List[Dict]:
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
                    {"NAME": "startTime", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_127(self) -> List[Dict]:
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
                    {"name": "XXstartTimeXX", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_128(self) -> List[Dict]:
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
                    {"name": "starttime", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_129(self) -> List[Dict]:
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
                    {"name": "STARTTIME", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_130(self) -> List[Dict]:
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
                    {"name": "startTime", "XXtypeXX": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_131(self) -> List[Dict]:
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
                    {"name": "startTime", "TYPE": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_132(self) -> List[Dict]:
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
                    {"name": "startTime", "type": "XXuint256XX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_133(self) -> List[Dict]:
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
                    {"name": "startTime", "type": "UINT256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_134(self) -> List[Dict]:
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
                    {"XXnameXX": "endTime", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_135(self) -> List[Dict]:
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
                    {"NAME": "endTime", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_136(self) -> List[Dict]:
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
                    {"name": "XXendTimeXX", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_137(self) -> List[Dict]:
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
                    {"name": "endtime", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_138(self) -> List[Dict]:
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
                    {"name": "ENDTIME", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_139(self) -> List[Dict]:
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
                    {"name": "endTime", "XXtypeXX": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_140(self) -> List[Dict]:
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
                    {"name": "endTime", "TYPE": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_141(self) -> List[Dict]:
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
                    {"name": "endTime", "type": "XXuint256XX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_142(self) -> List[Dict]:
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
                    {"name": "endTime", "type": "UINT256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_143(self) -> List[Dict]:
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
                    {"XXnameXX": "yesVotes", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_144(self) -> List[Dict]:
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
                    {"NAME": "yesVotes", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_145(self) -> List[Dict]:
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
                    {"name": "XXyesVotesXX", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_146(self) -> List[Dict]:
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
                    {"name": "yesvotes", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_147(self) -> List[Dict]:
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
                    {"name": "YESVOTES", "type": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_148(self) -> List[Dict]:
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
                    {"name": "yesVotes", "XXtypeXX": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_149(self) -> List[Dict]:
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
                    {"name": "yesVotes", "TYPE": "uint256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_150(self) -> List[Dict]:
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
                    {"name": "yesVotes", "type": "XXuint256XX"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_151(self) -> List[Dict]:
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
                    {"name": "yesVotes", "type": "UINT256"},
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
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_152(self) -> List[Dict]:
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
                    {"XXnameXX": "noVotes", "type": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_153(self) -> List[Dict]:
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
                    {"NAME": "noVotes", "type": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_154(self) -> List[Dict]:
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
                    {"name": "XXnoVotesXX", "type": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_155(self) -> List[Dict]:
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
                    {"name": "novotes", "type": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_156(self) -> List[Dict]:
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
                    {"name": "NOVOTES", "type": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_157(self) -> List[Dict]:
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
                    {"name": "noVotes", "XXtypeXX": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_158(self) -> List[Dict]:
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
                    {"name": "noVotes", "TYPE": "uint256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_159(self) -> List[Dict]:
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
                    {"name": "noVotes", "type": "XXuint256XX"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_160(self) -> List[Dict]:
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
                    {"name": "noVotes", "type": "UINT256"},
                    {"name": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_161(self) -> List[Dict]:
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
                    {"XXnameXX": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_162(self) -> List[Dict]:
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
                    {"NAME": "abstainVotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_163(self) -> List[Dict]:
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
                    {"name": "XXabstainVotesXX", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_164(self) -> List[Dict]:
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
                    {"name": "abstainvotes", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_165(self) -> List[Dict]:
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
                    {"name": "ABSTAINVOTES", "type": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_166(self) -> List[Dict]:
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
                    {"name": "abstainVotes", "XXtypeXX": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_167(self) -> List[Dict]:
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
                    {"name": "abstainVotes", "TYPE": "uint256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_168(self) -> List[Dict]:
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
                    {"name": "abstainVotes", "type": "XXuint256XX"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_169(self) -> List[Dict]:
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
                    {"name": "abstainVotes", "type": "UINT256"},
                    {"name": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_170(self) -> List[Dict]:
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
                    {"XXnameXX": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_171(self) -> List[Dict]:
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
                    {"NAME": "totalVotingPower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_172(self) -> List[Dict]:
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
                    {"name": "XXtotalVotingPowerXX", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_173(self) -> List[Dict]:
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
                    {"name": "totalvotingpower", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_174(self) -> List[Dict]:
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
                    {"name": "TOTALVOTINGPOWER", "type": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_175(self) -> List[Dict]:
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
                    {"name": "totalVotingPower", "XXtypeXX": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_176(self) -> List[Dict]:
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
                    {"name": "totalVotingPower", "TYPE": "uint256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_177(self) -> List[Dict]:
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
                    {"name": "totalVotingPower", "type": "XXuint256XX"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_178(self) -> List[Dict]:
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
                    {"name": "totalVotingPower", "type": "UINT256"},
                    {"name": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_179(self) -> List[Dict]:
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
                    {"XXnameXX": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_180(self) -> List[Dict]:
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
                    {"NAME": "executed", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_181(self) -> List[Dict]:
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
                    {"name": "XXexecutedXX", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_182(self) -> List[Dict]:
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
                    {"name": "EXECUTED", "type": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_183(self) -> List[Dict]:
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
                    {"name": "executed", "XXtypeXX": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_184(self) -> List[Dict]:
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
                    {"name": "executed", "TYPE": "bool"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_185(self) -> List[Dict]:
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
                    {"name": "executed", "type": "XXboolXX"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_186(self) -> List[Dict]:
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
                    {"name": "executed", "type": "BOOL"},
                    {"name": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_187(self) -> List[Dict]:
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
                    {"XXnameXX": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_188(self) -> List[Dict]:
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
                    {"NAME": "state", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_189(self) -> List[Dict]:
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
                    {"name": "XXstateXX", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_190(self) -> List[Dict]:
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
                    {"name": "STATE", "type": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_191(self) -> List[Dict]:
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
                    {"name": "state", "XXtypeXX": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_192(self) -> List[Dict]:
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
                    {"name": "state", "TYPE": "uint8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_193(self) -> List[Dict]:
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
                    {"name": "state", "type": "XXuint8XX"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_194(self) -> List[Dict]:
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
                    {"name": "state", "type": "UINT8"}
                ],
                "type": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_195(self) -> List[Dict]:
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
                "XXtypeXX": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_196(self) -> List[Dict]:
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
                "TYPE": "function",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_197(self) -> List[Dict]:
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
                "type": "XXfunctionXX",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_198(self) -> List[Dict]:
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
                "type": "FUNCTION",
                "stateMutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_199(self) -> List[Dict]:
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
                "XXstateMutabilityXX": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_200(self) -> List[Dict]:
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
                "statemutability": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_201(self) -> List[Dict]:
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
                "STATEMUTABILITY": "view"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_202(self) -> List[Dict]:
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
                "stateMutability": "XXviewXX"
            }
        ]
    
    def xǁGovernanceContractǁ_get_minimal_abi__mutmut_203(self) -> List[Dict]:
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
                "stateMutability": "VIEW"
            }
        ]
    
    xǁGovernanceContractǁ_get_minimal_abi__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁ_get_minimal_abi__mutmut_1': xǁGovernanceContractǁ_get_minimal_abi__mutmut_1, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_2': xǁGovernanceContractǁ_get_minimal_abi__mutmut_2, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_3': xǁGovernanceContractǁ_get_minimal_abi__mutmut_3, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_4': xǁGovernanceContractǁ_get_minimal_abi__mutmut_4, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_5': xǁGovernanceContractǁ_get_minimal_abi__mutmut_5, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_6': xǁGovernanceContractǁ_get_minimal_abi__mutmut_6, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_7': xǁGovernanceContractǁ_get_minimal_abi__mutmut_7, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_8': xǁGovernanceContractǁ_get_minimal_abi__mutmut_8, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_9': xǁGovernanceContractǁ_get_minimal_abi__mutmut_9, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_10': xǁGovernanceContractǁ_get_minimal_abi__mutmut_10, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_11': xǁGovernanceContractǁ_get_minimal_abi__mutmut_11, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_12': xǁGovernanceContractǁ_get_minimal_abi__mutmut_12, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_13': xǁGovernanceContractǁ_get_minimal_abi__mutmut_13, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_14': xǁGovernanceContractǁ_get_minimal_abi__mutmut_14, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_15': xǁGovernanceContractǁ_get_minimal_abi__mutmut_15, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_16': xǁGovernanceContractǁ_get_minimal_abi__mutmut_16, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_17': xǁGovernanceContractǁ_get_minimal_abi__mutmut_17, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_18': xǁGovernanceContractǁ_get_minimal_abi__mutmut_18, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_19': xǁGovernanceContractǁ_get_minimal_abi__mutmut_19, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_20': xǁGovernanceContractǁ_get_minimal_abi__mutmut_20, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_21': xǁGovernanceContractǁ_get_minimal_abi__mutmut_21, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_22': xǁGovernanceContractǁ_get_minimal_abi__mutmut_22, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_23': xǁGovernanceContractǁ_get_minimal_abi__mutmut_23, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_24': xǁGovernanceContractǁ_get_minimal_abi__mutmut_24, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_25': xǁGovernanceContractǁ_get_minimal_abi__mutmut_25, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_26': xǁGovernanceContractǁ_get_minimal_abi__mutmut_26, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_27': xǁGovernanceContractǁ_get_minimal_abi__mutmut_27, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_28': xǁGovernanceContractǁ_get_minimal_abi__mutmut_28, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_29': xǁGovernanceContractǁ_get_minimal_abi__mutmut_29, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_30': xǁGovernanceContractǁ_get_minimal_abi__mutmut_30, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_31': xǁGovernanceContractǁ_get_minimal_abi__mutmut_31, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_32': xǁGovernanceContractǁ_get_minimal_abi__mutmut_32, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_33': xǁGovernanceContractǁ_get_minimal_abi__mutmut_33, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_34': xǁGovernanceContractǁ_get_minimal_abi__mutmut_34, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_35': xǁGovernanceContractǁ_get_minimal_abi__mutmut_35, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_36': xǁGovernanceContractǁ_get_minimal_abi__mutmut_36, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_37': xǁGovernanceContractǁ_get_minimal_abi__mutmut_37, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_38': xǁGovernanceContractǁ_get_minimal_abi__mutmut_38, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_39': xǁGovernanceContractǁ_get_minimal_abi__mutmut_39, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_40': xǁGovernanceContractǁ_get_minimal_abi__mutmut_40, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_41': xǁGovernanceContractǁ_get_minimal_abi__mutmut_41, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_42': xǁGovernanceContractǁ_get_minimal_abi__mutmut_42, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_43': xǁGovernanceContractǁ_get_minimal_abi__mutmut_43, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_44': xǁGovernanceContractǁ_get_minimal_abi__mutmut_44, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_45': xǁGovernanceContractǁ_get_minimal_abi__mutmut_45, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_46': xǁGovernanceContractǁ_get_minimal_abi__mutmut_46, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_47': xǁGovernanceContractǁ_get_minimal_abi__mutmut_47, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_48': xǁGovernanceContractǁ_get_minimal_abi__mutmut_48, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_49': xǁGovernanceContractǁ_get_minimal_abi__mutmut_49, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_50': xǁGovernanceContractǁ_get_minimal_abi__mutmut_50, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_51': xǁGovernanceContractǁ_get_minimal_abi__mutmut_51, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_52': xǁGovernanceContractǁ_get_minimal_abi__mutmut_52, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_53': xǁGovernanceContractǁ_get_minimal_abi__mutmut_53, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_54': xǁGovernanceContractǁ_get_minimal_abi__mutmut_54, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_55': xǁGovernanceContractǁ_get_minimal_abi__mutmut_55, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_56': xǁGovernanceContractǁ_get_minimal_abi__mutmut_56, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_57': xǁGovernanceContractǁ_get_minimal_abi__mutmut_57, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_58': xǁGovernanceContractǁ_get_minimal_abi__mutmut_58, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_59': xǁGovernanceContractǁ_get_minimal_abi__mutmut_59, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_60': xǁGovernanceContractǁ_get_minimal_abi__mutmut_60, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_61': xǁGovernanceContractǁ_get_minimal_abi__mutmut_61, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_62': xǁGovernanceContractǁ_get_minimal_abi__mutmut_62, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_63': xǁGovernanceContractǁ_get_minimal_abi__mutmut_63, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_64': xǁGovernanceContractǁ_get_minimal_abi__mutmut_64, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_65': xǁGovernanceContractǁ_get_minimal_abi__mutmut_65, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_66': xǁGovernanceContractǁ_get_minimal_abi__mutmut_66, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_67': xǁGovernanceContractǁ_get_minimal_abi__mutmut_67, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_68': xǁGovernanceContractǁ_get_minimal_abi__mutmut_68, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_69': xǁGovernanceContractǁ_get_minimal_abi__mutmut_69, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_70': xǁGovernanceContractǁ_get_minimal_abi__mutmut_70, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_71': xǁGovernanceContractǁ_get_minimal_abi__mutmut_71, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_72': xǁGovernanceContractǁ_get_minimal_abi__mutmut_72, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_73': xǁGovernanceContractǁ_get_minimal_abi__mutmut_73, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_74': xǁGovernanceContractǁ_get_minimal_abi__mutmut_74, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_75': xǁGovernanceContractǁ_get_minimal_abi__mutmut_75, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_76': xǁGovernanceContractǁ_get_minimal_abi__mutmut_76, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_77': xǁGovernanceContractǁ_get_minimal_abi__mutmut_77, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_78': xǁGovernanceContractǁ_get_minimal_abi__mutmut_78, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_79': xǁGovernanceContractǁ_get_minimal_abi__mutmut_79, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_80': xǁGovernanceContractǁ_get_minimal_abi__mutmut_80, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_81': xǁGovernanceContractǁ_get_minimal_abi__mutmut_81, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_82': xǁGovernanceContractǁ_get_minimal_abi__mutmut_82, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_83': xǁGovernanceContractǁ_get_minimal_abi__mutmut_83, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_84': xǁGovernanceContractǁ_get_minimal_abi__mutmut_84, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_85': xǁGovernanceContractǁ_get_minimal_abi__mutmut_85, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_86': xǁGovernanceContractǁ_get_minimal_abi__mutmut_86, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_87': xǁGovernanceContractǁ_get_minimal_abi__mutmut_87, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_88': xǁGovernanceContractǁ_get_minimal_abi__mutmut_88, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_89': xǁGovernanceContractǁ_get_minimal_abi__mutmut_89, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_90': xǁGovernanceContractǁ_get_minimal_abi__mutmut_90, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_91': xǁGovernanceContractǁ_get_minimal_abi__mutmut_91, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_92': xǁGovernanceContractǁ_get_minimal_abi__mutmut_92, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_93': xǁGovernanceContractǁ_get_minimal_abi__mutmut_93, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_94': xǁGovernanceContractǁ_get_minimal_abi__mutmut_94, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_95': xǁGovernanceContractǁ_get_minimal_abi__mutmut_95, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_96': xǁGovernanceContractǁ_get_minimal_abi__mutmut_96, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_97': xǁGovernanceContractǁ_get_minimal_abi__mutmut_97, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_98': xǁGovernanceContractǁ_get_minimal_abi__mutmut_98, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_99': xǁGovernanceContractǁ_get_minimal_abi__mutmut_99, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_100': xǁGovernanceContractǁ_get_minimal_abi__mutmut_100, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_101': xǁGovernanceContractǁ_get_minimal_abi__mutmut_101, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_102': xǁGovernanceContractǁ_get_minimal_abi__mutmut_102, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_103': xǁGovernanceContractǁ_get_minimal_abi__mutmut_103, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_104': xǁGovernanceContractǁ_get_minimal_abi__mutmut_104, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_105': xǁGovernanceContractǁ_get_minimal_abi__mutmut_105, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_106': xǁGovernanceContractǁ_get_minimal_abi__mutmut_106, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_107': xǁGovernanceContractǁ_get_minimal_abi__mutmut_107, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_108': xǁGovernanceContractǁ_get_minimal_abi__mutmut_108, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_109': xǁGovernanceContractǁ_get_minimal_abi__mutmut_109, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_110': xǁGovernanceContractǁ_get_minimal_abi__mutmut_110, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_111': xǁGovernanceContractǁ_get_minimal_abi__mutmut_111, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_112': xǁGovernanceContractǁ_get_minimal_abi__mutmut_112, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_113': xǁGovernanceContractǁ_get_minimal_abi__mutmut_113, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_114': xǁGovernanceContractǁ_get_minimal_abi__mutmut_114, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_115': xǁGovernanceContractǁ_get_minimal_abi__mutmut_115, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_116': xǁGovernanceContractǁ_get_minimal_abi__mutmut_116, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_117': xǁGovernanceContractǁ_get_minimal_abi__mutmut_117, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_118': xǁGovernanceContractǁ_get_minimal_abi__mutmut_118, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_119': xǁGovernanceContractǁ_get_minimal_abi__mutmut_119, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_120': xǁGovernanceContractǁ_get_minimal_abi__mutmut_120, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_121': xǁGovernanceContractǁ_get_minimal_abi__mutmut_121, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_122': xǁGovernanceContractǁ_get_minimal_abi__mutmut_122, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_123': xǁGovernanceContractǁ_get_minimal_abi__mutmut_123, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_124': xǁGovernanceContractǁ_get_minimal_abi__mutmut_124, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_125': xǁGovernanceContractǁ_get_minimal_abi__mutmut_125, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_126': xǁGovernanceContractǁ_get_minimal_abi__mutmut_126, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_127': xǁGovernanceContractǁ_get_minimal_abi__mutmut_127, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_128': xǁGovernanceContractǁ_get_minimal_abi__mutmut_128, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_129': xǁGovernanceContractǁ_get_minimal_abi__mutmut_129, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_130': xǁGovernanceContractǁ_get_minimal_abi__mutmut_130, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_131': xǁGovernanceContractǁ_get_minimal_abi__mutmut_131, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_132': xǁGovernanceContractǁ_get_minimal_abi__mutmut_132, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_133': xǁGovernanceContractǁ_get_minimal_abi__mutmut_133, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_134': xǁGovernanceContractǁ_get_minimal_abi__mutmut_134, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_135': xǁGovernanceContractǁ_get_minimal_abi__mutmut_135, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_136': xǁGovernanceContractǁ_get_minimal_abi__mutmut_136, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_137': xǁGovernanceContractǁ_get_minimal_abi__mutmut_137, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_138': xǁGovernanceContractǁ_get_minimal_abi__mutmut_138, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_139': xǁGovernanceContractǁ_get_minimal_abi__mutmut_139, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_140': xǁGovernanceContractǁ_get_minimal_abi__mutmut_140, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_141': xǁGovernanceContractǁ_get_minimal_abi__mutmut_141, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_142': xǁGovernanceContractǁ_get_minimal_abi__mutmut_142, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_143': xǁGovernanceContractǁ_get_minimal_abi__mutmut_143, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_144': xǁGovernanceContractǁ_get_minimal_abi__mutmut_144, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_145': xǁGovernanceContractǁ_get_minimal_abi__mutmut_145, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_146': xǁGovernanceContractǁ_get_minimal_abi__mutmut_146, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_147': xǁGovernanceContractǁ_get_minimal_abi__mutmut_147, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_148': xǁGovernanceContractǁ_get_minimal_abi__mutmut_148, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_149': xǁGovernanceContractǁ_get_minimal_abi__mutmut_149, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_150': xǁGovernanceContractǁ_get_minimal_abi__mutmut_150, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_151': xǁGovernanceContractǁ_get_minimal_abi__mutmut_151, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_152': xǁGovernanceContractǁ_get_minimal_abi__mutmut_152, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_153': xǁGovernanceContractǁ_get_minimal_abi__mutmut_153, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_154': xǁGovernanceContractǁ_get_minimal_abi__mutmut_154, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_155': xǁGovernanceContractǁ_get_minimal_abi__mutmut_155, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_156': xǁGovernanceContractǁ_get_minimal_abi__mutmut_156, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_157': xǁGovernanceContractǁ_get_minimal_abi__mutmut_157, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_158': xǁGovernanceContractǁ_get_minimal_abi__mutmut_158, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_159': xǁGovernanceContractǁ_get_minimal_abi__mutmut_159, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_160': xǁGovernanceContractǁ_get_minimal_abi__mutmut_160, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_161': xǁGovernanceContractǁ_get_minimal_abi__mutmut_161, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_162': xǁGovernanceContractǁ_get_minimal_abi__mutmut_162, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_163': xǁGovernanceContractǁ_get_minimal_abi__mutmut_163, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_164': xǁGovernanceContractǁ_get_minimal_abi__mutmut_164, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_165': xǁGovernanceContractǁ_get_minimal_abi__mutmut_165, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_166': xǁGovernanceContractǁ_get_minimal_abi__mutmut_166, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_167': xǁGovernanceContractǁ_get_minimal_abi__mutmut_167, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_168': xǁGovernanceContractǁ_get_minimal_abi__mutmut_168, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_169': xǁGovernanceContractǁ_get_minimal_abi__mutmut_169, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_170': xǁGovernanceContractǁ_get_minimal_abi__mutmut_170, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_171': xǁGovernanceContractǁ_get_minimal_abi__mutmut_171, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_172': xǁGovernanceContractǁ_get_minimal_abi__mutmut_172, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_173': xǁGovernanceContractǁ_get_minimal_abi__mutmut_173, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_174': xǁGovernanceContractǁ_get_minimal_abi__mutmut_174, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_175': xǁGovernanceContractǁ_get_minimal_abi__mutmut_175, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_176': xǁGovernanceContractǁ_get_minimal_abi__mutmut_176, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_177': xǁGovernanceContractǁ_get_minimal_abi__mutmut_177, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_178': xǁGovernanceContractǁ_get_minimal_abi__mutmut_178, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_179': xǁGovernanceContractǁ_get_minimal_abi__mutmut_179, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_180': xǁGovernanceContractǁ_get_minimal_abi__mutmut_180, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_181': xǁGovernanceContractǁ_get_minimal_abi__mutmut_181, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_182': xǁGovernanceContractǁ_get_minimal_abi__mutmut_182, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_183': xǁGovernanceContractǁ_get_minimal_abi__mutmut_183, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_184': xǁGovernanceContractǁ_get_minimal_abi__mutmut_184, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_185': xǁGovernanceContractǁ_get_minimal_abi__mutmut_185, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_186': xǁGovernanceContractǁ_get_minimal_abi__mutmut_186, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_187': xǁGovernanceContractǁ_get_minimal_abi__mutmut_187, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_188': xǁGovernanceContractǁ_get_minimal_abi__mutmut_188, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_189': xǁGovernanceContractǁ_get_minimal_abi__mutmut_189, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_190': xǁGovernanceContractǁ_get_minimal_abi__mutmut_190, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_191': xǁGovernanceContractǁ_get_minimal_abi__mutmut_191, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_192': xǁGovernanceContractǁ_get_minimal_abi__mutmut_192, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_193': xǁGovernanceContractǁ_get_minimal_abi__mutmut_193, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_194': xǁGovernanceContractǁ_get_minimal_abi__mutmut_194, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_195': xǁGovernanceContractǁ_get_minimal_abi__mutmut_195, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_196': xǁGovernanceContractǁ_get_minimal_abi__mutmut_196, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_197': xǁGovernanceContractǁ_get_minimal_abi__mutmut_197, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_198': xǁGovernanceContractǁ_get_minimal_abi__mutmut_198, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_199': xǁGovernanceContractǁ_get_minimal_abi__mutmut_199, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_200': xǁGovernanceContractǁ_get_minimal_abi__mutmut_200, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_201': xǁGovernanceContractǁ_get_minimal_abi__mutmut_201, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_202': xǁGovernanceContractǁ_get_minimal_abi__mutmut_202, 
        'xǁGovernanceContractǁ_get_minimal_abi__mutmut_203': xǁGovernanceContractǁ_get_minimal_abi__mutmut_203
    }
    
    def _get_minimal_abi(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁ_get_minimal_abi__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁ_get_minimal_abi__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _get_minimal_abi.__signature__ = _mutmut_signature(xǁGovernanceContractǁ_get_minimal_abi__mutmut_orig)
    xǁGovernanceContractǁ_get_minimal_abi__mutmut_orig.__name__ = 'xǁGovernanceContractǁ_get_minimal_abi'
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_orig(
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_1(
        self,
        title: str,
        description: str,
        duration_seconds: int = 259201  # 3 days default
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_2(
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
        if self.account:
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_3(
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
            raise ValueError(None)
        
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_4(
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
            raise ValueError("XXPrivate key required for creating proposalsXX")
        
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_5(
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
            raise ValueError("private key required for creating proposals")
        
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_6(
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
            raise ValueError("PRIVATE KEY REQUIRED FOR CREATING PROPOSALS")
        
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_7(
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
            nonce = None
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_8(
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
            nonce = self.web3.eth.get_transaction_count(None)
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_9(
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
            gas_price = None
            
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_10(
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
            
            tx = None
            
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_11(
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
            ).build_transaction(None)
            
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_12(
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
                None,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_13(
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
                None,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_14(
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
                None
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_15(
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_16(
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_17(
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_18(
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
                'XXfromXX': self.account.address,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_19(
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
                'FROM': self.account.address,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_20(
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
                'XXnonceXX': nonce,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_21(
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
                'NONCE': nonce,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_22(
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
                'XXgasXX': 500000,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_23(
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
                'GAS': 500000,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_24(
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
                'gas': 500001,
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_25(
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
                'XXgasPriceXX': gas_price
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_26(
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
                'gasprice': gas_price
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_27(
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
                'GASPRICE': gas_price
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_28(
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
            
            signed_tx = None
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_29(
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
            
            signed_tx = self.web3.eth.account.sign_transaction(None, self.private_key)
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_30(
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
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, None)
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_31(
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
            
            signed_tx = self.web3.eth.account.sign_transaction(self.private_key)
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_32(
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
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, )
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
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_33(
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
            tx_hash = None
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get proposal ID from event or contract state
            proposal_count = self.contract.functions.proposalCount().call()
            proposal_id = proposal_count
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_34(
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
            tx_hash = self.web3.eth.send_raw_transaction(None)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            # Get proposal ID from event or contract state
            proposal_count = self.contract.functions.proposalCount().call()
            proposal_id = proposal_count
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_35(
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
            receipt = None
            
            # Get proposal ID from event or contract state
            proposal_count = self.contract.functions.proposalCount().call()
            proposal_id = proposal_count
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_36(
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
            receipt = self.web3.eth.wait_for_transaction_receipt(None)
            
            # Get proposal ID from event or contract state
            proposal_count = self.contract.functions.proposalCount().call()
            proposal_id = proposal_count
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_37(
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
            proposal_count = None
            proposal_id = proposal_count
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_38(
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
            proposal_id = None
            
            logger.info(f"✅ Proposal created: {proposal_id} (tx: {tx_hash.hex()})")
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_39(
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
            
            logger.info(None)
            return proposal_id
            
        except Exception as e:
            logger.error(f"Failed to create proposal: {e}")
            raise
    
    def xǁGovernanceContractǁcreate_proposal__mutmut_40(
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
            logger.error(None)
            raise
    
    xǁGovernanceContractǁcreate_proposal__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁcreate_proposal__mutmut_1': xǁGovernanceContractǁcreate_proposal__mutmut_1, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_2': xǁGovernanceContractǁcreate_proposal__mutmut_2, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_3': xǁGovernanceContractǁcreate_proposal__mutmut_3, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_4': xǁGovernanceContractǁcreate_proposal__mutmut_4, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_5': xǁGovernanceContractǁcreate_proposal__mutmut_5, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_6': xǁGovernanceContractǁcreate_proposal__mutmut_6, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_7': xǁGovernanceContractǁcreate_proposal__mutmut_7, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_8': xǁGovernanceContractǁcreate_proposal__mutmut_8, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_9': xǁGovernanceContractǁcreate_proposal__mutmut_9, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_10': xǁGovernanceContractǁcreate_proposal__mutmut_10, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_11': xǁGovernanceContractǁcreate_proposal__mutmut_11, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_12': xǁGovernanceContractǁcreate_proposal__mutmut_12, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_13': xǁGovernanceContractǁcreate_proposal__mutmut_13, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_14': xǁGovernanceContractǁcreate_proposal__mutmut_14, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_15': xǁGovernanceContractǁcreate_proposal__mutmut_15, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_16': xǁGovernanceContractǁcreate_proposal__mutmut_16, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_17': xǁGovernanceContractǁcreate_proposal__mutmut_17, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_18': xǁGovernanceContractǁcreate_proposal__mutmut_18, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_19': xǁGovernanceContractǁcreate_proposal__mutmut_19, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_20': xǁGovernanceContractǁcreate_proposal__mutmut_20, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_21': xǁGovernanceContractǁcreate_proposal__mutmut_21, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_22': xǁGovernanceContractǁcreate_proposal__mutmut_22, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_23': xǁGovernanceContractǁcreate_proposal__mutmut_23, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_24': xǁGovernanceContractǁcreate_proposal__mutmut_24, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_25': xǁGovernanceContractǁcreate_proposal__mutmut_25, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_26': xǁGovernanceContractǁcreate_proposal__mutmut_26, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_27': xǁGovernanceContractǁcreate_proposal__mutmut_27, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_28': xǁGovernanceContractǁcreate_proposal__mutmut_28, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_29': xǁGovernanceContractǁcreate_proposal__mutmut_29, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_30': xǁGovernanceContractǁcreate_proposal__mutmut_30, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_31': xǁGovernanceContractǁcreate_proposal__mutmut_31, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_32': xǁGovernanceContractǁcreate_proposal__mutmut_32, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_33': xǁGovernanceContractǁcreate_proposal__mutmut_33, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_34': xǁGovernanceContractǁcreate_proposal__mutmut_34, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_35': xǁGovernanceContractǁcreate_proposal__mutmut_35, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_36': xǁGovernanceContractǁcreate_proposal__mutmut_36, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_37': xǁGovernanceContractǁcreate_proposal__mutmut_37, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_38': xǁGovernanceContractǁcreate_proposal__mutmut_38, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_39': xǁGovernanceContractǁcreate_proposal__mutmut_39, 
        'xǁGovernanceContractǁcreate_proposal__mutmut_40': xǁGovernanceContractǁcreate_proposal__mutmut_40
    }
    
    def create_proposal(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁcreate_proposal__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁcreate_proposal__mutmut_mutants"), args, kwargs, self)
        return result 
    
    create_proposal.__signature__ = _mutmut_signature(xǁGovernanceContractǁcreate_proposal__mutmut_orig)
    xǁGovernanceContractǁcreate_proposal__mutmut_orig.__name__ = 'xǁGovernanceContractǁcreate_proposal'
    
    def xǁGovernanceContractǁcast_vote__mutmut_orig(self, proposal_id: int, support: int) -> str:
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_1(self, proposal_id: int, support: int) -> str:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_id: Proposal ID
            support: 0 = against, 1 = for, 2 = abstain
            
        Returns:
            Transaction hash
        """
        if self.account:
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_2(self, proposal_id: int, support: int) -> str:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_id: Proposal ID
            support: 0 = against, 1 = for, 2 = abstain
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError(None)
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_3(self, proposal_id: int, support: int) -> str:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_id: Proposal ID
            support: 0 = against, 1 = for, 2 = abstain
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("XXPrivate key required for votingXX")
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_4(self, proposal_id: int, support: int) -> str:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_id: Proposal ID
            support: 0 = against, 1 = for, 2 = abstain
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("private key required for voting")
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_5(self, proposal_id: int, support: int) -> str:
        """
        Cast a vote on a proposal.
        
        Args:
            proposal_id: Proposal ID
            support: 0 = against, 1 = for, 2 = abstain
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("PRIVATE KEY REQUIRED FOR VOTING")
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_6(self, proposal_id: int, support: int) -> str:
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
        
        if support in [0, 1, 2]:
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_7(self, proposal_id: int, support: int) -> str:
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
        
        if support not in [1, 1, 2]:
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_8(self, proposal_id: int, support: int) -> str:
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
        
        if support not in [0, 2, 2]:
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_9(self, proposal_id: int, support: int) -> str:
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
        
        if support not in [0, 1, 3]:
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_10(self, proposal_id: int, support: int) -> str:
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
            raise ValueError(None)
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_11(self, proposal_id: int, support: int) -> str:
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
            raise ValueError("XXSupport must be 0 (against), 1 (for), or 2 (abstain)XX")
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_12(self, proposal_id: int, support: int) -> str:
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
            raise ValueError("support must be 0 (against), 1 (for), or 2 (abstain)")
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_13(self, proposal_id: int, support: int) -> str:
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
            raise ValueError("SUPPORT MUST BE 0 (AGAINST), 1 (FOR), OR 2 (ABSTAIN)")
        
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_14(self, proposal_id: int, support: int) -> str:
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
            nonce = None
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_15(self, proposal_id: int, support: int) -> str:
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
            nonce = self.web3.eth.get_transaction_count(None)
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_16(self, proposal_id: int, support: int) -> str:
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
            gas_price = None
            
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_17(self, proposal_id: int, support: int) -> str:
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
            
            tx = None
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_18(self, proposal_id: int, support: int) -> str:
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
            
            tx = self.contract.functions.castVote(proposal_id, support).build_transaction(None)
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_19(self, proposal_id: int, support: int) -> str:
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
            
            tx = self.contract.functions.castVote(None, support).build_transaction({
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_20(self, proposal_id: int, support: int) -> str:
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
            
            tx = self.contract.functions.castVote(proposal_id, None).build_transaction({
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_21(self, proposal_id: int, support: int) -> str:
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
            
            tx = self.contract.functions.castVote(support).build_transaction({
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_22(self, proposal_id: int, support: int) -> str:
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
            
            tx = self.contract.functions.castVote(proposal_id, ).build_transaction({
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_23(self, proposal_id: int, support: int) -> str:
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
                'XXfromXX': self.account.address,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_24(self, proposal_id: int, support: int) -> str:
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
                'FROM': self.account.address,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_25(self, proposal_id: int, support: int) -> str:
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
                'XXnonceXX': nonce,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_26(self, proposal_id: int, support: int) -> str:
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
                'NONCE': nonce,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_27(self, proposal_id: int, support: int) -> str:
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
                'XXgasXX': 200000,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_28(self, proposal_id: int, support: int) -> str:
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
                'GAS': 200000,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_29(self, proposal_id: int, support: int) -> str:
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
                'gas': 200001,
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
    
    def xǁGovernanceContractǁcast_vote__mutmut_30(self, proposal_id: int, support: int) -> str:
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
                'XXgasPriceXX': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_31(self, proposal_id: int, support: int) -> str:
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
                'gasprice': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_32(self, proposal_id: int, support: int) -> str:
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
                'GASPRICE': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_33(self, proposal_id: int, support: int) -> str:
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
            
            signed_tx = None
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_34(self, proposal_id: int, support: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(None, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_35(self, proposal_id: int, support: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, None)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_36(self, proposal_id: int, support: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_37(self, proposal_id: int, support: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_38(self, proposal_id: int, support: int) -> str:
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
            tx_hash = None
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_39(self, proposal_id: int, support: int) -> str:
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
            tx_hash = self.web3.eth.send_raw_transaction(None)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_40(self, proposal_id: int, support: int) -> str:
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
            receipt = None
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_41(self, proposal_id: int, support: int) -> str:
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
            receipt = self.web3.eth.wait_for_transaction_receipt(None)
            
            logger.info(f"✅ Vote cast: {support} on proposal {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_42(self, proposal_id: int, support: int) -> str:
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
            
            logger.info(None)
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to cast vote: {e}")
            raise
    
    def xǁGovernanceContractǁcast_vote__mutmut_43(self, proposal_id: int, support: int) -> str:
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
            logger.error(None)
            raise
    
    xǁGovernanceContractǁcast_vote__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁcast_vote__mutmut_1': xǁGovernanceContractǁcast_vote__mutmut_1, 
        'xǁGovernanceContractǁcast_vote__mutmut_2': xǁGovernanceContractǁcast_vote__mutmut_2, 
        'xǁGovernanceContractǁcast_vote__mutmut_3': xǁGovernanceContractǁcast_vote__mutmut_3, 
        'xǁGovernanceContractǁcast_vote__mutmut_4': xǁGovernanceContractǁcast_vote__mutmut_4, 
        'xǁGovernanceContractǁcast_vote__mutmut_5': xǁGovernanceContractǁcast_vote__mutmut_5, 
        'xǁGovernanceContractǁcast_vote__mutmut_6': xǁGovernanceContractǁcast_vote__mutmut_6, 
        'xǁGovernanceContractǁcast_vote__mutmut_7': xǁGovernanceContractǁcast_vote__mutmut_7, 
        'xǁGovernanceContractǁcast_vote__mutmut_8': xǁGovernanceContractǁcast_vote__mutmut_8, 
        'xǁGovernanceContractǁcast_vote__mutmut_9': xǁGovernanceContractǁcast_vote__mutmut_9, 
        'xǁGovernanceContractǁcast_vote__mutmut_10': xǁGovernanceContractǁcast_vote__mutmut_10, 
        'xǁGovernanceContractǁcast_vote__mutmut_11': xǁGovernanceContractǁcast_vote__mutmut_11, 
        'xǁGovernanceContractǁcast_vote__mutmut_12': xǁGovernanceContractǁcast_vote__mutmut_12, 
        'xǁGovernanceContractǁcast_vote__mutmut_13': xǁGovernanceContractǁcast_vote__mutmut_13, 
        'xǁGovernanceContractǁcast_vote__mutmut_14': xǁGovernanceContractǁcast_vote__mutmut_14, 
        'xǁGovernanceContractǁcast_vote__mutmut_15': xǁGovernanceContractǁcast_vote__mutmut_15, 
        'xǁGovernanceContractǁcast_vote__mutmut_16': xǁGovernanceContractǁcast_vote__mutmut_16, 
        'xǁGovernanceContractǁcast_vote__mutmut_17': xǁGovernanceContractǁcast_vote__mutmut_17, 
        'xǁGovernanceContractǁcast_vote__mutmut_18': xǁGovernanceContractǁcast_vote__mutmut_18, 
        'xǁGovernanceContractǁcast_vote__mutmut_19': xǁGovernanceContractǁcast_vote__mutmut_19, 
        'xǁGovernanceContractǁcast_vote__mutmut_20': xǁGovernanceContractǁcast_vote__mutmut_20, 
        'xǁGovernanceContractǁcast_vote__mutmut_21': xǁGovernanceContractǁcast_vote__mutmut_21, 
        'xǁGovernanceContractǁcast_vote__mutmut_22': xǁGovernanceContractǁcast_vote__mutmut_22, 
        'xǁGovernanceContractǁcast_vote__mutmut_23': xǁGovernanceContractǁcast_vote__mutmut_23, 
        'xǁGovernanceContractǁcast_vote__mutmut_24': xǁGovernanceContractǁcast_vote__mutmut_24, 
        'xǁGovernanceContractǁcast_vote__mutmut_25': xǁGovernanceContractǁcast_vote__mutmut_25, 
        'xǁGovernanceContractǁcast_vote__mutmut_26': xǁGovernanceContractǁcast_vote__mutmut_26, 
        'xǁGovernanceContractǁcast_vote__mutmut_27': xǁGovernanceContractǁcast_vote__mutmut_27, 
        'xǁGovernanceContractǁcast_vote__mutmut_28': xǁGovernanceContractǁcast_vote__mutmut_28, 
        'xǁGovernanceContractǁcast_vote__mutmut_29': xǁGovernanceContractǁcast_vote__mutmut_29, 
        'xǁGovernanceContractǁcast_vote__mutmut_30': xǁGovernanceContractǁcast_vote__mutmut_30, 
        'xǁGovernanceContractǁcast_vote__mutmut_31': xǁGovernanceContractǁcast_vote__mutmut_31, 
        'xǁGovernanceContractǁcast_vote__mutmut_32': xǁGovernanceContractǁcast_vote__mutmut_32, 
        'xǁGovernanceContractǁcast_vote__mutmut_33': xǁGovernanceContractǁcast_vote__mutmut_33, 
        'xǁGovernanceContractǁcast_vote__mutmut_34': xǁGovernanceContractǁcast_vote__mutmut_34, 
        'xǁGovernanceContractǁcast_vote__mutmut_35': xǁGovernanceContractǁcast_vote__mutmut_35, 
        'xǁGovernanceContractǁcast_vote__mutmut_36': xǁGovernanceContractǁcast_vote__mutmut_36, 
        'xǁGovernanceContractǁcast_vote__mutmut_37': xǁGovernanceContractǁcast_vote__mutmut_37, 
        'xǁGovernanceContractǁcast_vote__mutmut_38': xǁGovernanceContractǁcast_vote__mutmut_38, 
        'xǁGovernanceContractǁcast_vote__mutmut_39': xǁGovernanceContractǁcast_vote__mutmut_39, 
        'xǁGovernanceContractǁcast_vote__mutmut_40': xǁGovernanceContractǁcast_vote__mutmut_40, 
        'xǁGovernanceContractǁcast_vote__mutmut_41': xǁGovernanceContractǁcast_vote__mutmut_41, 
        'xǁGovernanceContractǁcast_vote__mutmut_42': xǁGovernanceContractǁcast_vote__mutmut_42, 
        'xǁGovernanceContractǁcast_vote__mutmut_43': xǁGovernanceContractǁcast_vote__mutmut_43
    }
    
    def cast_vote(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁcast_vote__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁcast_vote__mutmut_mutants"), args, kwargs, self)
        return result 
    
    cast_vote.__signature__ = _mutmut_signature(xǁGovernanceContractǁcast_vote__mutmut_orig)
    xǁGovernanceContractǁcast_vote__mutmut_orig.__name__ = 'xǁGovernanceContractǁcast_vote'
    
    def xǁGovernanceContractǁget_proposal__mutmut_orig(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_1(self, proposal_id: int) -> ProposalInfo:
        """
        Get proposal information from contract.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            ProposalInfo object
        """
        try:
            result = None
            
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_2(self, proposal_id: int) -> ProposalInfo:
        """
        Get proposal information from contract.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            ProposalInfo object
        """
        try:
            result = self.contract.functions.getProposal(None).call()
            
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_3(self, proposal_id: int) -> ProposalInfo:
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
                id=None,
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_4(self, proposal_id: int) -> ProposalInfo:
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
                title=None,
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_5(self, proposal_id: int) -> ProposalInfo:
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
                description=None,
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_6(self, proposal_id: int) -> ProposalInfo:
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
                proposer=None,
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_7(self, proposal_id: int) -> ProposalInfo:
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
                start_time=None,
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_8(self, proposal_id: int) -> ProposalInfo:
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
                end_time=None,
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_9(self, proposal_id: int) -> ProposalInfo:
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
                yes_votes=None,
                no_votes=result[7],
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_10(self, proposal_id: int) -> ProposalInfo:
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
                no_votes=None,
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_11(self, proposal_id: int) -> ProposalInfo:
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
                abstain_votes=None,
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_12(self, proposal_id: int) -> ProposalInfo:
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
                total_voting_power=None,
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_13(self, proposal_id: int) -> ProposalInfo:
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
                executed=None,
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_14(self, proposal_id: int) -> ProposalInfo:
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
                state=None
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_15(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_16(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_17(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_18(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_19(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_20(self, proposal_id: int) -> ProposalInfo:
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_21(self, proposal_id: int) -> ProposalInfo:
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
                no_votes=result[7],
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_22(self, proposal_id: int) -> ProposalInfo:
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
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_23(self, proposal_id: int) -> ProposalInfo:
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
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_24(self, proposal_id: int) -> ProposalInfo:
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
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_25(self, proposal_id: int) -> ProposalInfo:
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
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_26(self, proposal_id: int) -> ProposalInfo:
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
                )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_27(self, proposal_id: int) -> ProposalInfo:
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
                id=result[1],
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_28(self, proposal_id: int) -> ProposalInfo:
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
                title=result[2],
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_29(self, proposal_id: int) -> ProposalInfo:
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
                description=result[3],
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_30(self, proposal_id: int) -> ProposalInfo:
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
                proposer=result[4],
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_31(self, proposal_id: int) -> ProposalInfo:
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
                start_time=result[5],
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_32(self, proposal_id: int) -> ProposalInfo:
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
                end_time=result[6],
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
    
    def xǁGovernanceContractǁget_proposal__mutmut_33(self, proposal_id: int) -> ProposalInfo:
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
                yes_votes=result[7],
                no_votes=result[7],
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_34(self, proposal_id: int) -> ProposalInfo:
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
                no_votes=result[8],
                abstain_votes=result[8],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_35(self, proposal_id: int) -> ProposalInfo:
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
                abstain_votes=result[9],
                total_voting_power=result[9],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_36(self, proposal_id: int) -> ProposalInfo:
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
                total_voting_power=result[10],
                executed=result[10],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_37(self, proposal_id: int) -> ProposalInfo:
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
                executed=result[11],
                state=ProposalState(result[11])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_38(self, proposal_id: int) -> ProposalInfo:
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
                state=ProposalState(None)
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_39(self, proposal_id: int) -> ProposalInfo:
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
                state=ProposalState(result[12])
            )
        except Exception as e:
            logger.error(f"Failed to get proposal: {e}")
            raise
    
    def xǁGovernanceContractǁget_proposal__mutmut_40(self, proposal_id: int) -> ProposalInfo:
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
            logger.error(None)
            raise
    
    xǁGovernanceContractǁget_proposal__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁget_proposal__mutmut_1': xǁGovernanceContractǁget_proposal__mutmut_1, 
        'xǁGovernanceContractǁget_proposal__mutmut_2': xǁGovernanceContractǁget_proposal__mutmut_2, 
        'xǁGovernanceContractǁget_proposal__mutmut_3': xǁGovernanceContractǁget_proposal__mutmut_3, 
        'xǁGovernanceContractǁget_proposal__mutmut_4': xǁGovernanceContractǁget_proposal__mutmut_4, 
        'xǁGovernanceContractǁget_proposal__mutmut_5': xǁGovernanceContractǁget_proposal__mutmut_5, 
        'xǁGovernanceContractǁget_proposal__mutmut_6': xǁGovernanceContractǁget_proposal__mutmut_6, 
        'xǁGovernanceContractǁget_proposal__mutmut_7': xǁGovernanceContractǁget_proposal__mutmut_7, 
        'xǁGovernanceContractǁget_proposal__mutmut_8': xǁGovernanceContractǁget_proposal__mutmut_8, 
        'xǁGovernanceContractǁget_proposal__mutmut_9': xǁGovernanceContractǁget_proposal__mutmut_9, 
        'xǁGovernanceContractǁget_proposal__mutmut_10': xǁGovernanceContractǁget_proposal__mutmut_10, 
        'xǁGovernanceContractǁget_proposal__mutmut_11': xǁGovernanceContractǁget_proposal__mutmut_11, 
        'xǁGovernanceContractǁget_proposal__mutmut_12': xǁGovernanceContractǁget_proposal__mutmut_12, 
        'xǁGovernanceContractǁget_proposal__mutmut_13': xǁGovernanceContractǁget_proposal__mutmut_13, 
        'xǁGovernanceContractǁget_proposal__mutmut_14': xǁGovernanceContractǁget_proposal__mutmut_14, 
        'xǁGovernanceContractǁget_proposal__mutmut_15': xǁGovernanceContractǁget_proposal__mutmut_15, 
        'xǁGovernanceContractǁget_proposal__mutmut_16': xǁGovernanceContractǁget_proposal__mutmut_16, 
        'xǁGovernanceContractǁget_proposal__mutmut_17': xǁGovernanceContractǁget_proposal__mutmut_17, 
        'xǁGovernanceContractǁget_proposal__mutmut_18': xǁGovernanceContractǁget_proposal__mutmut_18, 
        'xǁGovernanceContractǁget_proposal__mutmut_19': xǁGovernanceContractǁget_proposal__mutmut_19, 
        'xǁGovernanceContractǁget_proposal__mutmut_20': xǁGovernanceContractǁget_proposal__mutmut_20, 
        'xǁGovernanceContractǁget_proposal__mutmut_21': xǁGovernanceContractǁget_proposal__mutmut_21, 
        'xǁGovernanceContractǁget_proposal__mutmut_22': xǁGovernanceContractǁget_proposal__mutmut_22, 
        'xǁGovernanceContractǁget_proposal__mutmut_23': xǁGovernanceContractǁget_proposal__mutmut_23, 
        'xǁGovernanceContractǁget_proposal__mutmut_24': xǁGovernanceContractǁget_proposal__mutmut_24, 
        'xǁGovernanceContractǁget_proposal__mutmut_25': xǁGovernanceContractǁget_proposal__mutmut_25, 
        'xǁGovernanceContractǁget_proposal__mutmut_26': xǁGovernanceContractǁget_proposal__mutmut_26, 
        'xǁGovernanceContractǁget_proposal__mutmut_27': xǁGovernanceContractǁget_proposal__mutmut_27, 
        'xǁGovernanceContractǁget_proposal__mutmut_28': xǁGovernanceContractǁget_proposal__mutmut_28, 
        'xǁGovernanceContractǁget_proposal__mutmut_29': xǁGovernanceContractǁget_proposal__mutmut_29, 
        'xǁGovernanceContractǁget_proposal__mutmut_30': xǁGovernanceContractǁget_proposal__mutmut_30, 
        'xǁGovernanceContractǁget_proposal__mutmut_31': xǁGovernanceContractǁget_proposal__mutmut_31, 
        'xǁGovernanceContractǁget_proposal__mutmut_32': xǁGovernanceContractǁget_proposal__mutmut_32, 
        'xǁGovernanceContractǁget_proposal__mutmut_33': xǁGovernanceContractǁget_proposal__mutmut_33, 
        'xǁGovernanceContractǁget_proposal__mutmut_34': xǁGovernanceContractǁget_proposal__mutmut_34, 
        'xǁGovernanceContractǁget_proposal__mutmut_35': xǁGovernanceContractǁget_proposal__mutmut_35, 
        'xǁGovernanceContractǁget_proposal__mutmut_36': xǁGovernanceContractǁget_proposal__mutmut_36, 
        'xǁGovernanceContractǁget_proposal__mutmut_37': xǁGovernanceContractǁget_proposal__mutmut_37, 
        'xǁGovernanceContractǁget_proposal__mutmut_38': xǁGovernanceContractǁget_proposal__mutmut_38, 
        'xǁGovernanceContractǁget_proposal__mutmut_39': xǁGovernanceContractǁget_proposal__mutmut_39, 
        'xǁGovernanceContractǁget_proposal__mutmut_40': xǁGovernanceContractǁget_proposal__mutmut_40
    }
    
    def get_proposal(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁget_proposal__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁget_proposal__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_proposal.__signature__ = _mutmut_signature(xǁGovernanceContractǁget_proposal__mutmut_orig)
    xǁGovernanceContractǁget_proposal__mutmut_orig.__name__ = 'xǁGovernanceContractǁget_proposal'
    
    def xǁGovernanceContractǁget_voting_power__mutmut_orig(self, address: str) -> int:
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
    
    def xǁGovernanceContractǁget_voting_power__mutmut_1(self, address: str) -> int:
        """
        Get voting power of an address.
        
        Args:
            address: Ethereum address
            
        Returns:
            Voting power (based on staked tokens)
        """
        try:
            power = None
            return power
        except Exception as e:
            logger.error(f"Failed to get voting power: {e}")
            return 0
    
    def xǁGovernanceContractǁget_voting_power__mutmut_2(self, address: str) -> int:
        """
        Get voting power of an address.
        
        Args:
            address: Ethereum address
            
        Returns:
            Voting power (based on staked tokens)
        """
        try:
            power = self.contract.functions.getVotingPower(None).call()
            return power
        except Exception as e:
            logger.error(f"Failed to get voting power: {e}")
            return 0
    
    def xǁGovernanceContractǁget_voting_power__mutmut_3(self, address: str) -> int:
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
            logger.error(None)
            return 0
    
    def xǁGovernanceContractǁget_voting_power__mutmut_4(self, address: str) -> int:
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
            return 1
    
    xǁGovernanceContractǁget_voting_power__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁget_voting_power__mutmut_1': xǁGovernanceContractǁget_voting_power__mutmut_1, 
        'xǁGovernanceContractǁget_voting_power__mutmut_2': xǁGovernanceContractǁget_voting_power__mutmut_2, 
        'xǁGovernanceContractǁget_voting_power__mutmut_3': xǁGovernanceContractǁget_voting_power__mutmut_3, 
        'xǁGovernanceContractǁget_voting_power__mutmut_4': xǁGovernanceContractǁget_voting_power__mutmut_4
    }
    
    def get_voting_power(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁget_voting_power__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁget_voting_power__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_voting_power.__signature__ = _mutmut_signature(xǁGovernanceContractǁget_voting_power__mutmut_orig)
    xǁGovernanceContractǁget_voting_power__mutmut_orig.__name__ = 'xǁGovernanceContractǁget_voting_power'
    
    def xǁGovernanceContractǁcan_execute__mutmut_orig(self, proposal_id: int) -> bool:
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
    
    def xǁGovernanceContractǁcan_execute__mutmut_1(self, proposal_id: int) -> bool:
        """
        Check if proposal can be executed.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            True if proposal can be executed
        """
        try:
            return self.contract.functions.canExecute(None).call()
        except Exception as e:
            logger.error(f"Failed to check execution status: {e}")
            return False
    
    def xǁGovernanceContractǁcan_execute__mutmut_2(self, proposal_id: int) -> bool:
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
            logger.error(None)
            return False
    
    def xǁGovernanceContractǁcan_execute__mutmut_3(self, proposal_id: int) -> bool:
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
            return True
    
    xǁGovernanceContractǁcan_execute__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁcan_execute__mutmut_1': xǁGovernanceContractǁcan_execute__mutmut_1, 
        'xǁGovernanceContractǁcan_execute__mutmut_2': xǁGovernanceContractǁcan_execute__mutmut_2, 
        'xǁGovernanceContractǁcan_execute__mutmut_3': xǁGovernanceContractǁcan_execute__mutmut_3
    }
    
    def can_execute(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁcan_execute__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁcan_execute__mutmut_mutants"), args, kwargs, self)
        return result 
    
    can_execute.__signature__ = _mutmut_signature(xǁGovernanceContractǁcan_execute__mutmut_orig)
    xǁGovernanceContractǁcan_execute__mutmut_orig.__name__ = 'xǁGovernanceContractǁcan_execute'
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_orig(self, proposal_id: int) -> str:
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_1(self, proposal_id: int) -> str:
        """
        Execute a passed proposal.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Transaction hash
        """
        if self.account:
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_2(self, proposal_id: int) -> str:
        """
        Execute a passed proposal.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError(None)
        
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_3(self, proposal_id: int) -> str:
        """
        Execute a passed proposal.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("XXPrivate key required for executing proposalsXX")
        
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_4(self, proposal_id: int) -> str:
        """
        Execute a passed proposal.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("private key required for executing proposals")
        
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_5(self, proposal_id: int) -> str:
        """
        Execute a passed proposal.
        
        Args:
            proposal_id: Proposal ID
            
        Returns:
            Transaction hash
        """
        if not self.account:
            raise ValueError("PRIVATE KEY REQUIRED FOR EXECUTING PROPOSALS")
        
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_6(self, proposal_id: int) -> str:
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
            nonce = None
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_7(self, proposal_id: int) -> str:
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
            nonce = self.web3.eth.get_transaction_count(None)
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_8(self, proposal_id: int) -> str:
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
            gas_price = None
            
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_9(self, proposal_id: int) -> str:
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
            
            tx = None
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_10(self, proposal_id: int) -> str:
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
            
            tx = self.contract.functions.executeProposal(proposal_id).build_transaction(None)
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_11(self, proposal_id: int) -> str:
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
            
            tx = self.contract.functions.executeProposal(None).build_transaction({
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_12(self, proposal_id: int) -> str:
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
                'XXfromXX': self.account.address,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_13(self, proposal_id: int) -> str:
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
                'FROM': self.account.address,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_14(self, proposal_id: int) -> str:
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
                'XXnonceXX': nonce,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_15(self, proposal_id: int) -> str:
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
                'NONCE': nonce,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_16(self, proposal_id: int) -> str:
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
                'XXgasXX': 300000,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_17(self, proposal_id: int) -> str:
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
                'GAS': 300000,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_18(self, proposal_id: int) -> str:
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
                'gas': 300001,
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
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_19(self, proposal_id: int) -> str:
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
                'XXgasPriceXX': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_20(self, proposal_id: int) -> str:
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
                'gasprice': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_21(self, proposal_id: int) -> str:
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
                'GASPRICE': gas_price
            })
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_22(self, proposal_id: int) -> str:
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
            
            signed_tx = None
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_23(self, proposal_id: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(None, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_24(self, proposal_id: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, None)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_25(self, proposal_id: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_26(self, proposal_id: int) -> str:
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
            
            signed_tx = self.web3.eth.account.sign_transaction(tx, )
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_27(self, proposal_id: int) -> str:
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
            tx_hash = None
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_28(self, proposal_id: int) -> str:
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
            tx_hash = self.web3.eth.send_raw_transaction(None)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_29(self, proposal_id: int) -> str:
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
            receipt = None
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_30(self, proposal_id: int) -> str:
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
            receipt = self.web3.eth.wait_for_transaction_receipt(None)
            
            logger.info(f"✅ Proposal executed: {proposal_id} (tx: {tx_hash.hex()})")
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_31(self, proposal_id: int) -> str:
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
            
            logger.info(None)
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(f"Failed to execute proposal: {e}")
            raise
    
    def xǁGovernanceContractǁexecute_proposal__mutmut_32(self, proposal_id: int) -> str:
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
            logger.error(None)
            raise
    
    xǁGovernanceContractǁexecute_proposal__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁexecute_proposal__mutmut_1': xǁGovernanceContractǁexecute_proposal__mutmut_1, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_2': xǁGovernanceContractǁexecute_proposal__mutmut_2, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_3': xǁGovernanceContractǁexecute_proposal__mutmut_3, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_4': xǁGovernanceContractǁexecute_proposal__mutmut_4, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_5': xǁGovernanceContractǁexecute_proposal__mutmut_5, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_6': xǁGovernanceContractǁexecute_proposal__mutmut_6, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_7': xǁGovernanceContractǁexecute_proposal__mutmut_7, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_8': xǁGovernanceContractǁexecute_proposal__mutmut_8, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_9': xǁGovernanceContractǁexecute_proposal__mutmut_9, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_10': xǁGovernanceContractǁexecute_proposal__mutmut_10, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_11': xǁGovernanceContractǁexecute_proposal__mutmut_11, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_12': xǁGovernanceContractǁexecute_proposal__mutmut_12, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_13': xǁGovernanceContractǁexecute_proposal__mutmut_13, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_14': xǁGovernanceContractǁexecute_proposal__mutmut_14, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_15': xǁGovernanceContractǁexecute_proposal__mutmut_15, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_16': xǁGovernanceContractǁexecute_proposal__mutmut_16, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_17': xǁGovernanceContractǁexecute_proposal__mutmut_17, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_18': xǁGovernanceContractǁexecute_proposal__mutmut_18, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_19': xǁGovernanceContractǁexecute_proposal__mutmut_19, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_20': xǁGovernanceContractǁexecute_proposal__mutmut_20, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_21': xǁGovernanceContractǁexecute_proposal__mutmut_21, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_22': xǁGovernanceContractǁexecute_proposal__mutmut_22, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_23': xǁGovernanceContractǁexecute_proposal__mutmut_23, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_24': xǁGovernanceContractǁexecute_proposal__mutmut_24, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_25': xǁGovernanceContractǁexecute_proposal__mutmut_25, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_26': xǁGovernanceContractǁexecute_proposal__mutmut_26, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_27': xǁGovernanceContractǁexecute_proposal__mutmut_27, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_28': xǁGovernanceContractǁexecute_proposal__mutmut_28, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_29': xǁGovernanceContractǁexecute_proposal__mutmut_29, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_30': xǁGovernanceContractǁexecute_proposal__mutmut_30, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_31': xǁGovernanceContractǁexecute_proposal__mutmut_31, 
        'xǁGovernanceContractǁexecute_proposal__mutmut_32': xǁGovernanceContractǁexecute_proposal__mutmut_32
    }
    
    def execute_proposal(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁexecute_proposal__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁexecute_proposal__mutmut_mutants"), args, kwargs, self)
        return result 
    
    execute_proposal.__signature__ = _mutmut_signature(xǁGovernanceContractǁexecute_proposal__mutmut_orig)
    xǁGovernanceContractǁexecute_proposal__mutmut_orig.__name__ = 'xǁGovernanceContractǁexecute_proposal'
    
    def xǁGovernanceContractǁget_proposal_count__mutmut_orig(self) -> int:
        """Get total number of proposals."""
        try:
            return self.contract.functions.proposalCount().call()
        except Exception as e:
            logger.error(f"Failed to get proposal count: {e}")
            return 0
    
    def xǁGovernanceContractǁget_proposal_count__mutmut_1(self) -> int:
        """Get total number of proposals."""
        try:
            return self.contract.functions.proposalCount().call()
        except Exception as e:
            logger.error(None)
            return 0
    
    def xǁGovernanceContractǁget_proposal_count__mutmut_2(self) -> int:
        """Get total number of proposals."""
        try:
            return self.contract.functions.proposalCount().call()
        except Exception as e:
            logger.error(f"Failed to get proposal count: {e}")
            return 1
    
    xǁGovernanceContractǁget_proposal_count__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceContractǁget_proposal_count__mutmut_1': xǁGovernanceContractǁget_proposal_count__mutmut_1, 
        'xǁGovernanceContractǁget_proposal_count__mutmut_2': xǁGovernanceContractǁget_proposal_count__mutmut_2
    }
    
    def get_proposal_count(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceContractǁget_proposal_count__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceContractǁget_proposal_count__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_proposal_count.__signature__ = _mutmut_signature(xǁGovernanceContractǁget_proposal_count__mutmut_orig)
    xǁGovernanceContractǁget_proposal_count__mutmut_orig.__name__ = 'xǁGovernanceContractǁget_proposal_count'

