"""
Core types for X0T Token Bridge.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

TOKEN_BRIDGE_CLAIM_BOUNDARY = (
    "TokenBridge chain-write event only. It records local policy, actuator, "
    "and settlement submission state for X0T bridge operations; it is not "
    "proof of final live external settlement without a verified receipt and "
    "live RPC evidence."
)

TOKEN_BRIDGE_CHAIN_READ_CLAIM_BOUNDARY = (
    "TokenBridge chain-read event only. It records a bounded local observation "
    "of an on-chain event and the resulting MeshToken sync outcome; raw chain "
    "event payload values are redacted and this is not proof of final external "
    "settlement beyond the cited transaction/block metadata."
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
    rpc_urls: List[str] = field(default_factory=list)
    rpc_url: str = "" # Keep for backward compatibility
    contract_address: str = ""
    private_key: str = ""
    chain_id: int = 84532  # Base Sepolia (testnet default)
    poll_interval: int = 12  # seconds (1 block on Base)
    confirmations: int = 2
    gas_limit: int = 200000
    max_gas_price_gwei: float = 50.0
    allow_simulated_chain_writes: bool = False
