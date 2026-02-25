"""
x0tta6bl4 Tokenomics Sustainability Simulator
==============================================

Simulates the circulation of X0T tokens in a 10k node pilot.
Parameters:
- Relay Reward: 0.0001 X0T per packet
- VPN Subscription: $5/month -> Buyback X0T
- Burn Rate: 1% of resource transactions
- Staking: 1000 X0T min for "Guardian" status
"""

import random
import logging
from dataclasses import dataclass, field
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("token-sim")

@dataclass
class TokenState:
    total_supply: float = 100_000_000.0
    circulating_supply: float = 20_000_000.0
    treasury_usd: float = 0.0
    burned_total: float = 0.0
    staked_total: float = 0.0

from src.ai.tokenomics_engine import AdaptiveRewardEngine

class TokenomicsSimulator:
    def __init__(self, num_nodes: int = 10000, avg_relay_per_node_sec: int = 50):
        self.state = TokenState()
        self.num_nodes = num_nodes
        self.relay_rate = avg_relay_per_node_sec
        self.relay_reward = 0.0001 # X0T
        self.vpn_price_usd = 5.0
        self.x0t_price_usd = 0.5
        self.resource_burn_pct = 0.01
        self.engine = AdaptiveRewardEngine()
        
    def simulate_month(self, num_users: int = 5000):
        """Simulates 1 month of network operation."""
        seconds_in_month = 30 * 24 * 3600
        total_relays = self.num_nodes * self.relay_rate * seconds_in_month
        total_emission = total_relays * self.relay_reward
        
        # 1. Emission
        self.state.circulating_supply += total_emission
        
        # 2. Revenue & Buyback
        total_revenue_usd = num_users * self.vpn_price_usd
        buyback_usd = total_revenue_usd * 0.20
        buyback_tokens = buyback_usd / self.x0t_price_usd
        
        # 3. Resource Burn
        resource_burn = (total_emission * 2) * self.resource_burn_pct
        
        # 4. Apply Burn
        total_burn = buyback_tokens + resource_burn
        self.state.burned_total += total_burn
        self.state.circulating_supply -= total_burn
        
        # 5. Adapt Parameters for next month
        growth_rate = total_emission / self.state.circulating_supply
        metrics = {
            "circulating_supply_growth_rate": growth_rate,
            "burn_to_earn_ratio": total_burn / total_emission if total_emission > 0 else 1.0
        }
        suggestions = self.engine.calculate_new_parameters(metrics)
        self.relay_reward = suggestions["relay_reward_x0t"]
        self.resource_burn_pct = suggestions["resource_burn_pct"]
        
        # 6. Price Update
        inflation_rate = (total_emission - total_burn) / self.state.circulating_supply
        self.x0t_price_usd *= (1.0 - inflation_rate)
        
        return {
            "emission": total_emission,
            "burned": total_burn,
            "revenue_usd": total_revenue_usd,
            "final_price": self.x0t_price_usd,
            "circulating": self.state.circulating_supply
        }

def run_simulation():
    sim = TokenomicsSimulator(num_nodes=10000)
    
    logger.info("=== Starting 12-Month Tokenomics Forecast ===")
    logger.info(f"Nodes: {sim.num_nodes}, Initial Price: ${sim.x0t_price_usd}")
    
    users = 1000 # Starting users
    for month in range(1, 13):
        # Growth: 20% user growth per month
        users = int(users * 1.2)
        results = sim.simulate_month(num_users=users)
        
        logger.info(f"Month {month:02d} | Users: {users:5d} | Price: ${results['final_price']:.3f} | Burn/Earn: {results['burned']/results['emission']:.2%}")
        
        if results['final_price'] < 0.01:
            logger.error("🛑 CRASH: Hyperinflation detected! Rewards too high.")
            break
            
    logger.info("=== Simulation Complete ===")
    logger.info(f"Final Supply: {sim.state.circulating_supply:,.0f} X0T")
    logger.info(f"Total Burned: {sim.state.burned_total:,.0f} X0T")
    logger.info(f"Final Treasury: ${sim.state.treasury_usd:,.0f}")

if __name__ == "__main__":
    run_simulation()
