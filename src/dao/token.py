"""
x0tta6bl4 Mesh Token Module.

Implements token economics for the mesh network:
- Token balances and transfers
- Staking for voting power and rewards
- Resource payment (bandwidth, storage, compute)
- Reward distribution for node operators
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be paid for with tokens."""
    BANDWIDTH = "bandwidth"      # MB transferred
    STORAGE = "storage"          # MB stored
    COMPUTE = "compute"          # CPU seconds
    RELAY = "relay"              # Messages relayed


@dataclass
class StakeInfo:
    """Information about a node's stake."""
    amount: float
    staked_at: float
    lock_until: float  # Cannot unstake before this time


@dataclass
class ResourceUsage:
    """Track resource usage for billing."""
    node_id: str
    resource_type: ResourceType
    amount: float  # Units depend on resource type
    timestamp: float
    paid: bool = False


class MeshToken:
    """
    Token system for x0tta6bl4 mesh network.
    
    Economics:
    - Nodes stake tokens to participate in governance (voting power)
    - Nodes pay tokens for resources (bandwidth, storage, compute)
    - Nodes earn tokens for providing resources (relay, storage, etc.)
    - Rewards distributed proportionally to stake + uptime
    """
    
    SYMBOL = "X0T"
    DECIMALS = 18
    INITIAL_SUPPLY = 1_000_000_000  # 1 billion tokens
    
    # Pricing (tokens per unit)
    PRICE_PER_MB_BANDWIDTH = 0.001
    PRICE_PER_MB_STORAGE = 0.0001
    PRICE_PER_CPU_SECOND = 0.01
    PRICE_PER_RELAY = 0.0001
    
    # Staking
    MIN_STAKE = 100.0
    STAKE_LOCK_SECONDS = 86400  # 24 hours
    
    # Rewards
    REWARD_POOL_PER_EPOCH = 10000.0  # Tokens distributed per epoch
    EPOCH_DURATION_SECONDS = 3600    # 1 hour epochs
    
    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.stakes: Dict[str, StakeInfo] = {}
        self.resource_usage: List[ResourceUsage] = []
        self.total_supply = self.INITIAL_SUPPLY
        self.treasury_balance = self.INITIAL_SUPPLY
        self.last_epoch_time = time.time()
        self.epoch_number = 0
        
        # Callbacks for external integrations
        self._on_transfer: List[Callable] = []
        self._on_stake_change: List[Callable] = []
        
    # ─────────────────────────────────────────────────────────────
    # Core Token Operations
    # ─────────────────────────────────────────────────────────────
    
    def balance_of(self, node_id: str) -> float:
        """Get token balance of a node."""
        return self.balances.get(node_id, 0.0)
    
    def transfer(self, from_node: str, to_node: str, amount: float) -> bool:
        """Transfer tokens between nodes."""
        if amount <= 0:
            logger.warning(f"Invalid transfer amount: {amount}")
            return False
            
        if self.balance_of(from_node) < amount:
            logger.warning(f"Insufficient balance: {from_node} has {self.balance_of(from_node)}, needs {amount}")
            return False
        
        self.balances[from_node] = self.balance_of(from_node) - amount
        self.balances[to_node] = self.balance_of(to_node) + amount
        
        logger.info(f"Transfer: {from_node} -> {to_node}: {amount} {self.SYMBOL}")
        
        for callback in self._on_transfer:
            callback(from_node, to_node, amount)
        
        # Prometheus metrics
        self._record_metrics_transfer(from_node, to_node)
            
        return True
    
    def _record_metrics_transfer(self, from_node: str, to_node: str):
        """Record transfer in Prometheus metrics."""
        try:
            from src.monitoring.metrics import record_token_transfer, set_token_balance
            record_token_transfer(from_node, to_node)
            set_token_balance(from_node, self.balance_of(from_node))
            set_token_balance(to_node, self.balance_of(to_node))
        except ImportError:
            pass
    
    def mint(self, to_node: str, amount: float, reason: str = "reward") -> bool:
        """Mint new tokens (from treasury or inflation)."""
        if amount <= 0:
            return False
            
        if self.treasury_balance >= amount:
            self.treasury_balance -= amount
        else:
            # Inflation: increase total supply
            self.total_supply += amount
            
        self.balances[to_node] = self.balance_of(to_node) + amount
        logger.info(f"Minted {amount} {self.SYMBOL} to {to_node} ({reason})")
        return True
    
    def burn(self, from_node: str, amount: float, reason: str = "fee") -> bool:
        """Burn tokens (deflationary mechanism)."""
        if amount <= 0 or self.balance_of(from_node) < amount:
            return False
            
        self.balances[from_node] -= amount
        self.total_supply -= amount
        logger.info(f"Burned {amount} {self.SYMBOL} from {from_node} ({reason})")
        return True
    
    # ─────────────────────────────────────────────────────────────
    # Staking (for voting power + rewards)
    # ─────────────────────────────────────────────────────────────
    
    def stake(self, node_id: str, amount: float) -> bool:
        """Stake tokens for voting power and rewards."""
        if amount < self.MIN_STAKE:
            logger.warning(f"Stake amount {amount} below minimum {self.MIN_STAKE}")
            return False
            
        if self.balance_of(node_id) < amount:
            logger.warning(f"Insufficient balance to stake: {node_id}")
            return False
        
        # Deduct from balance
        self.balances[node_id] -= amount
        
        # Add to stake (or increase existing)
        now = time.time()
        if node_id in self.stakes:
            existing = self.stakes[node_id]
            self.stakes[node_id] = StakeInfo(
                amount=existing.amount + amount,
                staked_at=existing.staked_at,  # Keep original stake time
                lock_until=now + self.STAKE_LOCK_SECONDS
            )
        else:
            self.stakes[node_id] = StakeInfo(
                amount=amount,
                staked_at=now,
                lock_until=now + self.STAKE_LOCK_SECONDS
            )
        
        logger.info(f"Staked {amount} {self.SYMBOL} by {node_id} (total: {self.stakes[node_id].amount})")
        
        for callback in self._on_stake_change:
            callback(node_id, self.stakes[node_id].amount)
        
        # Prometheus metrics
        self._record_metrics_stake(node_id)
            
        return True
    
    def _record_metrics_stake(self, node_id: str):
        """Record stake change in Prometheus metrics."""
        try:
            from src.monitoring.metrics import set_token_staked, set_token_balance
            set_token_staked(node_id, self.staked_amount(node_id))
            set_token_balance(node_id, self.balance_of(node_id))
        except ImportError:
            pass
    
    def unstake(self, node_id: str, amount: float) -> bool:
        """Unstake tokens (subject to lock period)."""
        if node_id not in self.stakes:
            logger.warning(f"No stake found for {node_id}")
            return False
            
        stake_info = self.stakes[node_id]
        
        if time.time() < stake_info.lock_until:
            logger.warning(f"Stake locked until {stake_info.lock_until} for {node_id}")
            return False
            
        if amount > stake_info.amount:
            logger.warning(f"Cannot unstake {amount}, only {stake_info.amount} staked")
            return False
        
        # Return to balance
        self.balances[node_id] = self.balance_of(node_id) + amount
        
        # Update or remove stake
        remaining = stake_info.amount - amount
        if remaining < self.MIN_STAKE:
            # Return all remaining stake
            self.balances[node_id] += remaining
            del self.stakes[node_id]
            logger.info(f"Fully unstaked {node_id}")
        else:
            self.stakes[node_id] = StakeInfo(
                amount=remaining,
                staked_at=stake_info.staked_at,
                lock_until=stake_info.lock_until
            )
            logger.info(f"Unstaked {amount} {self.SYMBOL} by {node_id} (remaining: {remaining})")
        
        for callback in self._on_stake_change:
            callback(node_id, self.staked_amount(node_id))
        
        # Prometheus metrics
        self._record_metrics_stake(node_id)
            
        return True
    
    def staked_amount(self, node_id: str) -> float:
        """Get staked amount for a node."""
        if node_id not in self.stakes:
            return 0.0
        return self.stakes[node_id].amount
    
    def total_staked(self) -> float:
        """Get total staked tokens across all nodes."""
        return sum(s.amount for s in self.stakes.values())
    
    def voting_power(self, node_id: str) -> float:
        """
        Get voting power for a node.
        Voting power = staked amount (can add multipliers for lock duration, etc.)
        """
        return self.staked_amount(node_id)
    
    # ─────────────────────────────────────────────────────────────
    # Resource Payments
    # ─────────────────────────────────────────────────────────────
    
    def get_resource_price(self, resource_type: ResourceType, amount: float) -> float:
        """Calculate price for resource usage."""
        prices = {
            ResourceType.BANDWIDTH: self.PRICE_PER_MB_BANDWIDTH,
            ResourceType.STORAGE: self.PRICE_PER_MB_STORAGE,
            ResourceType.COMPUTE: self.PRICE_PER_CPU_SECOND,
            ResourceType.RELAY: self.PRICE_PER_RELAY,
        }
        return prices.get(resource_type, 0.0) * amount
    
    def pay_for_resource(
        self, 
        payer_node: str, 
        provider_node: str, 
        resource_type: ResourceType, 
        amount: float
    ) -> bool:
        """
        Pay for resource usage.
        Payer pays provider directly, small fee burned.
        """
        price = self.get_resource_price(resource_type, amount)
        fee = price * 0.01  # 1% fee burned
        total = price + fee
        
        if self.balance_of(payer_node) < total:
            logger.warning(f"Insufficient balance for resource payment: {payer_node}")
            return False
        
        # Pay provider
        self.transfer(payer_node, provider_node, price)
        
        # Burn fee
        self.burn(payer_node, fee, reason=f"resource_fee_{resource_type.value}")
        
        # Record usage
        self.resource_usage.append(ResourceUsage(
            node_id=payer_node,
            resource_type=resource_type,
            amount=amount,
            timestamp=time.time(),
            paid=True
        ))
        
        logger.info(f"Resource payment: {payer_node} paid {price} to {provider_node} for {amount} {resource_type.value}")
        
        # Prometheus metrics
        try:
            from src.monitoring.metrics import record_resource_payment
            record_resource_payment(payer_node, provider_node, resource_type.value)
        except ImportError:
            pass
        
        return True
    
    # ─────────────────────────────────────────────────────────────
    # Rewards Distribution
    # ─────────────────────────────────────────────────────────────
    
    def distribute_epoch_rewards(self, node_uptimes: Dict[str, float]) -> Dict[str, float]:
        """
        Distribute rewards for an epoch.
        
        Args:
            node_uptimes: Dict of node_id -> uptime percentage (0.0 to 1.0)
            
        Returns:
            Dict of node_id -> reward amount
        """
        now = time.time()
        if now - self.last_epoch_time < self.EPOCH_DURATION_SECONDS:
            logger.debug("Epoch not complete yet")
            return {}
        
        self.epoch_number += 1
        self.last_epoch_time = now
        
        rewards: Dict[str, float] = {}
        
        # Calculate weighted scores (stake * uptime)
        scores: Dict[str, float] = {}
        total_score = 0.0
        
        for node_id, stake_info in self.stakes.items():
            uptime = node_uptimes.get(node_id, 0.0)
            score = stake_info.amount * uptime
            scores[node_id] = score
            total_score += score
        
        if total_score == 0:
            logger.info(f"Epoch {self.epoch_number}: No rewards distributed (no eligible stakers)")
            return rewards
        
        # Distribute proportionally
        for node_id, score in scores.items():
            if score > 0:
                reward = (score / total_score) * self.REWARD_POOL_PER_EPOCH
                self.mint(node_id, reward, reason=f"epoch_{self.epoch_number}_reward")
                rewards[node_id] = reward
                
                # Prometheus metrics
                try:
                    from src.monitoring.metrics import record_token_reward
                    record_token_reward(node_id, self.epoch_number, reward)
                except ImportError:
                    pass
        
        logger.info(f"Epoch {self.epoch_number}: Distributed {sum(rewards.values()):.2f} {self.SYMBOL} to {len(rewards)} nodes")
        return rewards
    
    # ─────────────────────────────────────────────────────────────
    # Integration Hooks
    # ─────────────────────────────────────────────────────────────
    
    def on_transfer(self, callback: Callable):
        """Register callback for transfer events."""
        self._on_transfer.append(callback)
    
    def on_stake_change(self, callback: Callable):
        """Register callback for stake changes (for GovernanceEngine integration)."""
        self._on_stake_change.append(callback)
    
    def get_voting_power_map(self) -> Dict[str, float]:
        """Get voting power for all stakers (for GovernanceEngine)."""
        return {node_id: self.voting_power(node_id) for node_id in self.stakes}


def create_token_integrated_governance(token: MeshToken, node_id: str):
    """
    Factory to create GovernanceEngine with token-based voting power.
    """
    from src.dao.governance import GovernanceEngine
    
    gov = GovernanceEngine(node_id=node_id)
    
    # Sync voting power from token stakes
    def sync_voting_power(staker_node: str, amount: float):
        gov.voting_power[staker_node] = amount
    
    token.on_stake_change(sync_voting_power)
    
    # Initialize with current stakes
    gov.voting_power = token.get_voting_power_map()
    
    return gov
