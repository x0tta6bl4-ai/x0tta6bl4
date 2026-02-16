"""
DAO Initialization Script

Initializes the X0T DAO Environment:
1. Creates the MeshToken instance.
2. Distributes the initial supply (Genesis Allocation).
3. Initializes the GovernanceEngine.
4. Creates a test proposal to verify the system.
5. Simulates voting and execution.

Usage:
    python scripts/init_dao.py
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dao.governance import VoteType
from src.dao.token import MeshToken, create_token_integrated_governance

# Configure Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DAO_INIT")


def main():
    logger.info("🚀 Initializing X0T DAO...")

    # 1. Initialize Token
    token = MeshToken()
    logger.info(f"Token Created: {token.SYMBOL} (Supply: {token.total_supply:,.2f})")

    # 2. Genesis Allocation
    # Total: 1,000,000,000 X0T
    allocations = {
        "treasury": 400_000_000.0,  # 40%
        "team_pool": 200_000_000.0,  # 20%
        "community_airdrop": 100_000_000.0,  # 10%
        "ecosystem_fund": 300_000_000.0,  # 30%
    }

    # Simulating initial distribution
    # We transfer from the implicit "treasury_balance" in MeshToken.__init__
    # Note: MeshToken initialized with full supply in treasury_balance.

    logger.info("💰 Distributing Genesis Allocation...")

    # Verify initial state
    if token.treasury_balance != token.INITIAL_SUPPLY:
        logger.error("Initial treasury balance mismatch!")
        return

    # Create dummy node accounts for demonstration
    nodes = {
        "node-genesis": 0.0,
        "node-team-1": 0.0,
        "node-community-1": 0.0,
        "node-community-2": 0.0,
        "node-voter-whale": 0.0,
    }

    # Distribute
    # Team Allocation
    token.mint("node-team-1", 5_000_000.0, reason="genesis_team_vesting")

    # Community Airdrop (simulated)
    token.mint("node-community-1", 1_000.0, reason="airdrop_batch_1")
    token.mint("node-community-2", 1_500.0, reason="airdrop_batch_1")

    # Whale
    token.mint("node-voter-whale", 100_000.0, reason="strategic_investor")

    logger.info("✅ Allocation Complete.")

    # 3. Governance Setup
    logger.info("🏛️  Initializing Governance Engine...")

    # Integrate Token with Governance
    # We use a dummy dispatcher for now
    gov_node_id = "gov-oracle-1"
    gov = create_token_integrated_governance(token, gov_node_id)

    # Nodes must stake to vote
    logger.info("🔒 Staking tokens for voting power...")
    token.stake("node-team-1", 1_000_000.0)
    token.stake("node-community-1", 500.0)
    token.stake(
        "node-community-2", 1_000.0
    )  # More stake than balance? No, balance is 1500
    token.stake("node-voter-whale", 50_000.0)

    # Verify Voting Power
    logger.info("📊 Current Voting Power (Quadratic potential):")
    for node, stake in token.stakes.items():
        logger.info(f"  - {node}: {stake.amount:,.2f} X0T")

    # 4. Create Proposal
    logger.info("📝 Creating Test Proposal 1: 'Increase Deploy Reward'")

    proposal = gov.create_proposal(
        title="Increase Deploy Reward to 100 X0T",
        description="To incentivize faster network growth, we propose doubling the deploy reward.",
        duration_seconds=60,  # Short duration for test
        actions=[{"type": "update_config", "key": "DEPLOY_REWARD", "value": 100.0}],
    )

    logger.info(f"Proposal Created: ID={proposal.id}")

    # 5. Simulate Voting
    logger.info("🗳️  Casting Votes...")

    # Team votes YES
    gov.cast_vote(
        proposal.id,
        "node-team-1",
        VoteType.YES,
        tokens=token.staked_amount("node-team-1"),
    )

    # Community 1 votes NO
    gov.cast_vote(
        proposal.id,
        "node-community-1",
        VoteType.NO,
        tokens=token.staked_amount("node-community-1"),
    )

    # Whale votes YES
    gov.cast_vote(
        proposal.id,
        "node-voter-whale",
        VoteType.YES,
        tokens=token.staked_amount("node-voter-whale"),
    )

    # 6. Tally
    logger.info("🧮 Tallying Votes (Quadratic)...")
    gov._tally_votes(proposal)

    logger.info(f"🏁 Proposal State: {proposal.state.value}")

    if proposal.state.value == "passed":
        logger.info("🚀 Executing Proposal...")
        results = gov.execute_proposal(proposal.id)
        for res in results:
            logger.info(
                f"Execution Result: {res.action_type} -> {res.success} ({res.detail})"
            )

    logger.info("DAO Initialization Test Complete.")


if __name__ == "__main__":
    main()
