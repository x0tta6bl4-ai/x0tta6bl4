"""
x0tta6bl4 Token Rewards System.
Handles distributing X0T tokens for relay traffic and uptime.
Supports both local simulation and real Base Sepolia transactions.
"""
import logging
import os
import json
from decimal import Decimal

logger = logging.getLogger(__name__)

# Try to import Web3, fall back to simulation if not available
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("Web3 not installed. Using simulation mode.")

# Base Sepolia RPC - should be configured via environment
BASE_SEPOLIA_RPC = os.getenv("RPC_URL", "")

# Minimal ERC20 ABI for transfer
ERC20_ABI = [
    {
        "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

class TokenRewards:
    """Rewards manager for Mesh Nodes. Supports real blockchain transactions."""
    
    def __init__(self, contract_address: str, private_key: str = None, rpc_url: str = None):
        self.contract_address = contract_address
        self.private_key = private_key or os.getenv("OPERATOR_PRIVATE_KEY")
        self.rpc_url = rpc_url or os.getenv("RPC_URL", BASE_SEPOLIA_RPC)
        
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
        
        if WEB3_AVAILABLE and self.private_key:
            try:
                self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
                self.contract = self.web3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=ERC20_ABI
                )
                self.account = self.web3.eth.account.from_key(self.private_key)
                logger.info(f"🔗 Blockchain connected: {self.rpc_url}")
                logger.info(f"   Wallet: {self.account.address}")
            except Exception as e:
                logger.error(f"Failed to initialize Web3: {e}")
                self.web3 = None
        
    def reward_relay(self, node_address: str, packets: int):
        """Calculate and queue reward for relayed packets."""
        # Rate: 0.0001 X0T per packet
        reward = Decimal(packets) * Decimal("0.0001")
        self.pending_rewards += reward
        self.daily_earnings += reward
        
        logger.info(f"💰 Reward queued: {reward:.4f} X0T for {packets} packets")
        
        # Settle rewards (local + blockchain if configured)
        self._settle_rewards(node_address)
        
    def _settle_rewards(self, node_address: str):
        """Execute transfer - local always, blockchain if configured."""
        if self.pending_rewards > 0:
            amount = self.pending_rewards
            self.balance += amount
            self.total_distributed += amount
            
            # Try blockchain transaction if Web3 is configured
            if self.web3 and self.contract and self.account:
                try:
                    tx_hash = self._send_blockchain_reward(node_address, amount)
                    if tx_hash:
                        self.tx_history.append({
                            'hash': tx_hash,
                            'amount': str(amount),
                            'to': node_address,
                            'timestamp': __import__('time').time()
                        })
                        logger.info(f"⛓️  Blockchain TX: {tx_hash}")
                except Exception as e:
                    logger.error(f"Blockchain TX failed: {e}")
            
            self.pending_rewards = Decimal("0.0")
    
    def _send_blockchain_reward(self, to_address: str, amount: Decimal) -> str:
        """Send actual ERC20 transfer on Base Sepolia."""
        if not self.web3:
            return None
            
        try:
            # Convert to wei (18 decimals)
            amount_wei = int(amount * Decimal("1e18"))
            
            # Build transaction
            nonce = self.web3.eth.get_transaction_count(self.account.address)
            
            tx = self.contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_wei
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': self.web3.eth.gas_price,
                'chainId': 84532  # Base Sepolia chain ID
            })
            
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
                balance_wei = self.contract.functions.balanceOf(self.account.address).call()
                balance = Decimal(balance_wei) / Decimal("1e18")
                return f"{balance:.4f}"
            except:
                pass
        return f"{self.balance:.4f}"
            
    def get_daily_earnings(self, node_address: str) -> str:
        return f"{self.daily_earnings:.4f}"
        
    def get_monthly_projection(self, node_address: str) -> str:
        # Simple projection: daily * 30
        return f"{self.daily_earnings * 30:.2f}"
        
    def get_balance(self, node_address: str) -> str:
        return f"{self.balance:.4f}"
